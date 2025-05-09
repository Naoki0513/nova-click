# ブラウザ操作エージェント

このプロジェクトは、Playwrightを使用してブラウザを操作するAIエージェントを提供します。Amazon Bedrock APIを介してLLMを活用し、ウェブページの操作を自動化します。

## 概要

- **ブラウザ操作**: Playwrightを使用して、ウェブページの要素をクリックしたり、テキストを入力したりします。
- **LLM統合**: Amazon Bedrock APIを介して、ユーザーの指示に基づいてブラウザ操作を決定します。
- **ARIA Snapshot**: ページのアクセシビリティ情報を取得し、操作対象の要素を特定します。

## 変更履歴

- 未使用の機能（URLへの移動、現在のURL取得、Cookieの保存機能）を削除し、コードを整理しました。
- テスト用の定数を削除しました。

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
