"""macOSの権限(アクセシビリティ/マイク)を明示的に要求するヘルパー。

バックグラウンド(launchd)で動くと許可ダイアログが自動で出ないことがあるため、
公式APIで「許可してください」のプロンプトを出し、対象(このPython)を
プライバシー設定のリストに登録させる。
"""

import logging
import platform

logger = logging.getLogger(__name__)
IS_MAC = platform.system() == "Darwin"


def request_accessibility(prompt: bool = True) -> bool | None:
    """アクセシビリティ権限の有無を返す。prompt=Trueなら許可ダイアログを出す。"""
    if not IS_MAC:
        return None
    try:
        from ApplicationServices import AXIsProcessTrustedWithOptions
        try:
            from ApplicationServices import kAXTrustedCheckOptionPrompt as KEY
        except Exception:
            KEY = "AXTrustedCheckOptionPrompt"
        return bool(AXIsProcessTrustedWithOptions({KEY: bool(prompt)}))
    except Exception as e:
        logger.debug("accessibility確認に失敗: %s", e)
        return None


def is_accessibility_trusted() -> bool | None:
    if not IS_MAC:
        return None
    try:
        from ApplicationServices import AXIsProcessTrusted
        return bool(AXIsProcessTrusted())
    except Exception:
        return None


def is_input_monitoring_trusted() -> bool | None:
    """入力監視(キー入力の監視)権限の有無。macOS 10.15+。"""
    if not IS_MAC:
        return None
    try:
        from Quartz import CGPreflightListenEventAccess
        return bool(CGPreflightListenEventAccess())
    except Exception:
        return None


def request_input_monitoring() -> bool | None:
    """入力監視の許可ダイアログを出し、要求元をリストに登録させる。
    ※グローバルホットキーの受信に必須(macOS 15/26)。"""
    if not IS_MAC:
        return None
    try:
        from Quartz import CGPreflightListenEventAccess, CGRequestListenEventAccess
        if CGPreflightListenEventAccess():
            return True
        CGRequestListenEventAccess()  # プロンプト表示＋リスト登録
        return bool(CGPreflightListenEventAccess())
    except Exception as e:
        logger.debug("入力監視の要求に失敗: %s", e)
        return None


def request_microphone() -> None:
    """マイクを一瞬開いて、マイク許可ダイアログを誘発する。"""
    if not IS_MAC:
        return
    try:
        import time

        import sounddevice as sd

        s = sd.InputStream(samplerate=16000, channels=1, dtype="float32")
        s.start()
        time.sleep(0.8)
        s.stop()
        s.close()
    except Exception as e:
        logger.debug("マイク要求に失敗: %s", e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print("入力監視 現在の状態   :", is_input_monitoring_trusted())
    print("アクセシビリティ 現在 :", is_accessibility_trusted())
    print("")
    print("① 入力監視の許可ダイアログを出します（ホットキー受信に必須）...")
    request_input_monitoring()
    print("② アクセシビリティの許可ダイアログを出します（自動貼り付けに必須）...")
    request_accessibility(prompt=True)
    print("③ マイクの許可も要求します...")
    request_microphone()
    print("")
    print("完了。設定画面の『入力監視』と『アクセシビリティ』で python をオンにしてください。")
