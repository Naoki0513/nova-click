# ブラウザ操作エージェント

このプロジェクトは、自然言語の指示に基づいてウェブブラウザを自動操作するAIエージェントです。コマンドラインインターフェースを通じて、Amazon Bedrock (Claude 3 Sonnetなど) と連携し、Webブラウザ上での操作（クリック、テキスト入力、ページ移動など）を自動実行します。

## ✨ 主な機能

- **自然言語による操作**: `main.py` 内で定義された指示に基づいてブラウザを操作します。
- **基本的なブラウザ操作**: 検索、クリック、フォーム入力などを自動で行います。
- **自動ページ状態取得**: 操作実行後にページの主要な要素情報（ARIA Snapshot）を自動的に取得し、次の操作判断に利用します。
- **ボット検出回避**: Playwrightの起動オプションにより、一部のボット検出メカニズムを回避します。
- **動的画面サイズ設定**: 実行環境の画面解像度を自動取得し、ブラウザ起動時のviewportとウィンドウサイズに適用します。
- **デフォルトタイムアウト**: すべての Playwright 操作にデフォルトで 5 秒 (`DEFAULT_TIMEOUT_MS`) のタイムアウトを適用し、タイムアウト発生時には自動でエラー情報と最新の ARIA Snapshot を返します。

## 🚀 セットアップ

### 1. 環境構築

まず、必要なライブラリをインストールし、Playwrightが使用するブラウザ（Chromium）をセットアップします。

```bash
# 実行環境のセットアップ
pip install -r requirements.txt
playwright install chromium

# 開発環境のセットアップ（コード品質ツールなど）
pip install -r requirements-dev.txt
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

### タイムアウトエラー発生時の挙動

すべての Playwright API 呼び出し (`page.goto`, `locator.click`, `locator.fill`, など) は既定で 5 秒のタイムアウトが設定されています。タイムアウトが発生すると、処理は中断されずに以下の情報がレスポンスとして返ります。

1. `status: "error"` とタイムアウトを示す `message`
2. 直近で取得した **最新の ARIA Snapshot** (ページ状態)

これにより、LLM はタイムアウト後でもページの状態を把握しつつ次のアクションを決定できます。

## 🧪 テスト

プロジェクトにはいくつかのテストスクリプトが含まれています。

### すべてのテストを実行

```bash
python -m unittest discover tests
```

### 個別のテスト実行

特定のテストを実行することも可能です。

```bash
# ARIA Snapshotのテスト
python tests/get_aria_snapshot.py

# クリック機能のテスト
python tests/click_element_test.py

# テキスト入力機能のテスト
python tests/input_text_test.py
```

### 環境変数

テスト実行時には以下の環境変数を設定できます。

```bash
# ヘッドレスモードでテストを実行（CIに最適）
HEADLESS=true python tests/get_aria_snapshot.py

# CIモードでログ出力を最適化
CI=true python tests/get_aria_snapshot.py
```

### CI/CD

このプロジェクトはGitHub Actionsを使用した継続的インテグレーション（CI）を実装しています。
メインブランチへのプッシュまたはプルリクエスト作成時に、自動的に以下のテストが実行されます：

1. ARIA Snapshotのテスト
2. クリック機能のテスト
3. テキスト入力機能のテスト

CIパイプラインでは、すべてのテストがヘッドレスモードで実行され、正常系と異常系の両方のテストケースが検証されます。

## 🛠️ 開発ガイドライン

### コード品質管理ツール

プロジェクトのコード品質を維持するため、以下のツールとプロセスを導入しています：

#### 自動フォーマットと品質チェックツール

- **autoflake**: 未使用のインポートや変数を自動的に削除
- **Black**: PEP 8準拠のコードフォーマッター
- **isort**: インポート文を整理・グループ化
- **Pylint**: コード品質とスタイルのリンター（10/10のスコアを目標）
- **flake8**: コードスタイルとエラーチェック
- **mypy**: 静的型チェック

#### 品質チェック自動化スクリプト

`dev-tools` ディレクトリには、コード品質を向上させるための便利なツールが含まれています：

```bash
# 開発ツールのインストール
pip install -r dev-tools/requirements-dev.txt

# 指定したディレクトリのすべてのPythonファイルを自動的にフォーマットしてPylintチェック
python dev-tools/format_code.py src/
python dev-tools/format_code.py tests/
python dev-tools/format_code.py dev-tools/

# VSCode設定を適用（自動フォーマットと品質チェックを有効化）
python dev-tools/setup_vscode.py
```

`format_code.py` は以下の処理を自動的に行います：

1. autoflakeで未使用インポートと変数を削除
2. blackでコードフォーマットを統一
3. isortでインポート文を整理
4. pylintでコード品質をチェック（スコア10/10を目指す）
5. 問題がある場合は自動修正を試みる（docstringの追加など）
6. 品質結果のサマリーを表示

### コードスタイル

コードのフォーマットには以下のツールを使用しています：

- [autoflake](https://github.com/PyCQA/autoflake) - 未使用のインポートや変数を自動削除
- [Black](https://github.com/psf/black) - コードフォーマッター
- [isort](https://pycqa.github.io/isort/) - インポート文の整理

以下のコマンドで自動的にコードをフォーマットできます：

```bash
# 未使用のインポートと変数を削除
autoflake --remove-all-unused-imports --remove-unused-variables --in-place ファイル名.py

# Blackでコードをフォーマット
black ファイル名.py

# isortでimport文を整理
isort ファイル名.py

# または、dev-toolsの自動スクリプトを使用（推奨）
python dev-tools/format_code.py ディレクトリ名/
```

これらのツールを順番に使用することで、コードの品質と一貫性を保つことができます。

### Pylint

コード品質のチェックには [Pylint](https://www.pylint.org/) を使用しています。
プロジェクト内のすべてのPythonファイルは、Pylintスコア **10/10** を目標としています。

```bash
# 通常のチェック
pylint ファイル名.py

# 特定のエラーチェックを無効化する場合
pylint ファイル名.py --disable=import-error,wrong-import-position

# または、dev-toolsの自動スクリプトを使用（推奨）
python dev-tools/format_code.py ディレクトリ名/
```

テストコードでは、以下のエラーチェックを無効化することがあります：
- import-error: インポートエラー（テスト環境での依存関係の問題）
- wrong-import-position: インポート位置の問題（テストコードでの必要なインポート順序）
- too-many-return-statements: 戻り値ステートメントが多すぎる問題（テストコードでの様々な条件確認）

## 🔄 変更履歴

| 日付 | 変更内容 |
|------|----------|
| 2024-10-XX | コード品質管理ツールを導入：<br>- `dev-tools/format_code.py`：自動的にautoflake、black、isort、pylintを実行し、10/10のPylintスコアを目指す<br>- `dev-tools/setup_vscode.py`：VSCodeの設定を自動適用し開発環境を統一<br>- `dev-tools/requirements-dev.txt`：開発用依存関係の管理<br>- pylint、flake8、mypy：静的解析ツールを導入してコード品質を向上<br>- `src/constants.py`、`src/message.py`、`src/prompts.py`、`src/tools.py`、`src/bedrock.py`、`dev-tools/`ディレクトリのスクリプトがPylintスコア10/10を達成 |
| 2024-09-01 | Playwright API呼び出しのタイムアウトを無効化し、time.sleepやwait_for_load_stateなどの待機時間を削除しました。 |
| 2024-09-XX | デフォルトタイムアウト (`DEFAULT_TIMEOUT_MS=5000`) を導入し、タイムアウト発生時にはエラー内容と最新のARIA Snapshotを返すよう改善しました。 |
| 2024-09-26 | Pylintエラーを修正：`tools.py`から未使用インポートを削除し、長すぎる行を複数行に分割しました。コード品質を向上させました。 |
| 2024-XX-XX | Pylintエラーを修正：`utils.py`で以下の改善を実施しました。<br>- ロギング関数でf文字列の代わりに%フォーマット記法を使用して遅延評価を実現<br>- openメソッドにエンコーディング指定を追加<br>- 例外処理の具体化（一般的なExceptionからより具体的な例外へ変更）<br>- 不要な条件テスト定数を除去<br>- 長すぎる行の分割<br>- モジュールdocstringの追加 |
| 2024-XX-XX | Pylintエラーを修正：テストスクリプトファイル（`input_text_test.py`と`get_aria_snapshot.py`）を改善しました。<br>- ロギング関数でf文字列の代わりに%フォーマット記法を使用して遅延評価を実現<br>- 未使用引数を`_`プレフィックスで明示<br>- インポート位置の問題を`pylint: disable/enable`コメントで解決<br>- 未使用インポートと変数を削除<br>- 不要なコメントを整理<br>- 例外処理を具体的な例外タイプに変更<br>- すべての関数に適切なdocstringを追加 |
| 2024-08-XX | ブラウザ起動時に実行環境の画面解像度を取得し、viewportおよびウィンドウサイズに動的に設定する機能を追加しました。 |
| 2024-07-16 | 大規模コードリファクタリングを実施。ディレクトリ構造を整理し、`agent`ディレクトリを`src`に変更。機能ごとに以下のモジュールに分割して保守性を向上：<br>- `browser.py`: Playwright APIを使用したブラウザ操作機能（旧`worker.py`と`tools.py`を統合）<br>- `tools.py`: LLM用ツール定義とディスパッチロジック<br>- `bedrock.py`: Amazon Bedrock API連携（旧`core.py`から分離）<br>- `message.py`: 会話履歴管理と整形（メッセージ関連処理を一元化）<br>- `prompts.py`: LLMシステムプロンプト（既存の場所を維持）<br>- `utils.py`: ユーティリティ関数（既存の場所を維持）<br>加えて、モジュール間の相対インポートパスを適切に修正し、循環インポートを解消。 |
| 2024-06-XX | Playwright 公式APIを直接使用するように `agent/browser/worker.py` をリファクタリングし、`browser-use` への依存を削除しました。 |
| 2024-06-29 | 未使用コードのクリーンアップを実施。未使用の関数・インポート・変数を削除してコードベースを最適化しました。 |
| 2024-06-30 | デバッグモード機能（`debug_pause`および`is_debug_mode`）を削除し、エラー時のURLと入力パラメータのログ出力に統合しました。 |
| 2024-10-XX | コードフォーマットとスタイル向上：Black、isortを導入し、テストコードのLintエラーを修正しました。特に`main_e2e_test.py`では「too-many-return-statements」エラーを解消するためにコード構造をリファクタリングしました。 |
