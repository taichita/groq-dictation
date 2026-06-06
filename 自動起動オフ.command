#!/bin/bash
# 自動起動を解除し、常駐を停止する。
cd "$(dirname "$0")" || exit 1
source .venv/bin/activate 2>/dev/null
clear
echo "自動起動を解除します..."
python autostart.py uninstall
echo ""
read -r -p "Enterで閉じます..." _
