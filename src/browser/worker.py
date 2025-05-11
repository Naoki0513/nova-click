"""browser.worker

将来的にブラウザワーカースレッド管理を専用モジュールへ分離するための
プレースホルダーです。現段階では ``browser.actions`` から既存 API を
そのまま再エクスポートして互換性を担保します。

このファイルを配置することで、静的解析ツールが ``src.browser.worker``
を解決できずに発する ImportError を防ぎます。
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
