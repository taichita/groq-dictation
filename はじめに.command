#!/bin/bash
# Groq Dictation かんたんセットアップ（配布版・最初にこれを実行）。
# やること: Python確認 → 部品インストール → APIキー設定 → 権限の許可。
# ダウンロード直後は「右クリック → 開く」で起動してください（初回のみ）。
set -u
cd "$(dirname "$0")" || exit 1
clear

# 同じフォルダ内の他ファイルのGatekeeper隔離を解除（このファイルは既に許可されて起動中）
xattr -dr com.apple.quarantine . 2>/dev/null || true

echo "============================================================"
echo "   Groq Dictation かんたんセットアップ"
echo "============================================================"
echo ""

# --- 1) Python 3.10+ を探す ---
find_python() {
  local cands p ver maj min
  cands="$(command -v python3 2>/dev/null) /opt/homebrew/bin/python3 /usr/local/bin/python3"
  for p in $cands /Library/Frameworks/Python.framework/Versions/*/bin/python3; do
    [ -n "$p" ] && [ -x "$p" ] || continue
    ver=$("$p" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null) || continue
    maj=${ver%%.*}; min=${ver##*.}
    if [ "${maj:-0}" -eq 3 ] && [ "${min:-0}" -ge 10 ]; then
      echo "$p"; return 0
    fi
  done
  return 1
}

PY="$(find_python || true)"
if [ -z "${PY:-}" ]; then
  echo "❌ Python が見つかりません（または古いです）。"
  echo ""
  echo "  1) これから開くページで Python をダウンロードしてインストール"
  echo "  2) インストール後、もう一度この『はじめに.command』を開いてください"
  echo ""
  open "https://www.python.org/downloads/macos/"
  read -r -p "Enterで閉じます..." _
  exit 1
fi
echo "✅ Python を確認しました: $PY"

# --- 2) 仮想環境 ---
if [ ! -d ".venv" ]; then
  echo "・準備中（仮想環境を作成）..."
  "$PY" -m venv .venv || { echo "❌ 仮想環境の作成に失敗"; read -r -p "Enter..."; exit 1; }
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# --- 3) 必要な部品 ---
echo "・必要な部品をインストール中（初回は数分かかります。お待ちください）..."
python -m pip install --upgrade pip -q
if ! python -m pip install -r requirements.txt -q; then
  echo "❌ 部品のインストールに失敗しました。ネット接続を確認して、もう一度お試しください。"
  read -r -p "Enter..."; exit 1
fi
echo "✅ 部品の準備ができました（録音部品は同梱のため Homebrew 不要）"

# --- 4) APIキー ---
echo ""
echo "・Groq APIキーを設定します（入力ダイアログが出ます）..."
python -m key_setup || true

# --- 5) 権限（マイク＋アクセシビリティ）---
echo ""
echo "・最後に Mac の許可を行います。"
echo "  [マイク] ダイアログが出たら『許可』を押してください..."
python - <<'PY'
import sounddevice as sd, time
try:
    s = sd.InputStream(samplerate=16000, channels=1, dtype='float32')
    s.start(); time.sleep(1.5); s.stop(); s.close()
except Exception as e:
    print("   （マイク初期化メッセージ）", e)
PY
sleep 1
echo "  [アクセシビリティ] 設定画面で『ターミナル』をオンにしてください..."
osascript -e 'tell application "System Events" to key code 123' 2>/dev/null || true
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility" 2>/dev/null || true

echo ""
echo "============================================================"
echo " 🎉 セットアップ完了です！"
echo "  これからは『起動.command』をダブルクリックで使えます。"
echo "  使い方:  入力欄をクリック → Ctrl+Shift+Space で録音 → もう一度で停止＆貼り付け"
echo "============================================================"
read -r -p "Enterで閉じます..." _
