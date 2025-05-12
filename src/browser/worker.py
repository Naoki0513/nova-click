"""browser.worker

A placeholder module for future separation of browser worker thread management.
At the current stage, it re-exports existing APIs from ``browser.actions``
to maintain compatibility.

This file prevents ImportError that would be raised by static analysis tools
when they try to resolve ``src.browser.worker``.
"""

from __future__ import annotations

from .actions import click_element  # re-export
from .actions import (cleanup_browser, get_aria_snapshot, get_current_url,
                      goto_url, initialize_browser, input_text, save_cookies)

__all__: list[str] = [
    "initialize_browser",
    "get_aria_snapshot",
    "goto_url",
    "click_element",
    "input_text",
    "get_current_url",
    "save_cookies",
    "cleanup_browser",
]
