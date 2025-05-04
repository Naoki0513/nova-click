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
│   ├── get_aria_snapshot.py # ARIA Snapshot取得テスト
│   ├── click_element_test.py # click_elementツールテスト
│   ├── input_text_test.py   # input_textツールテスト
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

デバッグモードを有効にするには、`setup_logging(debug=True)` を実行するか、各種テストスクリプト・CLIスクリプトで `--debug` オプションを指定してください。デバッグモードでは内部エラー発生時にブラウザを開いたまま処理が停止し、手動で状況を確認できます (Enter キーで再開)。

### 新しいデバッグ停止機能

Playwright のタイムアウトや要素操作エラーが発生した際、デバッグモード (`--debug` オプション) では処理を中断してブラウザを開いたままにします。これにより、開発者は問題が発生した状態を直接ブラウザ上で確認できます。通常モードでは従来通り、エラー内容をログに残して処理を継続・終了します。

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

各テストスクリプトは `--debug` オプションをサポートし、タイムアウトエラー発生時にブラウザを閉じずに一時停止し、テストパラメータ（URL、ref_id、textなど）をログに出力します。

## 新しいテストスクリプト

デバッグや各ツール単体の動作確認を容易にするため、以下のテストスクリプトを `tests/` ディレクトリに追加しました。

| スクリプト | 説明 | 例 | 
|------------|------|----|
| `get_aria_snapshot.py` | 指定URLを開き、最新のARIA Snapshotを取得して表示（--debugオプションでタイムアウト時に停止しURLをログ出力） | `python tests/get_aria_snapshot.py --url "https://www.google.com" --debug` |
| `click_element_test.py` | 指定URLを開き、指定 `ref_id` の要素をクリック（--debugオプションでタイムアウト時に停止しURLとref_idをログ出力） | `python tests/click_element_test.py --url "https://www.google.com" --ref-id 2 --debug` |
| `input_text_test.py` | 指定URLを開き、指定 `ref_id` の要素にテキスト入力（--debugオプションでタイムアウト時に停止しURL,ref_id,textをログ出力） | `python tests/input_text_test.py --url "https://www.google.com" --ref-id 1 --text "今日の天気" --debug` |
| | 各テストは `--debug` オプションを付与すると、タイムアウト時にブラウザを開いたままテストパラメータをログに出力し一時停止します | |

`--debug` を付けると、内部エラー発生時にブラウザを閉じずに一時停止するため、要素の状態などを確認しやすくなります。

## 技術仕様
- Playwright: ブラウザ自動化
- browser-use: 高度なブラウザ検出回避機能（Google reCAPTCHA対策）
- Amazon Bedrock: AI応答生成
- Claude 3 Sonnet (例): メインモデル
- Python: 開発言語
- **ツール**:
    - `click_element`: 指定された `ref_id` (数値) を持つ要素をクリックします。
    - `input_text`: 指定された `ref_id` (数値) を持つ入力要素に指定された `text` を入力し、Enterキーを押します。

## 注意事項

- このアプリケーションを実行するには、有効なAWS Bedrockのアクセス権が必要です。
- 使用するモデル (例: Claude 3 Sonnet) へのアクセス権が必要です。

## 概要

このプロジェクトは、自然言語での指示に基づいてウェブブラウザを自動操作するAIエージェントです。Amazon Bedrock の Claude (または他のモデル) と連携して、ユーザーの要求を理解し、ウェブブラウザ上での操作（クリック、テキスト入力、ページ移動など）をコマンドラインから自動実行します。

## 特徴

- **コマンドラインからの自然言語指示**: `main.py` 内で定義された指示に基づいてブラウザを操作
- **段階的な操作実行**: 複雑なタスクを小さなステップに分解して実行
- **自動ARIA Snapshot取得**: 操作実行後に自動的に最新のページ状態（ARIA Snapshot, `ref_id`は数値）を取得し、レスポンスに含める（成功時も失敗時も）
- **エラー回復機能**: 操作に失敗した場合、エラーメッセージと最新のARIA Snapshotを出力
- **詳細なデバッグログ**: 各関数の処理内容や状態をコンソールで確認可能なログ表示機能
- **`ref_id`による要素特定**: 要素を一意に特定できる数値の参照ID (`ref_id`) による要素操作
- **検出回避機能**: Google reCAPTCHAなどのボット検出を回避する機能を内蔵

## 技術スタック

- **AIモデル**: Amazon Bedrock (Claude 3 Sonnet など)
- **ブラウザ制御**: Playwright と browser-use を利用したワーカースレッド
- **開発言語**: Python

## 主な機能

1. **ページ内容取得 (ARIA Snapshot)**: Webページの主要なインタラクティブ要素（button, link, comboboxなど）の情報（`role`, `name`, `ref_id`(数値)）を取得 (内部処理、ツール実行後に自動取得)
2. **要素クリック (`click_element`)**: ARIA Snapshot を基に `ref_id` (数値) で指定された要素をクリックし、実行後の最新ARIA Snapshotを取得
3. **テキスト入力 (`input_text`)**: ARIA Snapshot を基に `ref_id` (数値) で指定された要素にテキストを入力してEnterを押し、実行後の最新ARIA Snapshotを取得
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

追加のログ強化機能:
- **URL移動スタックトレース出力**: `goto_url` ツールがエラーを検知した際、例外のスタックトレースをログおよびレスポンスに含めます。
- **ツールコマンド送受信ログ**: `tools.goto_url` でコマンド送信前後にキューサイズや応答内容をDEBUGレベルで記録します。
- **デバッグモードでのURL移動エラー停止**: デバッグモード (`--debug`) 時にURL移動エラー発生時に処理を一時停止し、ブラウザの状態を確認できます。

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
- {datetime.datetime.now().strftime("%Y-%m-%d")}: ツール (`click_element`, `input_text`) の要素特定方法を `ref_id` のみに変更。ARIA Snapshotの取得情報も `role`, `name`, `ref_id` に限定。
- YYYY-MM-DD: ツール実行失敗時にもARIA Snapshotを取得し結果に含めるように変更。
- YYYY-MM-DD: `click_element` の `role` を `button`, `link` に限定。
- YYYY-MM-DD: `input_text` の `role` を `combobox` に限定。
- {datetime.datetime.now().strftime("%Y-%m-%d")}: 要素操作 (`click_element`, `input_text`) でPlaywright Locator APIを使用するように変更し、操作の安定性を向上。
- {datetime.datetime.now().strftime("%Y-%m-%d")}: ARIA Snapshot取得処理 (`get_aria_snapshot`) の安定性を向上（待機処理の追加、JavaScript内のエラーハンドリング強化）。
- {datetime.datetime.now().strftime("%Y-%m-%d")}: ARIA Snapshotで返す `ref_id` を数値に変更。ツール (`click_element`, `input_text`) の入力スキーマも `ref_id` が数値を受け付けるように変更し、内部で `"ref-{数字}"` 形式のセレクタを使用するように修正。
- {datetime.datetime.now().strftime("%Y-%m-%d")}: ページ移動 (`goto`) の `wait_until` 条件を `networkidle` から `domcontentloaded` に変更し、動的コンテンツを持つページでも適切にナビゲーション完了を検出するように修正。

## ライセンス

[ライセンス情報を記載]

## 最終更新日

{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
