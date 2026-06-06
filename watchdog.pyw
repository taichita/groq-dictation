"""見張り役: Groq Dictation が動いていなければ起動する（Windows用）。

スリープ復帰・クラッシュ・ログイン時など、いろいろなタイミングでこれを呼べば、
落ちていたときだけ静かに起動し直す。既に動いていれば何もしない。
タスクスケジューラから定期＋復帰時に呼ばれる想定。画面に何も出さない(.pyw)。
"""

import ctypes
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PYTHONW = BASE_DIR / ".venv" / "Scripts" / "pythonw.exe"
APP = BASE_DIR / "app.py"
SINGLE_INSTANCE_NAME = "GroqDictationSingleton"

SYNCHRONIZE = 0x00100000
CREATE_NO_WINDOW = 0x08000000


def is_running() -> bool:
    """app.py 側が握っているミューテックスを開けたら起動中とみなす。"""
    h = ctypes.windll.kernel32.OpenMutexW(SYNCHRONIZE, False, SINGLE_INSTANCE_NAME)
    if h:
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    return False


def main() -> int:
    if is_running():
        return 0
    pyw = PYTHONW if PYTHONW.exists() else Path(sys.executable).with_name("pythonw.exe")
    try:
        subprocess.Popen(
            [str(pyw), str(APP)],
            cwd=str(BASE_DIR),
            creationflags=CREATE_NO_WINDOW,
            close_fds=True,
        )
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
