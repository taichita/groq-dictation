"""通知領域(画面右下のトレイ)に状態を示す小さな丸アイコンを出す。

GUIの無い常駐アプリでは「今録音中なのか」が分かりにくい。音の代わりに、
トレイの丸の色で状態を一目で示す:
  待機中=グレー / 録音中=赤 / 変換中=オレンジ

pystray・Pillow が無い、またはトレイが使えない環境では静かに無効化する(落ちない)。
"""

import logging
import threading

logger = logging.getLogger(__name__)

# (R, G, B, A)
_COLORS = {
    "idle": (140, 140, 140, 255),       # 待機: グレー
    "recording": (225, 45, 45, 255),    # 録音中: 赤
    "processing": (235, 165, 35, 255),  # 変換中: オレンジ
}
_LABELS = {
    "idle": "待機中（右Ctrl+左Altで録音）",
    "recording": "● 録音中",
    "processing": "変換中…",
}


class TrayIndicator:
    def __init__(self, enabled: bool = True, on_quit=None):
        self.enabled = enabled
        self._icon = None
        self._on_quit = on_quit
        self._pystray = None
        self._Image = None
        self._ImageDraw = None
        if not enabled:
            return
        try:
            import pystray
            from PIL import Image, ImageDraw
            self._pystray = pystray
            self._Image = Image
            self._ImageDraw = ImageDraw
        except Exception as e:
            logger.info("トレイアイコンは使えません(無視します): %s", e)
            self.enabled = False

    def _image(self, state: str):
        Image, ImageDraw = self._Image, self._ImageDraw
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        color = _COLORS.get(state, _COLORS["idle"])
        # 中央の丸。録音中は少し大きくして目立たせる。
        r = 23 if state == "recording" else 19
        c = 32
        d.ellipse((c - r, c - r, c + r, c + r), fill=color)
        return img

    def start(self) -> None:
        if not self.enabled:
            return

        def _run():
            try:
                menu = self._pystray.Menu(
                    self._pystray.MenuItem("終了", self._quit)
                )
                self._icon = self._pystray.Icon(
                    "groq_dictation",
                    self._image("idle"),
                    "Groq Dictation — " + _LABELS["idle"],
                    menu,
                )
                self._icon.run()
            except Exception as e:
                logger.info("トレイ起動に失敗(無視します): %s", e)
                self.enabled = False

        threading.Thread(target=_run, daemon=True).start()

    def set_state(self, state: str) -> None:
        if not self.enabled or self._icon is None:
            return
        try:
            self._icon.icon = self._image(state)
            self._icon.title = "Groq Dictation — " + _LABELS.get(state, "")
        except Exception:
            pass

    def _quit(self, icon, item) -> None:
        try:
            if self._on_quit:
                self._on_quit()
        finally:
            try:
                icon.stop()
            except Exception:
                pass

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
