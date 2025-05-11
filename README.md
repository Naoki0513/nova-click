# ブラウザ操作エージェント

Amazon Bedrock の **Amazon Nova** モデルと Playwright を組み合わせ、自然言語だけでブラウザを自動操作できるエージェントです。

![Demo](assets/demo.gif)

---

## できること

- 自然言語で指示を与えるだけでブラウザ操作を自動化

---

## クイックスタート

### 1. 事前準備

1. **AWS Bedrock へのアクセス権**を持つ IAM ユーザーを作成し、`bedrock:InvokeModel` 権限を付与します。
2. リポジトリ直下の `credentials/aws_credentials.json` に下記形式でアクセスキーを保存。

```json
{
  "aws_access_key_id": "YOUR_ACCESS_KEY",
  "aws_secret_access_key": "YOUR_SECRET_KEY",
  "region_name": "us-west-2"
}
```

### 2. 依存関係をインストール

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

### 3. 実行

```bash
python main.py
```

デフォルトでは「Google Map にアクセスし、東京からラスベガスまでの道のりを教えてください」というプロンプトが実行されます。設定を変えたい場合は `main.py` 先頭の定数を編集してください。