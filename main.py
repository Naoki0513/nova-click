"""
Browser Automation Agent - Entry point and configuration file

Users can change settings such as model and prompt
by modifying the constants below.
"""
# ---------------------------------------------------------------------------
# Default values for main.py execution
# ---------------------------------------------------------------------------

DEFAULT_QUERY = (
    "Search for the most popular waterproof Bluetooth speaker under $50 on Amazon and add it to the cart."
)
DEFAULT_MODEL_ID = "us.amazon.nova-pro-v1:0"
DEFAULT_CREDENTIALS_PATH = "credentials/aws_credentials.json"
DEFAULT_MAX_TURNS = 20

# ---------------------------------------------------------------------------
# User configurable constants (modify as needed)
# ---------------------------------------------------------------------------

# Log level setting ("DEBUG", "INFO", "WARNING", "ERROR")
LOG_LEVEL = "INFO"

# Cookie storage location
COOKIE_FILE = "browser_cookies.json"

# Roles to recognize in ARIA Snapshot
ALLOWED_ROLES = [
    "button",
    "link",
    "textbox",
    "searchbox",
    "combobox",
]

# Initial browser page URL
DEFAULT_INITIAL_URL = "https://www.google.com/"

# Default timeout for Playwright operations (milliseconds)
DEFAULT_TIMEOUT_MS = 3000

# ---------------------------------------------------------------------------
# Execution wrapper
# ---------------------------------------------------------------------------
import sys


def main() -> int:  # noqa: D401
    """Execute the conversation agent wrapper function"""
    # Use dynamic import to avoid circular references
    from src.message import run_cli_mode

    return run_cli_mode()


if __name__ == "__main__":
    sys.exit(main())
