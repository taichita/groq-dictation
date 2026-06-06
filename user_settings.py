"""ユーザーごとの設定（APIキー・ホットキー等）を1ファイルで管理。

保存先: ~/Library/Application Support/GroqDictation/config.env
形式  : KEY=VALUE の単純な行（.env と同じ）。
set() は他の設定行を保持したまま、対象キーだけ更新する。
"""

from pathlib import Path

USER_CONFIG_DIR = Path.home() / "Library" / "Application Support" / "GroqDictation"
USER_CONFIG_FILE = USER_CONFIG_DIR / "config.env"


def load_all() -> dict[str, str]:
    data: dict[str, str] = {}
    if not USER_CONFIG_FILE.exists():
        return data
    try:
        for line in USER_CONFIG_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            data[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return data


def get(name: str, default: str = "") -> str:
    return load_all().get(name, default)


def set(name: str, value: str) -> None:
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = load_all()
    data[name] = value
    lines = [f"{k}={v}" for k, v in data.items()]
    USER_CONFIG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        USER_CONFIG_FILE.chmod(0o600)  # 本人のみ読み書き
    except OSError:
        pass
