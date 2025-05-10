# ブラウザ操作エージェント

このプロジェクトは、Playwrightを使用してブラウザを操作するAIエージェントを提供します。Amazon Bedrock APIを介してLLMを活用し、ウェブページの操作を自動化します。

## 概要

- **ブラウザ操作**: Playwrightを使用して、ウェブページの要素をクリックしたり、テキストを入力したりします。
- **LLM統合**: Amazon Bedrock APIを介して、ユーザーの指示に基づいてブラウザ操作を決定します。
- **ARIA Snapshot**: ページのアクセシビリティ情報を取得し、操作対象の要素を特定します。

## 変更履歴

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

## テストの実行

ローカルで全テストを実行するには次のコマンドを利用します。

```bash
pip install -r requirements.txt
pip install pytest
pytest -q
```

CI では GitHub Actions のワークフローファイル (.github/workflows/ci.yml) で同様に pytest を実行しています。