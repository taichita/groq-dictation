"""文字起こし結果をローカル(Markdown)に無限に蓄積する。

各文字起こしの確定テキスト(置換後)を、指定フォルダの Markdown に追記する。
Obsidian でそのまま開ける形式。1日1ファイル / 単一ファイル を選べる。

設定(config 経由):
- enabled  : 記録するか
- directory: 追記先フォルダ
- mode     : "daily"(1日1ファイル) / "single"(1ファイルに全部)
"""

import json
import logging
import platform
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def machine_name() -> str:
    """PCを表す短い名前。2台で同じファイルを編集せず競合させないためのサブフォルダ名。"""
    s = platform.system()
    if s == "Darwin":
        return "mac"
    if s == "Windows":
        return "windows"
    return "other"


class TranscriptLogger:
    def __init__(self, enabled: bool, directory: str, mode: str = "daily"):
        self.enabled = enabled
        # PCごとのサブフォルダに分ける（mac/ , windows/）。
        base = Path(directory).expanduser() if directory else None
        self.directory = (base / machine_name()) if base else None
        self.mode = mode if mode in ("daily", "single") else "daily"

    def append(self, text: str, duration: float | None = None) -> None:
        if not self.enabled or not self.directory:
            return
        body = " ".join(text.split())  # 改行・連続空白を1スペースに整える
        if not body:
            return
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            now = datetime.now()
            if self.mode == "single":
                path = self.directory / "音声入力ログ.md"
                header = "# 音声入力ログ\n\n"
                entry = f"- {now:%Y-%m-%d %H:%M}  {body}\n"
            else:  # daily
                path = self.directory / f"{now:%Y-%m-%d}.md"
                header = f"## {now:%Y-%m-%d} の音声入力\n\n"
                entry = f"- {now:%H:%M}  {body}\n"

            new_file = not path.exists()
            with path.open("a", encoding="utf-8") as f:
                if new_file:
                    f.write(header)
                f.write(entry)
            logger.info("📝 記録しました → %s", path)
        except Exception as e:
            # 記録失敗は本来の音声入力フローを止めない
            logger.warning("文字起こしログの保存に失敗: %s", e)


class SuperwhisperLogger:
    """superwhisper と同じ recordings/<epoch>/meta.json 形式で1件ずつ保存する。

    既存の夜間タスク抽出（board/ingest_voice_raw.py）が読む形式に合わせ、
    superwhisper の代わりに同じ場所へ蓄積し続けられるようにするためのもの。
    読み取り側が使うフィールド: datetime / result / rawResult / duration(ms) /
    modelName / languageSelected。
    """

    def __init__(self, enabled: bool, directory: str, model: str = "",
                 language: str = "ja"):
        self.enabled = enabled
        self.directory = Path(directory).expanduser() if directory else None
        self.model = model or "Groq Dictation"
        self.language = language or "ja"

    def append(self, result: str, raw: str = "", duration_sec: float | None = None) -> None:
        if not self.enabled or not self.directory:
            return
        body = " ".join((result or "").split())
        if not body:
            return
        try:
            now = datetime.now()
            # superwhisper はフォルダ名に epoch 秒を使う。同一秒の衝突だけ避ける。
            epoch = str(int(now.timestamp()))
            folder = self.directory / epoch
            n = 0
            while folder.exists():
                n += 1
                folder = self.directory / f"{epoch}-{n}"
            folder.mkdir(parents=True, exist_ok=True)
            meta = {
                "datetime": now.strftime("%Y-%m-%dT%H:%M:%S"),
                "modelName": self.model,
                "duration": int((duration_sec or 0) * 1000),
                "languageSelected": self.language,
                "rawResult": raw or result,
                "result": result,
                "platform": platform.system().lower(),
                "source": "groq-dictation",
            }
            (folder / "meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            logger.info("📝 記録しました → %s", folder / "meta.json")
        except Exception as e:
            logger.warning("文字起こしログ(superwhisper形式)の保存に失敗: %s", e)
