"""クリップボードコピーと自動貼り付け。

安定化ポイント:
- macOS では pyautogui ではなく osascript(System Events) で Cmd+V を送る。
  pyautogui より取りこぼしが少なく、依存も軽い。
- 貼り付けの成否を bool で返し、失敗時に呼び出し側がログを出せるようにする。
- コピーと貼り付けを分離(copy は基本失敗しない / paste は権限で失敗しうる)。
"""

import logging
import platform
import subprocess
import time

import pyperclip

logger = logging.getLogger(__name__)

IS_MAC = platform.system() == "Darwin"


def copy_to_clipboard(text: str) -> bool:
    try:
        pyperclip.copy(text)
        return True
    except Exception as e:  # pyperclip.PyperclipException など
        logger.error("クリップボードへのコピーに失敗しました: %s", e)
        return False


def paste() -> bool:
    """フォーカス中のアプリへ貼り付け(Cmd+V / Ctrl+V)。成功なら True。"""
    time.sleep(0.12)  # コピー確定とフォーカス安定を待つ
    if IS_MAC:
        return _paste_mac()
    return _paste_other()


def _paste_mac() -> bool:
    # まず pynput(プロセス内)でCmd+Vを送る。これだと権限はこのPythonに集約され、
    # 自動起動(launchd)でも同じ権限のまま動く。失敗時のみ osascript にフォールバック。
    try:
        from pynput.keyboard import Controller, Key

        kb = Controller()
        with kb.pressed(Key.cmd):
            kb.press("v")
            kb.release("v")
        return True
    except Exception as e:
        logger.warning("pynputでの貼り付けに失敗、osascriptで再試行します: %s", e)

    script = 'tell application "System Events" to keystroke "v" using command down'
    try:
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=5
        )
    except Exception as e:
        logger.error("自動貼り付けの実行に失敗しました: %s", e)
        return False
    if result.returncode != 0:
        logger.error(
            "自動貼り付けに失敗しました。macOSの「システム設定 > プライバシーとセキュリティ > "
            "アクセシビリティ」で許可してください。詳細: %s",
            result.stderr.strip(),
        )
        return False
    return True


def _paste_other() -> bool:
    # Windows/Linux: pynput Controller で Ctrl+V を送る（権限不要）。失敗時 pyautogui。
    try:
        from pynput.keyboard import Controller, Key

        kb = Controller()
        with kb.pressed(Key.ctrl):
            kb.press("v")
            kb.release("v")
        return True
    except Exception as e:
        logger.warning("pynputでの貼り付けに失敗、pyautoguiで再試行します: %s", e)
    try:
        import pyautogui

        pyautogui.hotkey("ctrl", "v")
        return True
    except Exception as e:
        logger.error("自動貼り付けに失敗しました: %s", e)
        return False


def copy_and_paste(text: str, auto_paste: bool = True) -> tuple[bool, bool]:
    """(copied, pasted) を返す。"""
    copied = copy_to_clipboard(text)
    if not auto_paste or not copied:
        return copied, False
    pasted = paste()
    return copied, pasted
