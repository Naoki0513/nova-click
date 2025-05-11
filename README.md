# ブラウザ操作エージェント

このプロジェクトは、Playwrightを使用してブラウザを操作するAIエージェントを提供します。Amazon Bedrock APIを介してLLMを活用し、ウェブページの操作を自動化します。

## 概要

- **ブラウザ操作**: Playwrightを使用して、ウェブページの要素をクリックしたり、テキストを入力したりします。
- **LLM統合**: Amazon Bedrock APIを介して、ユーザーの指示に基づいてブラウザ操作を決定します。
- **ARIA Snapshot**: ページのアクセシビリティ情報を取得し、操作対象の要素を特定します。
- **プロンプトキャッシュ**: Amazon Bedrock API呼び出し時にシステムプロンプトとユーザーメッセージにキャッシュポイントを挿入し、キャッシュ読み書きトークンをトラッキングして効率的な再利用を実現します。

## 変更履歴

- コード品質の向上: lintエラーの修正とpylintスコアの改善
  - `src/browser/snapshot.py`、`src/browser/worker.py`、`src/browser/__init__.py`、`src/bedrock.py`、`src/exceptions.py`、`src/prompts.py`、`src/tools.py`のpylintスコアを10/10に改善
  - モジュールドキュメントの追加と改善
  - インポート文の順序整理（wrong-import-position修正）
  - f-stringからフォーマット文字列式への修正（logging-fstring-interpolation修正）
  - 長すぎる行の分割と整形（line-too-long修正）
  - `dev-tools/format_code.py`を活用して自動修正を適用

- 存在しない要素へのアクセス時の長時間待機問題を修正しました。
  - `src/browser/utils.py` の `locator.bounding_box()` にタイムアウト値 `constants.DEFAULT_TIMEOUT_MS` を設定
  - Playwrightの既定タイムアウト（30秒）ではなく、`main.py`で定義された標準タイムアウト（5秒）を適用
  - テスト実行時間が大幅に短縮され、特に存在しない要素を使用するエラーケースで約2分→約30秒に改善

- ブラウザの初期ページURLをmain.pyで設定できるようにしました。
  - `main.py` に `DEFAULT_INITIAL_URL` 定数を追加
  - ハードコードされていたGoogleのURLを定数で参照するように修正
  - ユーザーが初期ページを自由に変更できるようになり、特定のサイトを起点とした操作が容易になりました

- テスト用パラメータを統一して管理するよう修正しました。各テストスクリプトでより柔軟にパラメータを変更できます。
  - `tests/input_text_test.py`、`tests/click_element_test.py`、`tests/get_aria_snapshot.py`、`tests/main_e2e_test.py` に統一された形式でテストパラメータ変数を追加
  - URL、ref_id、入力テキストなどのパラメータをスクリプト上部で定義し、関数のデフォルト値や引数として使用するよう変更
  - テスト実行時にパラメータを簡単に変更可能になり、テストの柔軟性が向上

- スマートスクロール機能を追加しました。ビューポート外の要素操作時に自動でページをトップ・ボトムへスクロールし、要素を確実にビューポート内へ表示します。
  - `src/browser/utils.py` に `ensure_element_visible` ユーティリティを実装
  - `src/browser/actions.py` の `click_element` と `input_text` で同ユーティリティを利用し、従来の手動スクロールロジックを廃止

- プロンプトキャッシュ機能を実装しました。Amazon Bedrock API呼び出し時にシステムプロンプトとユーザーメッセージにキャッシュポイントを挿入し、トークン効率を向上させます。
  - `src/bedrock.py` のリクエスト構造を更新し、正しい形式でキャッシュポイントを追加
  - Amazon Bedrock APIの「タグ付き共用体」構造に対応し、システムプロンプトとキャッシュポイントを別オブジェクトとして設定
  - メッセージのcontentリスト内にキャッシュポイントを追加する形式に修正
  - トークン使用量のログ出力にキャッシュ読込/書込トークン数を追加
- `src/constants.py` を廃止し、定数定義を `main.py` に統合しました。これにより、ユーザーは `main.py` だけを編集すればモデルやプロンプトなどの設定を変更できます。
- 会話ループ処理（`run_cli_mode`）を `src/message.py` に移設しました。`main.py` は設定値とラッパー関数のみのシンプルな構成となっています。
- 未使用の機能（URLへの移動、現在のURL取得、Cookieの保存機能）を削除し、コードを整理しました。
- テスト用の定数を統合し、各テストスクリプトは `main.py` から定数を参照するように変更しました。
- pytest実行時の問題を修正し、テストがCI環境で正常に実行されるようになりました:
  - コマンドライン引数の処理を改善し、pytestから実行された際に不要な引数を無視するように変更
  - テスト関数がreturnではなくassertを使用するように修正
  - 不要なラッパーファイル（test_e2e_pytest.py）を削除し、テスト構造を簡素化
  - テスト実行中にタイムアウトした場合の処理を強化
  - 存在しない要素を使用した場合のフォールバック処理を実装
  - CI環境でのシステム依存関係のインストールを修正（libasound2t64 → libasound2）
- main.pyからテスト用定数を削除
  - `TEST_DEFAULT_URL` および `INPUT_TEXT_TEST_TIMEOUT` を削除
  - テスト用スクリプトで各定数をハードコーディングに変更
    - `tests/get_aria_snapshot.py`: デフォルトURL "https://www.google.co.jp/" を直接指定
    - `tests/input_text_test.py`: タイムアウト値 60 を直接指定
    - `tests/click_element_test.py`: setup_logging 関数の呼び出し方法を修正

## インストール

```bash
pip install -r requirements.txt
```

## 使用方法

```bash
python main.py
```

## ライセンス

MIT

## モジュール構成 (v2)

```
src/
  browser/           # ブラウザ操作ロジックを管理するサブパッケージ
    __init__.py      # 旧 browser.py と互換性を保つエクスポート
    actions.py       # Playwright を用いた実際の操作（クリック・入力・URL 遷移など）
    worker.py        # (今後) ブラウザワーカースレッド管理用プレースホルダー
    snapshot.py      # ARIA Snapshot 取得ロジック（JS コードを含む）
    utils.py         # 画面解像度取得・デバッグユーティリティなど
```

以前は `src/browser.py` 1 ファイルに集約されていた実装を、上記 4 つの
モジュールへ分割しました。`import browser` で従来どおり API を呼び出せる
ように `src/browser/__init__.py` で公開関数を再エクスポートしているため、
既存スクリプト側の修正は基本的に不要です。

## エラーログの改善

ブラウザ操作（click_elementやinput_text）の実行中にタイムアウトなどのエラーが発生した場合、
ログレベルがINFOに設定されていても、エラー内容を確実にログに出力するよう改善しました。

- `src/utils.py` に `log_operation_error` 関数を追加
- 操作エラー発生時に常にINFOレベル以上でログ出力
- ツール実行時のパラメータエラーも同様にログ出力

これにより、デバッグレベルをINFOに設定している場合でも、重要なエラー情報が確実にログに記録されるようになりました。
エラーが発生した場合、以下のような形式でログに出力されます：

```
操作エラー - click_element: クリックタイムアウト (ref_id=123)
操作エラー - input_text: 要素が見つかりません (ref_id=456, text='検索ワード')
```

## テストの実行

ローカルで全テストを実行するには次のコマンドを利用します。

```