"""APIキーの自己設定（各自が自分のGroqキーを登録する仕組み）。

配布時、利用者は .env を編集できない/したくない。そこで:
- キーは各ユーザーごとの設定ファイルに保存する
  ( ~/Library/Application Support/GroqDictation/config.env )
- 未設定なら初回起動時にダイアログで入力してもらう
- 入力されたキーはGroqに問い合わせて有効か検証してから保存する

キーの探索優先順位(config.py と合わせる):
  1) 環境変数 GROQ_API_KEY
  2) ユーザー設定ファイル(上記)
  3) プロジェクト直下の .env
"""

import logging
import platform
import subprocess

import requests

import user_settings

logger = logging.getLogger(__name__)

IS_MAC = platform.system() == "Darwin"

# 互換のため公開（check.py 等が参照）
USER_CONFIG_DIR = user_settings.USER_CONFIG_DIR
USER_CONFIG_FILE = user_settings.USER_CONFIG_FILE

_PLACEHOLDERS = {"", "your_groq_api_key_here", "ここにAPIキー", "ここに gsk_... を貼り付け"}

MODELS_ENDPOINT = "https://api.groq.com/openai/v1/models"


def is_placeholder(key: str | None) -> bool:
    return (key or "").strip() in _PLACEHOLDERS


def load_user_key() -> str:
    """ユーザー設定ファイルから GROQ_API_KEY を読む。無ければ空文字。"""
    return user_settings.get("GROQ_API_KEY", "")


def save_user_key(key: str) -> None:
    """ユーザー設定ファイルに保存(他の設定は保持・本人のみ読み書き)。"""
    user_settings.set("GROQ_API_KEY", key)
    logger.info("APIキーを保存しました: %s", USER_CONFIG_FILE)


def validate_key(key: str, timeout: int = 15) -> tuple[bool, str]:
    """Groqにキーが有効か問い合わせる。(OKか, メッセージ) を返す。"""
    key = (key or "").strip()
    if is_placeholder(key):
        return False, "キーが入力されていません。"
    if not key.startswith("gsk_"):
        return False, "キーの形式が違うようです（通常 gsk_ で始まります）。"
    try:
        r = requests.get(
            MODELS_ENDPOINT,
            headers={"Authorization": f"Bearer {key}"},
            timeout=timeout,
        )
    except requests.exceptions.RequestException as e:
        return False, f"ネットワークに接続できませんでした: {e}"
    if r.status_code == 401:
        return False, "キーが無効です（401）。Groq Consoleで再確認してください。"
    if not r.ok:
        return False, f"検証に失敗しました（{r.status_code}）。"
    return True, "キーは有効です。"


def prompt_for_key_dialog() -> str | None:
    """macOSのダイアログでキーを入力してもらう。キャンセルなら None。"""
    if not IS_MAC:
        # 非macOS(Windows等)はコンソール入力にフォールバック
        try:
            return input("Groq APIキー (gsk_...) を貼り付けてEnter: ").strip()
        except EOFError:
            return None

    msg = (
        "Groq 音声入力に使う APIキーを貼り付けてください。\\n\\n"
        "まだ無い場合: ブラウザで https://console.groq.com/keys を開き、"
        "ログイン →『Create API Key』で作成し、gsk_ で始まる文字列をコピーしてここに貼り付け。"
    )
    script = (
        f'display dialog "{msg}" default answer "" with hidden answer '
        f'with title "Groq Dictation 初期設定" buttons {{"キャンセル", "保存"}} '
        f'default button "保存"'
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=300
        )
    except Exception as e:
        logger.error("入力ダイアログの表示に失敗: %s", e)
        return None
    if result.returncode != 0:
        return None  # キャンセル
    # 出力例: "button returned:保存, text returned:gsk_xxx"
    out = result.stdout.strip()
    marker = "text returned:"
    if marker in out:
        return out.split(marker, 1)[1].strip()
    return None


def open_groq_keys_page() -> None:
    url = "https://console.groq.com/keys"
    try:
        if IS_MAC:
            subprocess.Popen(["open", url])
        elif platform.system() == "Windows":
            subprocess.Popen(["cmd", "/c", "start", "", url], shell=False)
        else:
            subprocess.Popen(["xdg-open", url])
    except Exception:
        pass


def show_message(text: str, title: str = "Groq Dictation") -> None:
    if not IS_MAC:
        print(text)
        return
    safe = text.replace('"', "'")
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display dialog "{safe}" with title "{title}" buttons {{"OK"}} default button "OK"'],
            capture_output=True, text=True, timeout=120,
        )
    except Exception:
        print(text)


def ensure_key_interactive(max_tries: int = 3) -> str | None:
    """キーが無ければダイアログで取得・検証・保存する。確定したキーを返す。"""
    existing = load_user_key()
    if not is_placeholder(existing):
        return existing

    for _ in range(max_tries):
        key = prompt_for_key_dialog()
        if key is None:
            return None  # ユーザーがキャンセル
        ok, message = validate_key(key)
        if ok:
            save_user_key(key)
            show_message("APIキーを保存しました。これで使えます。", "設定完了")
            return key
        show_message(f"{message}\\n\\nもう一度入力してください。", "キーを確認してください")
    return None


def reconfigure(max_tries: int = 3) -> str | None:
    """既存キーの有無に関わらず、必ず入力ダイアログを出して設定し直す。"""
    for _ in range(max_tries):
        key = prompt_for_key_dialog()
        if key is None:
            return None
        ok, message = validate_key(key)
        if ok:
            save_user_key(key)
            show_message("APIキーを更新しました。", "設定完了")
            return key
        show_message(f"{message}\\n\\nもう一度入力してください。", "キーを確認してください")
    return None


if __name__ == "__main__":
    # 『キー設定.command』から呼ばれる: いつでもキーを設定し直す
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    open_groq_keys_page()
    result = reconfigure()
    print("設定完了" if result else "設定はキャンセルされました。")
