[README.md](https://github.com/user-attachments/files/32478929/README.md)
# MENSA Watch

JAPAN MENSAの[入会テスト日程](https://mensa.jp/exam/)から**関東地方**の試験枠を定期的に取得し、状態が「満員」または「締切」から「申込可」に変わったときだけ通知するPython製の監視ツールです。

実際の申込操作は自動化しません。空き枠の発生を検知して、利用者が公式サイトで申し込むためのきっかけを提供することに責任範囲を絞っています。

## 特徴

- 関東地方の試験枠をHTMLから抽出
- 前回実行時の状態と比較し、**新たに申込可能になった枠**だけを検知
- Discord、Slack、LINE Notify、メールへの通知に対応
- GitHub Actionsによる20分ごとの定期実行
- 最新の状態を`mensa_state.json`へ保存し、Actionsから自動コミット
- 手動実行時に通知経路を確認できるテスト通知モード
- 対象地域の見出しや枠が見つからない場合に、サイト構造の変更を検知しやすい出力

## 動作の仕組み

```text
JAPAN MENSA 入会テスト日程ページ
            ↓ HTTP GET
     関東地方セクションを抽出
            ↓ BeautifulSoup
   日時・申込状態・申込リンクを取得
            ↓
   mensa_state.json の前回状態と比較
            ↓
   「申込可」へ変化した枠だけ通知
            ↓
       最新状態を保存
```

状態は日時文字列をキーに保存します。同じ枠が継続して「申込可」の間は再通知しないため、通知の重複を抑えられます。

## セットアップ

### 必要条件

- Python 3.11以降（GitHub Actionsでは3.11を使用）
- `pip`

### ローカル環境

```bash
git clone https://github.com/kazumatsutsumi/mensa-watch.git
cd mensa-watch
python -m venv .venv
```

仮想環境を有効化してから依存関係を入れます。

```bash
pip install -r requirements.txt
```

必要な通知方法だけ、[`.env.example`](.env.example)を参考に環境変数を設定してください。スクリプトは`.env`を自動読み込みしないため、ローカルではシェル、OSの環境変数、または環境変数を読み込むツールから渡します。

## 環境変数 / GitHub Secrets

すべて任意です。何も設定しない場合でも、監視結果は標準出力に表示され、状態ファイルは更新されます。

| 目的 | 環境変数 | 値 |
| --- | --- | --- |
| Discord | `DISCORD_WEBHOOK_URL` | Discord Incoming WebhookのURL |
| Slack | `SLACK_WEBHOOK_URL` | Slack Incoming WebhookのURL |
| LINE Notify | `LINE_NOTIFY_TOKEN` | LINE Notifyアクセストークン（レガシー対応） |
| メールの有効化 | `EMAIL_ENABLED` | `true`でメール送信を有効化 |
| SMTPホスト | `EMAIL_SMTP_HOST` | 省略時: `smtp.gmail.com` |
| SMTPポート | `EMAIL_SMTP_PORT` | 省略時: `587` |
| 差出人 | `EMAIL_FROM` | SMTP認証に使用するメールアドレス |
| 宛先 | `EMAIL_TO` | 送信先。複数の場合はカンマ区切り |
| SMTPパスワード | `EMAIL_APP_PASSWORD` | Gmailではアプリパスワードを使用 |
| テスト通知 | `TEST_NOTIFY` | `true`で監視を行わずテスト通知を送信 |

GitHub Actionsでメール通知を使う場合は、リポジトリの **Settings → Secrets and variables → Actions** に次のSecretsを登録します。

- `EMAIL_FROM`
- `EMAIL_TO`
- `EMAIL_APP_PASSWORD`

現行のワークフローはメール用の環境変数のみを渡します。Discord、Slack、LINE NotifyをActionsで使う場合は、該当の値をGitHub Secretsに登録したうえで、[`.github/workflows/mensa-watch.yml`](.github/workflows/mensa-watch.yml)の`env`へ明示的に追加してください。Secretsやアプリパスワードをリポジトリへコミットしないでください。

## 実行方法

### ローカル実行

```bash
python mensa_kanto_watch.py
```

通知設定だけを確認する場合は、次のように実行します。このモードでは日程ページの取得や状態ファイルの更新を行いません。

```bash
TEST_NOTIFY=true python mensa_kanto_watch.py
```

### GitHub Actions

ワークフローは20分ごとに実行されます。`Actions`タブから **MENSA Kanto Watch** を選び、`Run workflow`で手動実行することもできます。`test_notify`を`true`にするとテスト通知モードになります。

通常実行後に`mensa_state.json`が変化していれば、`mensa-watch-bot`名義で`update state`コミットが作成されます。そのためワークフローには`contents: write`権限を設定しています。

## 通知の条件と初回実行

- **初回実行**: 前回の状態がない場合、現在の全枠を状態ファイルに保存します。通知は送りません。
- **2回目以降**: 同じ日時の枠が「申込可」へ変わった場合だけ通知します。
- **継続して申込可**: すでに「申込可」だった枠には再通知しません。
- **テスト通知**: `TEST_NOTIFY=true`の場合は、状態比較をせずに設定済みの通知先へテストメッセージを送ります。

リポジトリには既存の状態ファイルが含まれています。別の監視履歴として開始したい場合は、内容を確認したうえで`mensa_state.json`を空のJSONオブジェクト（`{}`）に置き換えてください。次回実行は初回実行として扱われます。

## 注意事項

- 本ツールは公式サイトのHTML構造に依存します。見出しや表示方法が変わると取得できなくなる可能性があります。
- 空き枠・申込可否の最終確認と申込みは、必ず公式サイト上で行ってください。
- 過度な頻度でのアクセスは避けてください。現行のGitHub Actions設定は20分間隔です。
- Webhook URL、SMTPパスワード、アクセストークンは機密情報です。`.env`とGitHub Secretsで管理してください。
- LINE Notifyはレガシーの通知経路としてコードに残っています。新規の運用ではDiscord、Slack、またはメールを推奨します。

## プロジェクト構成

```text
.
├── .github/workflows/mensa-watch.yml  # 定期実行・状態の自動コミット
├── mensa_kanto_watch.py               # 取得、解析、状態比較、通知
├── mensa_state.json                   # 前回取得した枠の状態
├── requirements.txt                   # Python依存関係
├── .env.example                       # 通知設定のひな形
└── tests/                             # HTML解析の回帰テスト
```

## 技術スタック

- Python 3.11
- [Requests](https://requests.readthedocs.io/) — HTTPリクエスト
- [Beautiful Soup 4](https://www.crummy.com/software/BeautifulSoup/) — HTML解析
- GitHub Actions — 定期実行と状態ファイルの更新
- Discord / Slack Webhook、SMTP — 通知チャネル

## テスト

HTML解析の基本的な振る舞いは標準ライブラリの`unittest`で確認できます。

```bash
python -m unittest discover -s tests -v
```

## 今後の改善案

- HTMLフィクスチャを増やし、サイト構造変更に備えるテストを拡充する
- 通知先ごとの送信失敗を個別に記録し、再試行方針を設ける
- 監視対象の地域や実行間隔を設定ファイル化する
- 型ヒント、静的解析、依存関係のバージョン固定を導入する
- 通知経路をメンテナンス中のAPIへ整理し、設定検証を追加する

## License

ライセンスは未設定です。公開利用の条件を明確にする場合は、用途に合うライセンスを追加してください。
