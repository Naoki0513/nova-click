"""
ブラウザ操作エージェント - エントリポイント兼設定ファイル

ユーザーは以下の定数を書き換えるだけでモデルやプロンプトなどの
設定を変更できます。
"""
# ---------------------------------------------------------------------------
# main.py 実行用デフォルト値
# ---------------------------------------------------------------------------

DEFAULT_QUERY = (
    "google mapにアクセスし、目黒駅から溜池山王駅までの道のりを教えてください"
)
DEFAULT_MODEL_ID = "us.amazon.nova-pro-v1:0"
DEFAULT_CREDENTIALS_PATH = "credentials/aws_credentials.json"
DEFAULT_MAX_TURNS = 20

# ---------------------------------------------------------------------------
# ユーザー設定用定数（必要に応じて変更してください）
# ---------------------------------------------------------------------------

# ログレベル設定 ("DEBUG", "INFO", "WARNING", "ERROR")
LOG_LEVEL = "INFO"

# Cookie 保存先
COOKIE_FILE = "browser_cookies.json"

# ARIA Snapshot で認識対象とするロール
ALLOWED_ROLES = [
    "button",
    "link",
    "textbox",
    "searchbox",
    "combobox",
]

# ブラウザの初期ページURL
DEFAULT_INITIAL_URL = "https://www.google.com/"

# Playwright 操作のデフォルトタイムアウト (ミリ秒)
DEFAULT_TIMEOUT_MS = 3000

# ---------------------------------------------------------------------------
# 実行ラッパー
# ---------------------------------------------------------------------------
import sys


def main() -> int:  # noqa: D401
    """会話エージェントを実行するラッパー関数"""
    # 循環参照を避けるために動的 import を行う
    from src.message import run_cli_mode

    return run_cli_mode()


if __name__ == "__main__":
    sys.exit(main())
