# ブラウザ操作エージェント

このプロジェクトは、自然言語の指示に基づいてウェブブラウザを自動操作するAIエージェントです。コマンドラインインターフェースを通じて、Amazon Bedrock (Claude 3 Sonnetなど) と連携し、Webブラウザ上での操作（クリック、テキスト入力、ページ移動など）を自動実行します。

## ✨ 主な機能

- **自然言語による操作**: `main.py` 内で定義された指示に基づいてブラウザを操作します。
- **基本的なブラウザ操作**: 検索、クリック、フォーム入力などを自動で行います。
- **自動ページ状態取得**: 操作実行後にページの主要な要素情報（ARIA Snapshot）を自動的に取得し、次の操作判断に利用します。
- **ボット検出回避**: Playwrightの起動オプションにより、一部のボット検出メカニズムを回避します。
- **デバッグサポート**: 詳細なログ出力や、エラー発生時にブラウザを開いたまま停止するデバッグモードを提供します。

## 🚀 セットアップ

### 1. 環境構築

まず、必要なライブラリをインストールし、Playwrightが使用するブラウザ（Chromium）をセットアップします。

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 認証情報の設定

Amazon Bedrockを利用するためのAWS認証情報が必要です。
プロジェクトルートに `credentials/` ディレクトリを作成し、その中に `aws_credentials.json` という名前で以下の内容のファイルを作成してください。

```json
{
  "aws_access_key_id": "あなたのAWSアクセスキー",
  "aws_secret_access_key": "あなたのAWSシークレットキー"
}
```

**注意:** 認証情報は機密情報です。Gitリポジトリにコミットしないように `.gitignore` に `credentials/` を追加することを推奨します。

## ▶️ 実行方法

以下のコマンドでエージェントを実行します。

```bash
python main.py
```

デフォルトでは、`main.py` の `run_cli_mode` 関数内で定義された固定の指示（クエリ）が実行されます。異なる操作を試したい場合は、`main.py` 内の `query` 変数の値を変更してください。

実行すると、自動的にブラウザ（Chromium）が起動し、指示に基づいた操作が開始されます。操作の進行状況や結果はターミナルにログとして表示されます。

### デバッグモード

より詳細なログを確認したい場合や、エラー発生時にブラウザの状態を確認したい場合は、`main.py` 内の `run_cli_mode` 関数の `debug` 変数を `True` に設定して実行してください。

```python
# main.py の run_cli_mode 関数内
debug = True # デバッグモードを有効にする
```

デバッグモードでは、エラー発生時に処理が一時停止し、コンソールにメッセージが表示されます。Enterキーを押すと処理が終了します。

## 🧪 テスト

プロジェクトにはいくつかのテストスクリプトが含まれています。

### すべてのテストを実行

```bash
python -m unittest discover tests
```

### 個別のテスト

特定のテストを実行することも可能です。

```bash
# コアロジックのテスト
python -m unittest tests.test_core

# E2Eテスト
python -m unittest tests.test_cli
```

各テストスクリプトも `--debug` オプションをサポートしており、デバッグモードで実行できます。

## 📂 プロジェクト構成

```
browser-agent/
├── agent/                 # エージェントのコアコード
│   ├── __init__.py
│   ├── core.py            # メインロジック、Bedrock連携
│   ├── prompts.py         # LLM向けプロンプト
│   ├── utils.py           # ユーティリティ（ロギング、認証情報読み込み等）
│   └── browser/           # ブラウザ操作関連
│       ├── __init__.py
│       ├── worker.py      # Playwrightを非同期で実行するワーカー
│       └── tools.py       # ブラウザ操作ツール (click, inputなど)
├── credentials/           # 認証情報 (Git管理外推奨)
│   └── aws_credentials.json
├── tests/                 # 各種テストスクリプト
│   ├── test_cli.py        # E2Eテスト
│   ├── test_core.py       # agent.core のユニットテスト
│   ├── get_aria_snapshot.py # ARIA Snapshot取得単体テスト
│   ├── click_element_test.py # click_element 単体テスト
│   └── input_text_test.py   # input_text 単体テスト
├── requirements.txt       # Python依存ライブラリ
├── README.md              # このファイル
└── main.py                # アプリケーションのエントリーポイント
```

## ライセンス

[ライセンス情報を記載してください]
