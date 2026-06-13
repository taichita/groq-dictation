"""Groq Dictation — Groq Speech-to-Text だけを使う高速音声入力アプリ(MVP)。

フロー:
  ホットキー → 録音 → 一時wav → Groq送信 → 置換辞書 → クリップボード → 自動貼り付け
LLM後処理は一切しない(要件)。

安定化の要点(スターター版からの主な改善):
  1) 文字起こし/貼り付けはワーカースレッドで実行。ホットキー監視が固まらない。
  2) コールバック内の例外は必ず握り込む。1回の失敗でアプリが落ちない。
  3) 録音中の二重押し・処理中の押下を状態とロックで安全に捌く。
  4) 短すぎる録音(誤爆)・空録音は送信せずスキップ。
  5) 長すぎる録音は自動停止(413/巨大ファイル対策)。
  6) コンソールとログファイルの両方に出力。失敗時に原因を後から追える。
  7) 音(macOS)で録音状態が分かる。
"""

import logging
import os
import platform
import signal
import sys
import tempfile
import threading

# 多重起動防止に使う名前付きミューテックスの名前（同一ユーザーセッション内で一意）
SINGLE_INSTANCE_NAME = "GroqDictationSingleton"

from pynput import keyboard

import key_setup
import permissions
import sound_cue
from audio_recorder import AudioRecorder, MicPermissionError
from clipboard_paste import copy_and_paste
from config import AppConfig
from groq_client import GroqTranscriptionClient, TranscriptionError
from replacement import ReplacementEngine
from transcript_log import SuperwhisperLogger, TranscriptLogger
from overlay_indicator import OverlayIndicator
from tray_icon import TrayIndicator


def setup_logging(log_file: str) -> None:
    fmt = "[%(asctime)s] %(levelname)s: %(message)s"
    datefmt = "%H:%M:%S"
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    except OSError:
        pass  # ログファイルが作れなくてもコンソールには出す
    logging.basicConfig(level=logging.INFO, format=fmt, datefmt=datefmt, handlers=handlers)


logger = logging.getLogger("groq_dictation")


class GroqDictationApp:
    def __init__(self):
        self.config = AppConfig.load()
        # 設定(SOUND_CUE)に従って音のオン/オフを反映（既定はオフ運用・状態はトレイで表示）
        sound_cue.set_enabled(self.config.sound_cue)
        self.recorder = AudioRecorder(
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
        )
        # client はキー確定後に作る（未設定でも起動時に落ちないように）
        self.client: GroqTranscriptionClient | None = None
        self.replacer = ReplacementEngine(self.config.replacement_file)
        self.transcript_logger = TranscriptLogger(
            enabled=self.config.transcript_log,
            directory=self.config.transcript_dir,
            mode=self.config.transcript_mode,
        )
        # superwhisper と同じ場所・形式での蓄積（夜間タスク抽出がそのまま読める）
        self.sw_logger = SuperwhisperLogger(
            enabled=bool(self.config.superwhisper_dir),
            directory=self.config.superwhisper_dir,
            model=self.config.groq_model,
            language=self.config.language,
        )

        # 通知領域(右下)の状態アイコン（待機=グレー/録音中=赤/変換中=オレンジ）
        self.tray = TrayIndicator(
            enabled=self.config.tray_icon,
            on_quit=self._request_quit,
        )
        # トレイは隠れがちなので、録音中だけ画面隅に小さな丸を最前面表示する保険
        self.overlay = OverlayIndicator(enabled=self.config.overlay_icon)

        # 状態管理
        self._lock = threading.Lock()
        self.is_recording = False
        self.is_processing = False
        self.current_audio_path: str | None = None
        self._auto_stop_timer: threading.Timer | None = None
        self._stop_event = threading.Event()

    def _set_state(self, state: str) -> None:
        """状態表示(トレイ＋画面隅の目印)をまとめて更新する。"""
        self.tray.set_state(state)
        self.overlay.set_state(state)

    # ----- ホットキー入口（pynput監視スレッドから呼ばれる） -----
    def toggle_recording(self) -> None:
        # 監視スレッドを絶対に殺さないため、全部を try で包む
        try:
            with self._lock:
                if self.is_processing:
                    logger.info("⏳ 処理中です。完了まで少しお待ちください。")
                    return
                if not self.is_recording:
                    self._start_recording_locked()
                else:
                    self._begin_stop_locked()
        except Exception:
            logger.exception("ホットキー処理中に予期しないエラー(継続します)")

    # ----- 録音開始 -----
    def _start_recording_locked(self) -> None:
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            tmp.close()
            self.current_audio_path = tmp.name
            self.recorder.start()
        except MicPermissionError as e:
            logger.error("🎙 録音を開始できません: %s", e)
            sound_cue.play("error")
            self._cleanup_temp()
            return
        except Exception:
            logger.exception("🎙 録音開始に失敗")
            sound_cue.play("error")
            self._cleanup_temp()
            return

        self.is_recording = True
        self._set_state("recording")
        sound_cue.play("start")

        # MAX_RECORD_SEC=0（既定）なら自動停止せず長さ無制限。
        # 長い録音は送信時に自動分割するので、巨大ファイルで失敗する心配はない。
        if self.config.max_record_sec and self.config.max_record_sec > 0:
            logger.info("🔴 録音開始（もう一度ホットキーで停止 / 最大 %.0f 秒で自動停止）",
                        self.config.max_record_sec)
            self._auto_stop_timer = threading.Timer(
                self.config.max_record_sec, self._auto_stop
            )
            self._auto_stop_timer.daemon = True
            self._auto_stop_timer.start()
        else:
            self._auto_stop_timer = None
            logger.info("🔴 録音開始（もう一度ホットキーで停止 / 自動停止なし＝長さ無制限）")

    def _auto_stop(self) -> None:
        try:
            with self._lock:
                if self.is_recording and not self.is_processing:
                    logger.info("⏱ 最大録音時間に達したため自動停止します。")
                    self._begin_stop_locked()
        except Exception:
            logger.exception("自動停止中のエラー(継続します)")

    # ----- 録音停止 → ワーカーへ -----
    def _begin_stop_locked(self) -> None:
        self.is_recording = False
        self.is_processing = True
        self._set_state("processing")
        if self._auto_stop_timer is not None:
            self._auto_stop_timer.cancel()
            self._auto_stop_timer = None
        sound_cue.play("stop")
        logger.info("⏹ 録音停止")

        worker = threading.Thread(target=self._process, daemon=True)
        worker.start()

    # ----- 重い処理（別スレッド） -----
    def _process(self) -> None:
        audio_path = self.current_audio_path
        try:
            audio_data, duration = self.recorder.stop()

            if audio_data.size == 0 or duration < self.config.min_record_sec:
                logger.info(
                    "🟡 録音が短すぎます(%.2f秒)。送信せずスキップします。", duration
                )
                sound_cue.play("error")
                return

            raw_text = self._transcribe_audio(audio_data, duration)
            text = self.replacer.apply(raw_text)

            if not text.strip():
                logger.info("🟡 文字起こし結果が空でした。無音だった可能性があります。")
                sound_cue.play("error")
                return

            logger.info("✅ 文字起こし成功: %s", text)

            # ローカルへ蓄積（失敗しても貼り付けは続行）
            self.transcript_logger.append(text, duration)
            self.sw_logger.append(text, raw_text, duration)

            copied, pasted = copy_and_paste(text, auto_paste=self.config.auto_paste)
            if copied:
                logger.info("📋 クリップボードへコピーしました。")
            if self.config.auto_paste:
                if pasted:
                    logger.info("⌨️  入力欄へ自動貼り付けしました。")
                    sound_cue.play("done")
                else:
                    logger.warning(
                        "貼り付けに失敗しました（コピーは成功）。手動で Cmd+V してください。"
                    )
                    sound_cue.play("error")
            else:
                sound_cue.play("done")

        except TranscriptionError as e:
            logger.error("❌ 文字起こし失敗: %s", e)
            sound_cue.play("error")
        except Exception:
            logger.exception("❌ 処理中に予期しないエラー")
            sound_cue.play("error")
        finally:
            self._cleanup_temp()
            with self._lock:
                self.is_processing = False
            self._set_state("idle")

    # ----- 文字起こし（長い録音は自動分割して送信） -----
    def _transcribe_audio(self, audio_data, duration: float) -> str:
        """録音データを文字起こしして返す。

        Groq の1リクエストには上限（おおよそ13分相当のファイルサイズ）があるため、
        長い録音は CHUNK_SEC ごとに「間」で自動分割して順番に送り、結果をつなげる。
        一部の送信が失敗しても、成功した分はつなげて返す（全消えを防ぐ）。
        """
        chunks = self.recorder.split_chunks(audio_data, self.config.chunk_sec)
        total = len(chunks)
        if total <= 1:
            logger.info("📤 Groqへ送信中（%.1f秒の音声）...", duration)
        else:
            logger.info(
                "📤 長い音声（%.0f秒）を %d 個に分割して送信します...", duration, total
            )

        parts: list[str] = []
        failures = 0
        for i, chunk in enumerate(chunks, start=1):
            path = None
            try:
                fd, path = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                self.recorder.save_wav(path, chunk)
                if total > 1:
                    logger.info("  → 送信中 %d/%d ...", i, total)
                part = self.client.transcribe(path, language=self.config.language)
                parts.append(part.strip())
            except TranscriptionError as e:
                failures += 1
                logger.error("  ✗ %d/%d の送信に失敗（この部分はスキップ）: %s", i, total, e)
            finally:
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass

        if total > 1 and failures:
            logger.warning(
                "⚠ %d/%d 個の送信に失敗しました（成功した分だけ貼り付けます）", failures, total
            )
        if total and failures == total:
            raise TranscriptionError("すべての分割送信に失敗しました。")
        return "".join(parts)

    # ----- 後始末 -----
    def _cleanup_temp(self) -> None:
        path = self.current_audio_path
        self.current_audio_path = None
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError as e:
                logger.warning("一時ファイル削除に失敗: %s", e)

    # ----- 起動 -----
    def run(self) -> None:
        logger.info("=" * 56)
        logger.info("Groq Dictation を起動しました")
        logger.info("モデル: %s / 言語: %s", self.config.groq_model, self.config.language)

        # APIキーが無ければ初回設定ダイアログで取得（配布時の各自設定）
        if not self.config.groq_api_key:
            logger.info("APIキーが未設定です。初回設定を開きます...")
            key = key_setup.ensure_key_interactive()
            if not key:
                logger.error("⚠ APIキーが設定されませんでした。終了します。")
                logger.error("→ もう一度起動するか『キー設定.command』から設定してください。")
                return
            self.config = AppConfig.load()  # 保存されたキーで再読み込み

        self.client = GroqTranscriptionClient(
            api_key=self.config.groq_api_key,
            model=self.config.groq_model,
            timeout=self.config.request_timeout,
            max_retries=self.config.max_retries,
        )
        logger.info("✅ APIキー読み込み成功")

        logger.info("ホットキー: %s （押すたびに 録音開始 / 停止）", self.config.hotkey)
        logger.info("自動貼り付け: %s", "ON" if self.config.auto_paste else "OFF")

        # macOS: グローバルホットキーの受信には「入力監視」、
        # 自動貼り付けには「アクセシビリティ」が必要（別々の権限）。
        # 未許可なら公式APIで許可ダイアログを出し、要求元(このpython)を登録させる。
        if platform.system() == "Darwin":
            im = permissions.request_input_monitoring()
            ax = permissions.request_accessibility(prompt=True)
            if im is False:
                logger.warning(
                    "『入力監視』が未許可です。ホットキーを受信できません。"
                    "「システム設定 > プライバシーとセキュリティ > 入力監視」で python をオンにしてください。"
                )
            if ax is False:
                logger.warning(
                    "『アクセシビリティ』が未許可です。自動貼り付けができません。"
                    "「システム設定 > プライバシーとセキュリティ > アクセシビリティ」で python をオンにしてください。"
                )
            if im and ax:
                logger.info("✅ 入力監視・アクセシビリティ 許可OK")

        logger.info("終了するには Ctrl+C を押してください。")
        logger.info("=" * 56)

        # Ctrl+C / kill で綺麗に終了
        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)

        # 状態表示を開始（トレイ＝常駐／画面隅の目印＝録音中だけ表示）
        self.tray.start()
        self.overlay.start()

        # 診断モード: DEBUG_KEYS ファイルがあれば、届いたキーを keydiag.log に記録
        self._maybe_start_keydiag()

        try:
            # pynput標準の GlobalHotKeys は「左右を区別した修飾キーだけ」の組み合わせ
            # (例: 右Ctrl+左Alt) を取りこぼす。実キーコード(vk)を直接照合する自前の
            # 監視に統一して、修飾だけの組み合わせ・文字キー併用のどちらも確実に拾う。
            required = self._parse_hotkey_ids(self.config.hotkey)
            if not required:
                raise ValueError(self.config.hotkey)
            pressed: set = set()
            self._chord_ready = True

            def on_press(key):
                try:
                    pressed.update(self._key_ids(key))
                    if required.issubset(pressed):
                        if self._chord_ready:
                            self._chord_ready = False
                            self.toggle_recording()
                except Exception:
                    logger.exception("ホットキー処理中の予期しないエラー(継続します)")

            def on_release(key):
                try:
                    for i in self._key_ids(key):
                        pressed.discard(i)
                    if not required.issubset(pressed):
                        self._chord_ready = True
                except Exception:
                    pass

            with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
                self._listener = listener
                while not self._stop_event.is_set():
                    self._stop_event.wait(0.5)
                listener.stop()
        except ValueError as e:
            logger.error(
                "ホットキー '%s' の指定が不正です。.env の HOTKEY を見直してください。詳細: %s",
                self.config.hotkey, e,
            )
        finally:
            self._shutdown()

    # ----- ホットキー照合（実キーコード/文字ベース） -----
    @staticmethod
    def _parse_hotkey_ids(spec: str) -> set:
        """HOTKEY 文字列を「必要なキーの識別子集合」に変換する。
        修飾キーは vk、文字キーは小文字に正規化。"""
        ids: set = set()
        try:
            for key in keyboard.HotKey.parse(spec):
                vk = getattr(key, "vk", None)
                if vk is None:
                    vk = getattr(getattr(key, "value", None), "vk", None)
                ch = getattr(key, "char", None)
                if vk is not None:
                    ids.add(vk)
                elif ch:
                    ids.add(ch.lower())
        except ValueError:
            return set()
        return ids

    @staticmethod
    def _key_ids(key) -> set:
        """押された/離されたキーを識別子集合にする。
        左右の修飾キーには総称(Ctrl=17/Alt=18/Shift=16)も足し、
        『総称指定』の HOTKEY でも左右どちらでも反応するようにする。
        逆に左右指定(右Ctrl=163 等)はその vk が一致したときだけ反応する。"""
        ids: set = set()
        vk = getattr(key, "vk", None)
        if vk is None:
            vk = getattr(getattr(key, "value", None), "vk", None)
        if vk is not None:
            ids.add(vk)
            if vk in (162, 163):
                ids.add(17)
            elif vk in (164, 165):
                ids.add(18)
            elif vk in (160, 161):
                ids.add(16)
        ch = getattr(key, "char", None)
        if ch:
            ids.add(ch.lower())
        return ids

    def _maybe_start_keydiag(self) -> None:
        from config import BASE_DIR

        if not (BASE_DIR / "DEBUG_KEYS").exists():
            return
        diag_path = BASE_DIR / "keydiag.log"
        logger.info("🔬 キー診断モード ON（届いたキーを keydiag.log に記録）")

        def on_press(key):
            try:
                with open(diag_path, "a", encoding="utf-8") as f:
                    f.write(f"press {key}\n")
            except Exception:
                pass

        try:
            dl = keyboard.Listener(on_press=on_press)
            dl.daemon = True
            dl.start()
            self._debug_listener = dl
        except Exception as e:
            logger.warning("キー診断リスナー起動失敗: %s", e)

    def _on_signal(self, signum, frame) -> None:
        logger.info("終了します...")
        self._stop_event.set()

    def _request_quit(self) -> None:
        """トレイの『終了』メニューから呼ばれる。常駐を綺麗に止める。"""
        logger.info("トレイから終了が選ばれました。")
        self._stop_event.set()
        if getattr(self, "_listener", None) is not None:
            try:
                self._listener.stop()
            except Exception:
                pass

    def _shutdown(self) -> None:
        if self._auto_stop_timer is not None:
            self._auto_stop_timer.cancel()
        if self.is_recording:
            try:
                self.recorder.stop()
            except Exception:
                pass
        self._cleanup_temp()
        self.tray.stop()
        self.overlay.stop()
        logger.info("👋 Groq Dictation を終了しました。")


def _acquire_single_instance():
    """多重起動を防ぐ。既に起動中なら False を返す。
    Windows は名前付きミューテックス、それ以外は素通り(None)。
    見張り役が何度起動を試みても、2つ目以降はここで終了する。"""
    if platform.system() != "Windows":
        return None
    import ctypes
    handle = ctypes.windll.kernel32.CreateMutexW(None, False, SINGLE_INSTANCE_NAME)
    ERROR_ALREADY_EXISTS = 183
    if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        return False
    return handle  # プロセスが生きている間ハンドルを保持し続ける


if __name__ == "__main__":
    # 既に動いていれば静かに終了（見張り役からの重複起動を弾く）
    _instance = _acquire_single_instance()
    if _instance is False:
        sys.exit(0)
    cfg = AppConfig.load()
    setup_logging(cfg.log_file)
    GroqDictationApp().run()
