"""設定の一元管理。

.env から値を読み込み、アプリ全体で使う設定を1か所にまとめる。
APIキーはコードに直書きせず、必ず .env から読む。
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

import key_setup
import user_settings

DEFAULT_HOTKEY = "<ctrl_r>+<alt>"

# 「本物の環境変数」をモジュール読み込み時に1回だけ捕捉する。
# load_dotenv() は os.environ に .env の値を注入するため、load() を複数回呼ぶと
# 2回目以降は .env の値が環境変数と区別できなくなる。それを避けるための固定値。
_REAL_ENV_KEY = os.environ.get("GROQ_API_KEY", "")
_REAL_ENV_HOTKEY = os.environ.get("HOTKEY", "")

# このファイルが置かれているディレクトリ（プロジェクトルート）を基準にする。
# どこから python app.py しても .env / replacement.json を確実に見つけるため。
BASE_DIR = Path(__file__).resolve().parent


def _resolve_api_key(real_env_key: str) -> str:
    """APIキーを優先順位つきで解決する。
    1) 環境変数 GROQ_API_KEY (load_dotenv より前に存在したもの)
    2) ユーザー設定ファイル(各自のキー / 配布時はこれが本命)
    3) プロジェクト .env (開発・個人利用)
    プレースホルダのままの値は無視する。
    """
    if not key_setup.is_placeholder(real_env_key):
        return real_env_key.strip()

    user_key = key_setup.load_user_key()
    if not key_setup.is_placeholder(user_key):
        return user_key.strip()

    dotenv_key = os.getenv("GROQ_API_KEY", "")  # load_dotenv 後 = .env の値
    if not key_setup.is_placeholder(dotenv_key):
        return dotenv_key.strip()

    return ""  # 見つからなければ空（呼び出し側で初回設定を促す）


def _resolve_hotkey(real_env_hotkey: str) -> str:
    """ホットキーを優先順位つきで解決する。
    1) 環境変数 HOTKEY
    2) ユーザー設定(各自が設定したショートカット / 配布時の本命)
    3) プロジェクト .env
    4) 既定値
    """
    if real_env_hotkey.strip():
        return real_env_hotkey.strip()
    user_hotkey = user_settings.get("HOTKEY", "")
    if user_hotkey.strip():
        return user_hotkey.strip()
    dotenv_hotkey = os.getenv("HOTKEY", "")
    if dotenv_hotkey.strip():
        return dotenv_hotkey.strip()
    return DEFAULT_HOTKEY


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _resolve_str(name: str, default: str = "") -> str:
    """ユーザー設定 > .env の順で文字列設定を解決する。"""
    v = user_settings.get(name, "")
    if v.strip():
        return v.strip()
    v = os.getenv(name, "")
    return v.strip() if v.strip() else default


def _resolve_bool(name: str, default: bool) -> bool:
    v = user_settings.get(name, "")
    if not v.strip():
        v = os.getenv(name, "")
    if not v.strip():
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass
class AppConfig:
    groq_api_key: str
    groq_model: str
    language: str
    hotkey: str
    auto_paste: bool
    replacement_file: str
    # --- 安定化のための追加設定 ---
    sample_rate: int          # 録音サンプリングレート（Hz）
    channels: int             # 録音チャンネル数（1=モノラル）
    min_record_sec: float     # これより短い録音は無視（誤爆/空録音対策）
    max_record_sec: float     # これを超えたら自動停止（413/巨大ファイル対策）
    request_timeout: int      # Groq API のタイムアウト秒
    max_retries: int          # タイムアウト/5xx 時のリトライ回数
    sound_cue: bool           # 録音開始/停止のビープ音
    tray_icon: bool           # 通知領域(右下)に状態アイコンを出す
    overlay_icon: bool        # 録音中だけ画面隅に小さな丸を最前面表示する
    log_file: str             # ログ出力先ファイル
    # --- 文字起こしの蓄積（Obsidian等への記録） ---
    transcript_log: bool      # 記録を有効にするか
    transcript_dir: str       # 追記先フォルダ
    transcript_mode: str      # "daily"(1日1ファイル) / "single"
    # --- superwhisper 互換の保存（recordings/<epoch>/meta.json） ---
    superwhisper_dir: str     # 設定すると superwhisper と同じ場所・形式でも保存する

    @classmethod
    def load(cls) -> "AppConfig":
        # load_dotenv は既存の環境変数を上書きしないので、.env を読む前に
        # 「本物の環境変数」を捕捉しておき、キー解決の最優先に使う。
        real_env_key = _REAL_ENV_KEY
        real_env_hotkey = _REAL_ENV_HOTKEY
        # BASE_DIR の .env を明示的に読む（カレントディレクトリに依存しない）。
        load_dotenv(BASE_DIR / ".env")

        replacement_file = os.getenv("REPLACEMENT_FILE", "replacement.json")
        if not os.path.isabs(replacement_file):
            replacement_file = str(BASE_DIR / replacement_file)

        log_file = os.getenv("LOG_FILE", "groq_dictation.log")
        if not os.path.isabs(log_file):
            log_file = str(BASE_DIR / log_file)

        return cls(
            groq_api_key=_resolve_api_key(real_env_key),
            groq_model=os.getenv("GROQ_MODEL", "whisper-large-v3-turbo").strip(),
            language=os.getenv("LANGUAGE", "ja").strip(),
            hotkey=_resolve_hotkey(real_env_hotkey),
            auto_paste=_get_bool("AUTO_PASTE", True),
            replacement_file=replacement_file,
            sample_rate=int(_get_float("SAMPLE_RATE", 16000)),
            channels=int(_get_float("CHANNELS", 1)),
            min_record_sec=_get_float("MIN_RECORD_SEC", 0.4),
            max_record_sec=_get_float("MAX_RECORD_SEC", 120.0),
            request_timeout=int(_get_float("REQUEST_TIMEOUT", 60)),
            max_retries=int(_get_float("MAX_RETRIES", 2)),
            sound_cue=_get_bool("SOUND_CUE", False),
            tray_icon=_get_bool("TRAY_ICON", True),
            overlay_icon=_get_bool("OVERLAY_ICON", True),
            log_file=log_file,
            transcript_log=_resolve_bool("TRANSCRIPT_LOG", False),
            # 既定はアプリの1つ上（=リポジトリ直下）の「音声入力ログ」。
            # アプリを AI2027/groq-dictation に置けば AI2027/音声入力ログ になり、
            # Mac/Windows どちらでも正しい場所に保存される（絶対パス設定も可）。
            transcript_dir=_resolve_str(
                "TRANSCRIPT_DIR", str(BASE_DIR.parent / "音声入力ログ")
            ),
            transcript_mode=_resolve_str("TRANSCRIPT_MODE", "daily"),
            superwhisper_dir=_resolve_str("SUPERWHISPER_DIR", ""),
        )

    def validate(self) -> list[str]:
        """致命的でない警告も含めて問題点を返す。空ならOK。"""
        problems = []
        if not self.groq_api_key:
            problems.append(
                "GROQ_API_KEY が未設定です。.env に GROQ_API_KEY=... を書いてください。"
            )
        elif self.groq_api_key in ("your_groq_api_key_here", "ここにAPIキー"):
            problems.append(
                "GROQ_API_KEY がサンプルのままです。Groq Console で取得した本物のキーに書き換えてください。"
            )
        return problems
