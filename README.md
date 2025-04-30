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
- Webブラウザの自動操作（CAPTCHAブロックの回避機能付き）
- コマンドラインからの自然言語指示による操作
- 検索、クリック、フォーム入力などの基本的なブラウザ操作
- 操作実行後の自動ARIA Snapshot取得と結果への含有
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

デフォルトでは、`main.py` 内の `run_cli_mode` 関数で定義された固定クエリが実行されます。異なる操作を行いたい場合は、`main.py` の `query` 変数を直接編集してください。

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
- browser-use: 高度なブラウザ検出回避機能（Google reCAPTCHA対策）
- Amazon Bedrock: AI応答生成
- Claude 3 Sonnet (例): メインモデル
- Python: 開発言語
- **ツール**: 
    - `click_element`: `role` が `button` または `link` の要素をクリックします。ref_idによる指定も可能です。
    - `input_text`: `role` が `combobox` の要素にテキストを入力しEnterを押します。ref_idによる指定も可能です。

## 注意事項

- このアプリケーションを実行するには、有効なAWS Bedrockのアクセス権が必要です。
- 使用するモデル (例: Claude 3 Sonnet) へのアクセス権が必要です。

## 概要

このプロジェクトは、自然言語での指示に基づいてウェブブラウザを自動操作するAIエージェントです。Amazon Bedrock の Claude (または他のモデル) と連携して、ユーザーの要求を理解し、ウェブブラウザ上での操作（クリック、テキスト入力、ページ移動など）をコマンドラインから自動実行します。

## 特徴

- **コマンドラインからの自然言語指示**: `main.py` 内で定義された指示に基づいてブラウザを操作
- **段階的な操作実行**: 複雑なタスクを小さなステップに分解して実行
- **自動ARIA Snapshot取得**: 操作実行後に自動的に最新のページ状態（ARIA Snapshot）を取得し、レスポンスに含める（成功時も失敗時も）
- **エラー回復機能**: 操作に失敗した場合、エラーメッセージと最新のARIA Snapshotを出力
- **詳細なデバッグログ**: 各関数の処理内容や状態をコンソールで確認可能なログ表示機能
- **ref-id機能**: 要素を一意に特定できる参照IDによる要素操作が可能
- **検出回避機能**: Google reCAPTCHAなどのボット検出を回避する機能を内蔵

## 技術スタック

- **AIモデル**: Amazon Bedrock (Claude 3 Sonnet など)
- **ブラウザ制御**: Playwright と browser-use を利用したワーカースレッド
- **開発言語**: Python

## 主な機能

1. **ページ内容取得 (ARIA Snapshot)**: Webページの主要なインタラクティブ要素（button, link, combobox）の情報を取得 (内部処理、ツール実行後に自動取得)
2. **要素クリック (`click_element`)**: ARIA Snapshot を基に `role` (`button` または `link`) と `name` または `ref_id` で指定された要素をクリックし、実行後の最新ARIA Snapshotを取得
3. **テキスト入力 (`input_text`)**: ARIA Snapshot を基に `role` (`combobox`) と `name` または `ref_id` で指定された要素にテキストを入力してEnterを押し、実行後の最新ARIA Snapshotを取得
4. **ページ移動**: 指定URLへの移動 (内部処理、または将来的なツール追加が必要)
5. **ボット検出回避**: browser-useライブラリを使用してreCAPTCHA等のボット検出を回避

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
   playwright install chromium
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
- アプリケーションには詳細なデバッグログ機能が実装されています。
- `main.py` 内の `debug` 変数を `True` に設定すると、詳細なログがコンソールに出力されます。
- デバッグモード実行時、プロジェクトルートの `log/` ディレクトリにタイムスタンプ付きのファイル名（`YYYY-MM-DD_HH-MM-SS.json`）でログファイルが生成されます。
- 各ログ呼び出しごとに1件のJSONオブジェクトがインデント付きの形式で書き出されるため、ファイル単位で完全なJSON構造を確認できます。

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

## 変更履歴

- 2024-XX-XX: browser-useライブラリを導入し、Google reCAPTCHA回避機能を追加
- 2024-XX-XX: AX TreeからARIA Snapshotへの移行を実施。要素操作の柔軟性と安定性が向上
- 2024-XX-XX: ref-id機能を追加。要素を一意に特定できる参照IDを使用した操作が可能に
- YYYY-MM-DD: ツール実行失敗時にもARIA Snapshotを取得し結果に含めるように変更。
- YYYY-MM-DD: `click_element` の `role` を `button`, `link` に限定。
- YYYY-MM-DD: `input_text` の `role` を `combobox` に限定。
- 2024-0X-XX: ツール実行後の自動ARIA Snapshot取得機能を追加。ツール応答のJSON内に最新ページ状態が含まれるよう改善。
- 2024-0X-XX: 内部的なBedrock APIリクエスト形式を調整し、ツール実行結果とARIA Snapshot情報の送信方法を改善。

## ライセンス

[ライセンス情報を記載]

## 最終更新日

{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
