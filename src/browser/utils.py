"""browser.utils

ブラウザ操作に関連するユーティリティ関数を集約したモジュールです。

主な責務:
1. ヘッドレスモード判定 (環境変数 ``HEADLESS``)
2. 画面解像度取得 (`get_screen_size`)

``is_headless`` は他モジュールからインポートされる定数のため
モジュールロード時に決定します。
"""

import asyncio
import logging
import os
import sys
from typing import Tuple

# ルート utils からデバッグログを再利用
from ..utils import add_debug_log

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ヘッドレス判定
# ---------------------------------------------------------------------------

is_headless: bool = os.environ.get("HEADLESS", "false").lower() == "true"

# ---------------------------------------------------------------------------
# tkinter などの GUI 関連ライブラリの事前読み込み
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    import ctypes  # type: ignore  # noqa: WPS433  # Windows API 呼び出しで必要
    TKINTER_MODULE = None  # Windows では tkinter を使用しない
else:
    # UNIX 系(OSX/Linux) でヘッドレスでなければ tkinter を試行ロード
    if not is_headless:
        try:
            import tkinter as TKINTER_MODULE  # type: ignore
        except ImportError:
            logger.warning("tkinterをインポートできませんでした。デフォルトの画面サイズを使用します。")
            TKINTER_MODULE = None
    else:
        TKINTER_MODULE = None

# Windows プラットフォームで asyncio のイベントループポリシーを調整
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# ---------------------------------------------------------------------------
# 画面サイズ取得
# ---------------------------------------------------------------------------

def get_screen_size() -> Tuple[int, int]:  # noqa: D401
    """デバイスの画面解像度を取得して返します。

    ヘッドレスモードの場合は ``1920x1080`` を返します。
    """

    if is_headless:
        add_debug_log("ヘッドレスモード: デフォルト画面解像度 1920x1080 を使用")
        return 1920, 1080

    try:
        if sys.platform == "win32":
            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)
        elif TKINTER_MODULE:
            root = TKINTER_MODULE.Tk()  # type: ignore[operator]
            width = root.winfo_screenwidth()
            height = root.winfo_screenheight()
            root.destroy()
        else:
            add_debug_log("tkinterが利用できません: デフォルト画面解像度を使用", level="WARNING")
            return 1920, 1080

        add_debug_log(f"取得した画面解像度: {width}x{height}")
        return int(width), int(height)
    except (NameError, AttributeError) as exc:
        add_debug_log(f"スクリーンサイズ取得エラー: {exc}", level="WARNING")
        return 1920, 1080
    except Exception as exc:  # pragma: no cover
        if TKINTER_MODULE is not None and isinstance(exc, TKINTER_MODULE.TclError):  # type: ignore[attr-defined]
            add_debug_log(f"スクリーンサイズ取得エラー (tkinter): {exc}", level="WARNING")
        else:
            add_debug_log(f"スクリーンサイズ取得エラー (不明): {exc}", level="WARNING")
        return 1920, 1080

__all__ = [
    "is_headless",
    "get_screen_size",
] 