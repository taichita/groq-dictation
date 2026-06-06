"""録音開始/停止/完了の音のフィードバック(macOS)。

GUIが無いターミナル常駐アプリでは「今録音中なのか」が分かりにくく、
これが体感上の不安定さ(押したつもりが録れていない等)につながる。
macOS標準のシステム音を afplay で鳴らして状態を耳で分かるようにする。
非macOS・音声ファイルが無い環境では静かに何もしない(落ちない)。
"""

import logging
import platform
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

IS_MAC = platform.system() == "Darwin"
IS_WIN = platform.system() == "Windows"

# macOS標準のシステムサウンド
_SOUNDS = {
    "start": "/System/Library/Sounds/Tink.aiff",    # 録音開始
    "stop": "/System/Library/Sounds/Pop.aiff",       # 録音停止(送信開始)
    "done": "/System/Library/Sounds/Glass.aiff",     # 貼り付け完了
    "error": "/System/Library/Sounds/Basso.aiff",    # 失敗
}

# Windows: システムの「警告/エラー」音(MessageBeep)はエラーに聞こえて紛らわしいので、
# winsound.Beep で澄んだ短い電子音を鳴らす。(周波数Hz, 長さms) の並び。
_WIN_TONES = {
    "start": [(880, 90)],              # 録音開始: 高めの短い1音
    "stop": [(620, 90)],               # 停止(送信開始): 少し低い1音
    "done": [(988, 70), (1319, 90)],   # 完了: 軽い上昇2音
    "error": [(400, 200)],             # 失敗: 低い1音(明確に区別)
}


_enabled = True


def set_enabled(enabled: bool) -> None:
    """設定(SOUND_CUE)で音のオン/オフを切り替える。play() が参照する。"""
    global _enabled
    _enabled = bool(enabled)


def play(kind: str) -> None:
    if not _enabled:
        return
    try:
        if IS_MAC:
            path = _SOUNDS.get(kind)
            if not path or not Path(path).exists():
                return
            # 非ブロッキングで鳴らす(処理を待たせない)
            subprocess.Popen(
                ["afplay", path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif IS_WIN:
            import winsound

            for freq, dur in _WIN_TONES.get(kind, []):
                winsound.Beep(freq, dur)
    except Exception as e:
        logger.debug("サウンド再生に失敗(無視します): %s", e)
