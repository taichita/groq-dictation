"""自己診断ツール。

「音声入力が不安定」なときに、どこが原因かを切り分けるためのスクリプト。
順に: 設定 → マイク一覧 → 3秒テスト録音 → Groq送信 → 置換 を確認する。

使い方:
    python check.py
"""

import sys
import time

from config import AppConfig


def main() -> int:
    print("=" * 56)
    print(" Groq Dictation 自己診断")
    print("=" * 56)

    cfg = AppConfig.load()

    # 1) 設定
    print("\n[1/4] 設定の確認")
    problems = cfg.validate()
    if problems:
        for p in problems:
            print("  ❌", p)
        print("  → .env を設定してから再実行してください。")
        return 1
    masked = cfg.groq_api_key[:6] + "..." + cfg.groq_api_key[-4:]
    print(f"  ✅ GROQ_API_KEY 読み込みOK ({masked})")
    print(f"  ・モデル: {cfg.groq_model}  言語: {cfg.language}")

    # 2) マイク
    print("\n[2/4] マイクデバイスの確認")
    try:
        import sounddevice as sd

        default_in = sd.query_devices(kind="input")
        print(f"  ✅ 既定の入力デバイス: {default_in['name']}")
    except Exception as e:
        print(f"  ❌ マイクを取得できません: {e}")
        print("  → システム設定 > プライバシーとセキュリティ > マイク でターミナルを許可してください。")
        return 1

    # 3) テスト録音
    print("\n[3/4] 3秒間テスト録音します。何か話してください...")
    from audio_recorder import AudioRecorder, MicPermissionError

    rec = AudioRecorder(sample_rate=cfg.sample_rate, channels=cfg.channels)
    try:
        rec.start()
        for i in range(3, 0, -1):
            print(f"     録音中... {i}")
            time.sleep(1)
        audio, duration = rec.stop()
    except MicPermissionError as e:
        print(f"  ❌ {e}")
        return 1

    if audio.size == 0:
        print("  ❌ 録音データが空です。マイク権限/入力デバイスを確認してください。")
        return 1

    import numpy as np

    peak = float(np.max(np.abs(audio)))
    print(f"  ✅ 録音OK ({duration:.1f}秒, 最大音量 {peak:.3f})")
    if peak < 0.01:
        print("  ⚠ 音がほとんど入っていません。マイクのミュート/入力音量を確認してください。")

    # 4) Groq送信
    print("\n[4/4] Groqへ送信して文字起こしします...")
    import tempfile

    from groq_client import GroqTranscriptionClient, TranscriptionError
    from replacement import ReplacementEngine

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp.close()
    rec.save_wav(tmp.name, audio)
    try:
        client = GroqTranscriptionClient(
            api_key=cfg.groq_api_key,
            model=cfg.groq_model,
            timeout=cfg.request_timeout,
            max_retries=cfg.max_retries,
        )
        t0 = time.time()
        text = client.transcribe(tmp.name, language=cfg.language)
        elapsed = time.time() - t0
        replaced = ReplacementEngine(cfg.replacement_file).apply(text)
        print(f"  ✅ 文字起こし成功 ({elapsed:.1f}秒)")
        print(f"     生テキスト : {text!r}")
        print(f"     置換後     : {replaced!r}")
    except TranscriptionError as e:
        print(f"  ❌ {e}")
        return 1
    finally:
        import os

        if os.path.exists(tmp.name):
            os.remove(tmp.name)

    print("\n🎉 すべて正常です。`python app.py` で本番起動できます。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
