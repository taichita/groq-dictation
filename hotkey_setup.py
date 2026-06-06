"""ショートカット(ホットキー)を各自が設定する。

非エンジニアでも選べるよう、よく使う組み合わせをメニューで提示する。
上級者は自分でpynput形式を入力もできる。選んだ値は検証してから保存する。

保存先: ユーザー設定の HOTKEY（user_settings 経由）。
"""

import logging
import platform
import subprocess

from pynput import keyboard

import user_settings

logger = logging.getLogger(__name__)
IS_MAC = platform.system() == "Darwin"

# (画面に出す名前, pynput形式)
PRESETS: list[tuple[str, str]] = [
    ("Control + Shift + Space（標準）", "<ctrl>+<shift>+<space>"),
    ("Command + Shift + Space", "<cmd>+<shift>+<space>"),
    ("Command + Shift + D", "<cmd>+<shift>+d"),
    ("Control + Option + Space", "<ctrl>+<alt>+<space>"),
    ("Option + Space", "<alt>+<space>"),
    ("F5 キー", "<f5>"),
]
CUSTOM_LABEL = "自分で入力する（上級者）"


def validate_spec(spec: str) -> bool:
    try:
        keyboard.HotKey.parse(spec)
        return True
    except Exception:
        return False


def _osascript(args: list[str]) -> tuple[int, str]:
    try:
        r = subprocess.run(["osascript", *args], capture_output=True, text=True, timeout=300)
        return r.returncode, r.stdout.strip()
    except Exception as e:
        logger.error("ダイアログ表示に失敗: %s", e)
        return 1, ""


def _choose_mac(current_spec: str) -> str | None:
    labels = [label for label, _ in PRESETS] + [CUSTOM_LABEL]
    apple_list = "{" + ", ".join(f'"{l}"' for l in labels) + "}"
    # 現在値に一致するプリセットを既定選択に
    default_label = next((l for l, s in PRESETS if s == current_spec), labels[0])
    script = (
        f'choose from list {apple_list} with title "ショートカットの設定" '
        f'with prompt "音声入力を開始/停止するショートカットを選んでください" '
        f'default items {{"{default_label}"}}'
    )
    code, out = _osascript(["-e", script])
    if code != 0 or out in ("", "false"):
        return None  # キャンセル
    if out == CUSTOM_LABEL:
        return _custom_input_mac()
    for label, spec in PRESETS:
        if label == out:
            return spec
    return None


def _custom_input_mac() -> str | None:
    msg = (
        "pynput形式で入力してください。\\n"
        "例: <ctrl>+<shift>+<space>  /  <cmd>+<shift>+d  /  <f5>\\n"
        "修飾キー: <ctrl> <cmd> <alt> <shift>  特殊キー: <space> <f5> など"
    )
    script = (
        f'display dialog "{msg}" default answer "<ctrl>+<shift>+<space>" '
        f'with title "ショートカット（自分で入力）" buttons {{"キャンセル", "保存"}} '
        f'default button "保存"'
    )
    code, out = _osascript(["-e", script])
    if code != 0:
        return None
    marker = "text returned:"
    if marker in out:
        return out.split(marker, 1)[1].strip()
    return None


def _choose_console(current_spec: str) -> str | None:
    print("ショートカットを選んでください:")
    for i, (label, _) in enumerate(PRESETS, 1):
        print(f"  {i}) {label}")
    print(f"  {len(PRESETS)+1}) {CUSTOM_LABEL}")
    try:
        choice = input("番号: ").strip()
    except EOFError:
        return None
    if not choice.isdigit():
        return None
    n = int(choice)
    if 1 <= n <= len(PRESETS):
        return PRESETS[n - 1][1]
    if n == len(PRESETS) + 1:
        try:
            return input("pynput形式 (例 <ctrl>+<shift>+<space>): ").strip()
        except EOFError:
            return None
    return None


def set_hotkey_interactive() -> str | None:
    current = user_settings.get("HOTKEY", "<ctrl>+<shift>+<space>")
    for _ in range(3):
        spec = _choose_mac(current) if IS_MAC else _choose_console(current)
        if spec is None:
            return None
        if validate_spec(spec):
            user_settings.set("HOTKEY", spec)
            logger.info("ショートカットを保存しました: %s", spec)
            if IS_MAC:
                _osascript(["-e",
                    f'display dialog "ショートカットを設定しました:\\n{spec}\\n\\n'
                    f'（自動起動が有効なら、反映には一度ログインし直すか『自動起動オン』を再実行）" '
                    f'with title "設定完了" buttons {{"OK"}} default button "OK"'])
            return spec
        if IS_MAC:
            _osascript(["-e",
                'display dialog "その形式は認識できませんでした。もう一度選んでください。" '
                'with title "もう一度" buttons {"OK"} default button "OK"'])
        else:
            print("認識できない形式です。もう一度。")
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    result = set_hotkey_interactive()
    print(f"設定: {result}" if result else "設定はキャンセルされました。")
