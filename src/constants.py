"""
constantsモジュール
"""

COOKIE_FILE = "browser_cookies.json"
ALLOWED_ROLES = ["button", "link", "textbox", "searchbox", "combobox"]
DEFAULT_TIMEOUT_MS = 5000  # 5秒

# main.py 用のデフォルト値
DEFAULT_QUERY = (
    "Amazonでイヤホンを調べてカートに入れてください。そのあとカートを開いてください。"
)
DEFAULT_MODEL_ID = "us.amazon.nova-pro-v1:0"
DEFAULT_CREDENTIALS_PATH = "credentials/aws_credentials.json"
DEFAULT_MAX_TURNS = 20
