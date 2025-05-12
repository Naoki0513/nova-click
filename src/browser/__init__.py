"""browser package

Provides browser automation functionality using Playwright.
This package includes the following modules:
- actions: High-level browser operation API (click, input, etc.)
- snapshot: ARIA Snapshot retrieval functionality
- utils: Browser-related utilities
- worker: Worker thread management (future extension)
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
