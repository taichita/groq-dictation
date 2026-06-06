#!/bin/bash
# 録音開始/停止のショートカットを各自で設定する。
cd "$(dirname "$0")" || exit 1
source .venv/bin/activate 2>/dev/null
clear
echo "ショートカット（録音開始/停止キー）を設定します..."
python -m hotkey_setup
echo ""
echo "※ 自動起動で常駐中の場合は、反映のため自動で再起動します..."
python autostart.py restart 2>/dev/null || true
echo ""
read -r -p "Enterで閉じます..." _
