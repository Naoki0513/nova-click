# ブラウザ操作エージェント

このプロジェクトは、自然言語指示でブラウザを操作するAIエージェントです。コマンドラインインターフェースから Webブラウザを自動的に操作できます。

## 構成

現在のプロジェクト構成は以下の通りです：

```
browser-agent/
├── agent/                 # エージェントコードディレクトリ
│   ├── __init__.py        # パッケージ初期化
│   ├── core.py            # コアロジック
│   ├── prompts.py         # プロンプト定義
│   ├── utils.py           # ユーティリティ関数 (ロギング設定含む)
│   └── browser/           # ブラウザ操作関連
│       ├── __init__.py
│       ├── worker.py      # ワーカースレッド処理
│       └── tools.py       # ツールの高レベル API
├── credentials/           # 認証情報ディレクトリ
│   └── aws_credentials.json
├── tests/                 # テスト用スクリプト
│   ├── test_cli.py        # E2Eテスト
│   ├── test_core.py       # コアロジックのユニットテスト
│   └── browser_test_app.py # ブラウザ操作テスト用UI (テスト目的のみ)
├── requirements.txt       # 依存ライブラリ
├── README.md              # このファイル
└── main.py                # プロジェクトのメインエントリーポイント
```

## 機能
- Webブラウザの自動操作
- コマンドラインからの自然言語指示による操作
- 検索、クリック、フォーム入力などの基本的なブラウザ操作
- 操作実行時のデバッグログ出力
- Converse API を利用したツール呼び出しと応答生成

## 使用方法

### 1. 環境構築
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 認証情報の設定
`credentials/` ディレクトリに `aws_credentials.json` を配置します。
```json
{
  "aws_access_key_id": "あなたのAWSアクセスキー",
  "aws_secret_access_key": "あなたのAWSシークレットキー"
}
```

### 3. アプリケーションの実行
コマンドラインから直接ブラウザ操作を実行します。実行中はターミナルにログが表示され、ブラウザが自動的に起動します。

```bash
# 基本的な使い方 (main.py内の固定クエリを実行)
python main.py

# main.py 内のクエリやモデルを変更して実行
# (必要に応じて main.py の run_cli_mode 関数内のパラメータを編集してください)
```

デフォルトでは、`main.py` 内の `run_cli_mode` 関数で定義された固定クエリ (`東京の現在の天気を教えてください。`) が実行されます。異なる操作を行いたい場合は、`main.py` の `query` 変数を直接編集してください。

デバッグモードを有効にするには、`main.py` 内の `debug` 変数を `True` に設定します。

## テスト
テスト用スクリプトは `tests/` ディレクトリに配置されています。

### すべてのテストを実行
```bash
python -m unittest discover tests
```

### 特定のテストを実行
```bash
# コアロジックのユニットテスト
python -m unittest tests.test_core

# E2Eテスト
python -m unittest tests.test_cli

# ブラウザ操作テスト（Streamlit UI - テスト用）
# streamlit run tests/browser_test_app.py
# (注: このテストは Streamlit がインストールされている場合のみ実行可能です)
```

## 技術仕様
- Playwright: ブラウザ自動化
- Amazon Bedrock: AI応答生成
- Claude 3 Sonnet (例): メインモデル
- Python: 開発言語

## 注意事項

- このアプリケーションを実行するには、有効なAWS Bedrockのアクセス権が必要です。
- 使用するモデル (例: Claude 3 Sonnet) へのアクセス権が必要です。

## 概要

このプロジェクトは、自然言語での指示に基づいてウェブブラウザを自動操作するAIエージェントです。Amazon Bedrock の Claude (または他のモデル) と連携して、ユーザーの要求を理解し、ウェブブラウザ上での操作（クリック、テキスト入力、ページ移動など）をコマンドラインから自動実行します。

## 特徴

- **コマンドラインからの自然言語指示**: `main.py` 内で定義された指示に基づいてブラウザを操作
- **段階的な操作実行**: 複雑なタスクを小さなステップに分解して実行
- **エラー回復機能**: 操作に失敗した場合、エラーメッセージを出力 (現状では自動回復は限定的)
- **詳細なデバッグログ**: 各関数の処理内容や状態をコンソールで確認可能なログ表示機能

## 技術スタック

- **AIモデル**: Amazon Bedrock (Claude 3 Sonnet など)
- **ブラウザ制御**: Playwright を利用したワーカースレッド
- **開発言語**: Python

## 主な機能

1. **ページ内容取得 (AX Tree)**: Webページのアクセシビリティ情報を取得 (内部処理)
2. **要素クリック**: AX Tree を基に要素をクリック
3. **テキスト入力**: AX Tree を基に要素にテキストを入力
4. **ページ移動**: 指定URLへの移動 (内部処理、または将来的なツール追加が必要)

## セットアップ方法

### 前提条件

- Python 3.8以上
- AWS認証情報（Amazon Bedrockへのアクセス権限を持つ）

### インストール手順

1. リポジトリをクローン
   ```
   git clone https://github.com/yourusername/browser-agent.git
   cd browser-agent
   ```

2. 依存パッケージのインストール
   ```
   pip install -r requirements.txt
   ```

3. AWS認証情報の設定
   `credentials/aws_credentials.json` ファイルを実際のAWS認証情報で更新してください。
   ```json
   {
     "aws_access_key_id": "your_access_key",
     "aws_secret_access_key": "your_secret_key",
     "region_name": "us-west-2" // 必要に応じてリージョン変更
   }
   ```
   > 注意: AWS認証情報は機密情報です。Gitリポジトリにコミットしないよう注意してください。

### 実行方法

```
cd browser-agent
python main.py
```
クエリを変更する場合は `main.py` を編集してください。

## デバッグログ機能

アプリケーションには詳細なデバッグログ機能が実装されています。
`main.py` 内の `debug` 変数を `True` に設定すると、詳細なログがコンソールに出力されます。

### 表示されるログ情報

- **Bedrock API呼び出し**: リクエスト詳細とレスポンス内容
- **ブラウザ操作ツール**: 各ツールの実行状態と結果
- **会話処理**: 会話の進行状況やターン管理の詳細 (限定的)
- **エラー情報**: 発生したエラーの詳細とスタックトレース

### 開発者向け情報

新しい関数を追加する場合は、`agent.utils` の `add_debug_log` 関数を使用してログを記録できます。

```python
from agent.utils import add_debug_log

# 文字列メッセージをログに記録
add_debug_log("ログメッセージ", "グループ名")

# dictやlistを直接渡せます
data = {"key": "value", "nested": {"number": 123}}
add_debug_log(data, "グループ名")
```

## 注意事項

- Amazon Bedrockの使用にはAWSアカウントと適切な権限が必要です。
- 複雑なJavaScriptを使用したサイトでは一部機能が制限される場合があります。

## ライセンス

[ライセンス情報を記載]

## 最終更新: 2025-04-23 00:00:28
