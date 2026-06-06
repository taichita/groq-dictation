"""ログイン時の自動起動。macOS は LaunchAgent、Windows はスタートアップ。

PC起動(ログイン)と同時にアプリを常駐させ、ホットキー1発で使えるようにする。
ウィンドウは出さない（headless）。

使い方:
    python autostart.py install     # 自動起動を有効化＋今すぐ起動
    python autostart.py uninstall   # 自動起動を無効化＋停止
    python autostart.py restart     # 設定変更を反映して再起動
    python autostart.py status      # 状態を表示
"""

import os
import platform
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LABEL = "com.groqdictation.agent"
PYTHON = sys.executable
APP_PY = str(BASE_DIR / "app.py")
OUT_LOG = str(BASE_DIR / "autostart.out.log")
ERR_LOG = str(BASE_DIR / "autostart.err.log")

IS_MAC = platform.system() == "Darwin"
IS_WIN = platform.system() == "Windows"


# ===================== macOS (LaunchAgent) =====================
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>{app}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{workdir}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>ProcessType</key>
    <string>Interactive</string>
    <key>StandardOutPath</key>
    <string>{out_log}</string>
    <key>StandardErrorPath</key>
    <string>{err_log}</string>
</dict>
</plist>
"""


def _domain() -> str:
    return f"gui/{os.getuid()}"


def _run(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def _mac_install() -> None:
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(
        PLIST_TEMPLATE.format(
            label=LABEL, python=PYTHON, app=APP_PY,
            workdir=str(BASE_DIR), out_log=OUT_LOG, err_log=ERR_LOG,
        ),
        encoding="utf-8",
    )
    print(f"・自動起動の設定を書き込みました: {PLIST_PATH}")
    _run(["launchctl", "bootout", f"{_domain()}/{LABEL}"])
    code, out = _run(["launchctl", "bootstrap", _domain(), str(PLIST_PATH)])
    if code != 0:
        _run(["launchctl", "unload", str(PLIST_PATH)])
        code, out = _run(["launchctl", "load", "-w", str(PLIST_PATH)])
    print("✅ 自動起動を有効化しました（次回ログインから自動）。" if code == 0
          else f"⚠ 登録コマンド失敗: {out}")
    print(f"   使用Python: {PYTHON}")


def _mac_uninstall() -> None:
    _run(["launchctl", "bootout", f"{_domain()}/{LABEL}"]) or _run(["launchctl", "unload", str(PLIST_PATH)])
    if PLIST_PATH.exists():
        PLIST_PATH.unlink()
    print("✅ 自動起動を無効化し、常駐を停止しました。")


def _mac_restart() -> None:
    if not PLIST_PATH.exists():
        print("自動起動が未設定です。先に install を実行してください。")
        return
    code, _ = _run(["launchctl", "kickstart", "-k", f"{_domain()}/{LABEL}"])
    if code != 0:
        _mac_uninstall(); _mac_install()
    else:
        print("✅ 設定を反映して再起動しました。")


def _mac_status() -> None:
    print(f"plist: {PLIST_PATH} ({'あり' if PLIST_PATH.exists() else 'なし'})")
    code, out = _run(["launchctl", "print", f"{_domain()}/{LABEL}"])
    print("状態: " + ("登録あり/稼働中" if code == 0 else "未登録（停止中）"))


# ===================== Windows (Startup フォルダ) =====================
def _win_startup_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _win_vbs_path() -> Path:
    return _win_startup_dir() / "GroqDictation.vbs"


def _win_pythonw() -> str:
    # venv の pythonw.exe（コンソールを出さずに常駐するため）
    p = Path(PYTHON)
    cand = p.with_name("pythonw.exe")
    return str(cand if cand.exists() else p)


def _win_install() -> None:
    startup = _win_startup_dir()
    startup.mkdir(parents=True, exist_ok=True)
    pyw = _win_pythonw()
    vbs = (
        'Set WshShell = CreateObject("WScript.Shell")\r\n'
        f'WshShell.CurrentDirectory = "{BASE_DIR}"\r\n'
        f'WshShell.Run """{pyw}"" ""{APP_PY}""", 0, False\r\n'
    )
    _win_vbs_path().write_text(vbs, encoding="utf-8")
    print(f"・スタートアップに登録しました: {_win_vbs_path()}")
    # 今すぐ起動
    try:
        subprocess.Popen(
            ["wscript.exe", str(_win_vbs_path())],
            cwd=str(BASE_DIR),
        )
    except Exception as e:
        print(f"⚠ 起動に失敗: {e}")
    print("✅ 自動起動を有効化しました（次回ログインから自動）。")
    print(f"   使用Python: {pyw}")


def _win_uninstall() -> None:
    if _win_vbs_path().exists():
        _win_vbs_path().unlink()
    # 稼働中プロセスの停止は試行（失敗は無視）
    subprocess.run(["taskkill", "/F", "/IM", "pythonw.exe"], capture_output=True)
    print("✅ 自動起動を無効化しました（次回ログインから起動しません）。")


def _win_restart() -> None:
    _win_uninstall()
    _win_install()


def _win_status() -> None:
    print(f"startup: {_win_vbs_path()} ({'あり' if _win_vbs_path().exists() else 'なし'})")


# ===================== dispatch =====================
def install() -> None:
    (_mac_install if IS_MAC else _win_install if IS_WIN else _unsupported)()


def uninstall() -> None:
    (_mac_uninstall if IS_MAC else _win_uninstall if IS_WIN else _unsupported)()


def restart() -> None:
    (_mac_restart if IS_MAC else _win_restart if IS_WIN else _unsupported)()


def status() -> None:
    (_mac_status if IS_MAC else _win_status if IS_WIN else _unsupported)()


def _unsupported() -> None:
    print("このOSの自動起動は未対応です（macOS / Windows のみ）。")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"install": install, "uninstall": uninstall,
     "restart": restart, "status": status}.get(action, status)()
