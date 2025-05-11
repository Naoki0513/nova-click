"""browserパッケージ

Playwright を利用したブラウザ自動操作機能を提供します。
このパッケージには以下のモジュールが含まれています：
- actions: 高レベルブラウザ操作API (click, input など)
- snapshot: ARIA Snapshot 取得機能
- utils: ブラウザ関連ユーティリティ
- worker: ワーカースレッド管理（将来拡張）
"""

from .actions import (cleanup_browser, click_element, get_aria_snapshot,
                      get_current_url, goto_url, initialize_browser,
                      input_text, save_cookies)
from .utils import get_screen_size, is_headless

__all__: list[str] = [
    "initialize_browser",
    "get_aria_snapshot",
    "goto_url",
    "click_element",
    "input_text",
    "get_current_url",
    "save_cookies",
    "cleanup_browser",
    "is_headless",
    "get_screen_size",
]
