"""Superwhisper の過去の文字起こし履歴を、音声入力ログ(日次Markdown)へ取り込む。

~/Documents/superwhisper/recordings/*/meta.json の result(本文) と datetime を読み、
TRANSCRIPT_DIR の日次ファイルへマージする（同じ時刻・本文は重複させない）。
一度きりのバックフィル用。何度実行しても重複しない。

使い方:
    python import_superwhisper.py            # 取り込み先は config の TRANSCRIPT_DIR
    python import_superwhisper.py <フォルダ>  # 取り込み先を明示
"""

import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from config import AppConfig
from transcript_log import machine_name

SW_DIR = Path.home() / "Documents" / "superwhisper" / "recordings"
BULLET_RE = re.compile(r"^- (\d{2}:\d{2})\s+(.*)$")


def collect() -> dict[str, list[tuple[str, str]]]:
    """date_str -> [(HH:MM, text)] を返す。"""
    by_date: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for meta in SW_DIR.glob("*/meta.json"):
        try:
            d = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            continue
        text = " ".join((d.get("result") or "").split())
        dt_raw = d.get("datetime")
        if not text or not dt_raw:
            continue
        try:
            dt = datetime.fromisoformat(dt_raw)
        except Exception:
            continue
        by_date[dt.strftime("%Y-%m-%d")].append((dt.strftime("%H:%M"), text))
    return by_date


def parse_existing(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = BULLET_RE.match(line.strip())
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def main() -> int:
    if len(sys.argv) > 1:
        out_dir = Path(sys.argv[1]).expanduser()
    else:
        cfg = AppConfig.load()
        if not cfg.transcript_dir:
            print("TRANSCRIPT_DIR が未設定です。先に記録先を設定してください。")
            return 1
        out_dir = Path(cfg.transcript_dir).expanduser()

    # Superwhisper履歴はこのMacのデータなので、PCごとサブフォルダ(mac/)に入れる
    out_dir = out_dir / machine_name()

    if not SW_DIR.exists():
        print(f"Superwhisper履歴が見つかりません: {SW_DIR}")
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    by_date = collect()
    total_added = 0
    days = 0

    for date_str, sw_entries in sorted(by_date.items()):
        path = out_dir / f"{date_str}.md"
        existing = parse_existing(path)
        seen = set(existing)
        merged = list(existing)
        added_here = 0
        for entry in sw_entries:
            if entry not in seen:
                seen.add(entry)
                merged.append(entry)
                added_here += 1
        if added_here == 0:
            continue
        merged.sort(key=lambda e: e[0])  # 時刻順
        lines = [f"## {date_str} の音声入力", ""]
        lines += [f"- {t}  {txt}" for t, txt in merged]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        total_added += added_here
        days += 1
        print(f"  {date_str}: +{added_here} 件")

    print(f"\n✅ 取り込み完了: {total_added} 件 / {days} 日分 → {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
