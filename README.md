# X 就活情報 自動投稿エージェント

就活に関する有益情報をAIが自動生成し、1日4〜8回X(Twitter)に投稿します。

---

## セットアップ手順

### 1. Pythonライブラリのインストール

```bash
cd x_agent
pip install -r requirements.txt
```

### 2. APIキーの設定

`.env.example` をコピーして `.env` を作成し、各APIキーを記入します。

```bash
cp .env.example .env
```

#### Claude APIキー
- https://console.anthropic.com/ からAPIキーを取得

#### X (Twitter) APIキー
Developer Portal → プロジェクト → Appの設定で取得します。
- **重要**: AppのPermissionsを `Read and Write` に設定してください
- 必要な5つのキー:
  - `X_BEARER_TOKEN`
  - `X_API_KEY` (Consumer Key)
  - `X_API_SECRET` (Consumer Secret)
  - `X_ACCESS_TOKEN`
  - `X_ACCESS_SECRET`

### 3. 動作確認（テスト投稿なし）

```bash
python x_agent.py --dry-run
```

### 4. 1回だけ投稿する

```bash
python x_agent.py
```

### 5. スケジュール自動投稿を開始する

```bash
python scheduler.py
```

デフォルトの投稿時刻: 7:30 / 10:00 / 12:15 / 15:00 / 18:30 / 21:00 (JST)

`scheduler.py` の `SCHEDULE_TIMES` リストを編集すれば時刻を変更できます。

---

## ファイル構成

```
x_agent/
├── x_agent.py       # メインエージェント
├── scheduler.py     # 自動スケジューラー
├── requirements.txt # 必要ライブラリ
├── .env.example     # APIキーテンプレート
├── .env             # APIキー（自分で作成・Gitに入れない！）
└── agent.log        # 実行ログ（自動生成）
```

## 注意事項

- `.env` は絶対にGitにコミットしないでください
- X APIの無料プランは月1500ツイートまで投稿可能（1日50投稿相当）
- 同一内容の連投はXのスパム判定を受ける場合があります（本ツールはランダム生成のため問題ありません）
