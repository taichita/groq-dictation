# Groq Dictation

Superwhisper の代替として、**Groq Speech-to-Text だけ**を使う高速音声入力アプリ（自分用 MVP）。
ChatGPT / Claude / Codex などのAIチャット欄への音声入力が主用途。

> **方針**: LLM後処理は一切しない。要約・言い換え・敬語化・整形をせず、話した内容をそのまま貼り付ける。
> 誤変換の修正は `replacement.json`（ローカル置換辞書）だけで行う。

---

## 何ができるか

ホットキー（既定 `右Ctrl + Alt`）を押す → 話す → もう一度押す → 文字起こし結果が今フォーカスしている入力欄に自動で貼り付けられる。録音中は **画面右下に赤い丸**が点灯します（**音は鳴りません**）。PC起動時に自動で常駐するので、いつでもホットキーひとつで使えます。

```
ホットキー → 録音 → Groqへ送信 → 置換辞書で誤変換修正 → クリップボード → 自動貼り付け
```

---

## セットアップ（初回のみ）

### 1. 必要なもの

- Python 3.13（このプロジェクトは 3.13 でセットアップ済み）
- portaudio（録音ライブラリの土台。`brew install portaudio` 済み）
- Groq APIキー（**まだ未設定。下記2で設定が必要**）

### 2. Groq APIキーを設定する ← 最初にやること

1. https://console.groq.com/keys を開く
2. ログイン（Googleアカウント等でOK）して「Create API Key」でキーを作成
3. 作成された文字列（`gsk_...`）をコピー
4. リポジトリ直下の `.env.example` を `.env` という名前でコピーし、開いて次の行を書き換える

   ```
   GROQ_API_KEY=ここに gsk_... を貼り付け
   ```

   （または `python -m key_setup` ／「キー設定」ランチャーでも設定できます）

### 3. macOS の権限を2つ付与する

「システム設定 > プライバシーとセキュリティ」で、**このアプリを動かすターミナル**（標準のターミナル.app か iTerm 等）を次の2つに追加・ON にする。

| 権限 | 用途 | これが無いと |
|---|---|---|
| **マイク** | 録音 | 録音できない／無音になる |
| **アクセシビリティ** | 自動貼り付け（Cmd+V送信） | クリップボードには入るが貼り付けされない |

> 権限を変えた後は **ターミナルを一度終了して開き直す**と確実です。

---

## 使い方

### まず自己診断（おすすめ）

不安定の原因を切り分けられます。設定→マイク→3秒テスト録音→Groq送信を順に確認します。

```bash
cd ~/groq-dictation
source .venv/bin/activate
python check.py
```

「🎉 すべて正常です」と出れば準備完了。

### 本番起動

```bash
cd ~/groq-dictation
./run.sh
```

または

```bash
cd ~/groq-dictation
source .venv/bin/activate
python app.py
```

起動したら:

1. ChatGPT / Claude などの入力欄をクリックしてフォーカス
2. `右Ctrl + Alt` を押す（録音開始。**画面右下に赤い丸**が点灯）
3. 話す
4. もう一度 `右Ctrl + Alt`（録音停止 → 送信 → 自動貼り付け。赤い丸が消える）
5. 終了は `Ctrl + C`

状態は **画面右下の赤い丸**で分かります（録音中だけ点灯）。**音は既定で鳴りません**。
耳でも確認したい場合は `.env` で `SOUND_CUE=true` にすると音フィードバックが出ます。

---

## 設定（.env）

| 項目 | 既定 | 説明 |
|---|---|---|
| `GROQ_API_KEY` | （必須） | Groq の APIキー |
| `GROQ_MODEL` | whisper-large-v3-turbo | 速度重視のモデル |
| `LANGUAGE` | ja | 認識言語 |
| `HOTKEY` | `<ctrl_r>+<alt>` | 録音開始/停止キー（既定は **右Ctrl + Alt**） |
| `AUTO_PASTE` | true | 自動貼り付けのON/OFF |
| `MIN_RECORD_SEC` | 0.4 | これより短い録音は送信しない（誤爆対策） |
| `MAX_RECORD_SEC` | 120 | これを超えたら自動停止（巨大ファイル対策） |
| `REQUEST_TIMEOUT` | 60 | Groq通信のタイムアウト秒 |
| `MAX_RETRIES` | 2 | タイムアウト/5xx時のリトライ回数 |
| `SOUND_CUE` | **false** | 録音状態の音フィードバック（既定オフ＝音なし） |
| `OVERLAY_ICON` | true | 録音中に **画面右下へ赤い丸**を表示 |
| `TRAY_ICON` | true | 通知領域に状態アイコンを表示 |

### ホットキーを変えたいとき

`.env` の `HOTKEY` を pynput 形式で書く。既定は `<ctrl_r>+<alt>`（右Ctrl + Alt）。例:

- `<ctrl_r>+<alt>`（既定。右Ctrl + Alt。カーソルが入力欄にあっても支障が出にくい）
- `<cmd>+<shift>+d`
- `<f8>`（単キー）
- `<ctrl>+<alt>+space`

---

## 誤変換を直したいとき（置換辞書）

`replacement.json` に「間違って出る文字列」→「正しい文字列」を足すだけ。

```json
{
  "グローブ": "Groq",
  "チャットGPT": "ChatGPT"
}
```

単純置換のみ。文脈判断やLLMは使いません。編集後はアプリを再起動。

---

## よくあるエラーと対処

| 症状 | 原因 | 対処 |
|---|---|---|
| `GROQ_API_KEYがサンプルのまま` | キー未設定 | `.env` に本物のキーを書く |
| `401 Unauthorized` | キーが間違い | Groq Console でキーを再確認/再発行 |
| `429 Rate Limit` | 使いすぎ | 少し待って再実行 |
| `413 Payload Too Large` | 録音が長すぎ | 録音を短く（`MAX_RECORD_SEC` 調整） |
| `マイクを開けませんでした` | マイク権限なし | システム設定 > マイク でターミナル許可 |
| クリップボードには入るが貼られない | アクセシビリティ権限なし | システム設定 > アクセシビリティ でターミナル許可 |
| 録音が短すぎますと出る | 押してすぐ離した/無音 | 少し話してから停止 |

失敗の詳細は `groq_dictation.log` に残ります（原因の後追い用）。

---

## ファイル構成

```
groq-dictation/
├─ app.py             起動・ホットキー・全体制御（スレッド分離で安定化）
├─ audio_recorder.py  マイク録音・wav保存
├─ groq_client.py     Groq送信（リトライ/ステータス別エラー）
├─ replacement.py     置換辞書による単純置換
├─ clipboard_paste.py コピー＆自動貼り付け（macはosascript）
├─ sound_cue.py       録音状態の音フィードバック
├─ config.py          .env 読み込み・設定一元化
├─ check.py           自己診断ツール
├─ replacement.json   誤変換 置換辞書
├─ .env               APIキー等（Git管理しない）
├─ .env.example       設定見本
├─ requirements.txt   依存ライブラリ
└─ run.sh             起動スクリプト
```

---

## 社内配布（フォルダ配布版）

非エンジニアの同僚にも配れるパッケージを同梱しています。

- 配布物: `GroqDictation_配布版.zip`（`はじめに.command` を作り直すと再生成）
- 同僚に必要なのは **Python 3 だけ**。録音部品(portaudio)は sounddevice に同梱(universal binary)されるため **Homebrew 不要**。各自が自分のMacで環境を作るので **Apple Silicon / Intel を自動で吸収**します。
- APIキーは **各自が初回ダイアログで入力** → 本人のMacの `~/Library/Application Support/GroqDictation/` に保存（アプリ本体・zipにキーは含まれない）。

### 同僚の手順

1. zip を解凍してフォルダを置く
2. `はじめに.command` を **右クリック →「開く」**（初回だけ。署名なしのため）→ 自動で準備＋キー入力＋権限許可
3. 以後は `起動.command` をダブルクリック

詳細は同梱の `使い方.html`（同僚向けガイド）を参照。

### キー解決の優先順位

1. 環境変数 `GROQ_API_KEY`
2. ユーザー設定 `~/Library/Application Support/GroqDictation/config.env`（各自のキー／配布時の本命）
3. プロジェクト直下の `.env`

`キー設定.command`（= `python -m key_setup`）でいつでも再設定できます。

## Windows での使い方

Windows PC では:

1. このリポジトリを clone（または「Code → Download ZIP」でダウンロードして解凍）する
2. フォルダを開き、**`はじめに.bat` をダブルクリック**
   - Python が無ければ案内ページから導入（インストール時「Add python.exe to PATH」にチェック）→ 再実行
   - 自動で venv 作成・部品導入・APIキー入力・ショートカット設定・自動起動登録
3. 以後はログイン時に自動常駐。設定したショートカットで音声入力

Windows ではマイク以外の特別な権限は不要。自動起動はスタートアップフォルダの `GroqDictation.vbs`（`pythonw` で画面を出さず常駐）。ショートカットは各自 `ショートカット設定.bat` で設定。

## 自動起動（PC起動時に常時オン）

既定では **PC を起動すると自動でバックグラウンド常駐**します（画面には出ません）。常駐していれば、いつでもホットキー（右Ctrl + Alt）だけで音声入力できます。

- **Windows**: `はじめに.bat` がスタートアップに `GroqDictation.vbs`（`pythonw` で画面を出さず常駐）を登録。オフにするには `自動起動オフ.bat`、オンに戻すには `自動起動オン.bat`。
- **macOS**: `自動起動オン.command` で登録 / `自動起動オフ.command` で解除。

## 文字起こしログ

文字起こしは手元の `音声入力ログ/` に保存されます。個人的な発話内容なので **`.gitignore` 済み（GitHub には上がりません）**。

## 切り分けメモ

Superwhisper では失敗するのに、このアプリ（または下記 curl）で成功するなら、Groq API ではなく Superwhisper 側の問題の可能性が高い。

```bash
curl https://api.groq.com/openai/v1/audio/transcriptions \
  -H "Authorization: Bearer $GROQ_API_KEY" \
  -F "file=@test.wav" \
  -F "model=whisper-large-v3-turbo" \
  -F "language=ja" \
  -F "response_format=text" \
  -F "temperature=0"
```
