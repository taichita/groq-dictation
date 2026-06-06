"""画面の隅に出す、ごく小さな録音インジケータ（常に最前面）。

通知領域(トレイ)のアイコンは Windows が既定で「隠れているアイコン」へ入れてしまい、
録音中かどうかが一目で分からない。そこで、録音中・変換中だけ画面右下に小さな丸を
最前面で表示する。待機中は完全に透明＝何も見えないので邪魔にならない。

tkinter(標準同梱)だけで実装。使えない環境では静かに無効化する(落ちない)。
"""

import logging
import threading

logger = logging.getLogger(__name__)

# 透明色（この色で塗った部分は画面に出ない＝クリックもすり抜ける）
_TRANSPARENT = "#010101"
_COLORS = {
    "recording": "#e12d2d",   # 録音中: 赤
    "processing": "#eba523",  # 変換中: オレンジ
}


class OverlayIndicator:
    def __init__(self, enabled: bool = True, size: int = 16):
        self.enabled = enabled
        self.size = size
        self._state = "idle"
        self._root = None
        self._canvas = None
        self._dot = None

    def start(self) -> None:
        if not self.enabled:
            return
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            import tkinter as tk
        except Exception as e:
            logger.info("画面インジケータは使えません(無視します): %s", e)
            self.enabled = False
            return
        try:
            root = tk.Tk()
            self._root = root
            root.overrideredirect(True)            # 枠・タイトルバー無し
            root.attributes("-topmost", True)       # 常に最前面
            try:
                root.attributes("-toolwindow", True)  # タスクバーに出さない
            except Exception:
                pass
            try:
                root.attributes("-transparentcolor", _TRANSPARENT)
            except Exception:
                pass
            s = self.size
            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            # 右下、タスクバーの少し上あたり
            x = sw - s - 14
            y = sh - s - 60
            root.geometry(f"{s}x{s}+{x}+{y}")
            root.configure(bg=_TRANSPARENT)
            c = tk.Canvas(root, width=s, height=s, bg=_TRANSPARENT,
                          highlightthickness=0, bd=0)
            c.pack()
            self._canvas = c
            self._dot = c.create_oval(1, 1, s - 1, s - 1,
                                      fill=_TRANSPARENT, outline="")
            root.after(100, self._tick)
            root.mainloop()
        except Exception as e:
            logger.info("画面インジケータの起動に失敗(無視します): %s", e)
            self.enabled = False

    def _tick(self) -> None:
        if self._root is None:
            return
        try:
            fill = _COLORS.get(self._state, _TRANSPARENT)
            self._canvas.itemconfig(self._dot, fill=fill)
            self._root.after(100, self._tick)
        except Exception:
            pass

    def set_state(self, state: str) -> None:
        # 別スレッドから呼ばれる。属性を書くだけ（描画は _tick が反映）。
        self._state = state

    def stop(self) -> None:
        if self._root is not None:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass
