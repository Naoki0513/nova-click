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
from typing import Tuple, TYPE_CHECKING

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

# Playwright 型ヒント用 (ランタイム依存回避)
if TYPE_CHECKING:  # pragma: no cover
    from playwright.async_api import Page, Locator

__all__ = [
    "is_headless",
    "get_screen_size",
    "ensure_element_visible",
]

# ---------------------------------------------------------------------------
# スクロールユーティリティ
# ---------------------------------------------------------------------------

async def _scroll_strategies(page: "Page", locator: "Locator", attempt: int) -> None:
    """試行回数に応じて異なるスクロール戦略を実行します。

    0回目 : ``scrollIntoView`` で要素を中央へ
    1回目 : ページトップへ移動 (上方向のナビゲーションメニューなどに対応)
    2回目 : ページボトムへ移動 (フッターなどに対応)
    それ以降: 何もしない
    """

    try:
        if attempt == 0:
            # 要素自身を中央にスクロール
            await locator.evaluate(
                "el => el.scrollIntoView({block: 'center', inline: 'center'})"
            )
        elif attempt == 1:
            # ページトップへ
            await page.evaluate("() => window.scrollTo({top: 0, behavior: 'auto'})")
        elif attempt == 2:
            # ページボトムへ
            await page.evaluate(
                "() => window.scrollTo({top: document.body.scrollHeight, behavior: 'auto'})"
            )
    except Exception as exc:  # pragma: no cover
        # スクロール戦略自体が失敗しても握り潰す
        add_debug_log(f"_scroll_strategies: スクロール失敗: {exc}", level="DEBUG")

async def ensure_element_visible(
    page: "Page", locator: "Locator", max_attempts: int = 3
) -> None:  # noqa: D401
    """要素がビューポート内に入るよう自動スクロールを試みます。

    Playwright は要素操作時に自動スクロールしますが、ナビゲーションバーの
    ように *ページトップまでスクロールしなければ* DOM上に現れない要素や、
    sticky ヘッダーの背後に隠れてしまう要素が存在します。

    そこで以下の手順で最大 ``max_attempts`` 回までスクロールを試行します。

    1. ``scrollIntoView`` を使用して中央へ移動
    2. ページトップへスクロール
    3. ページボトムへスクロール

    それでも要素がビューポート外の場合は呼び出し元で例外処理してください。
    """

    for attempt in range(max_attempts):
        try:
            # 要素が既にビューポート内か判定 (bounding_box が取得できればOK)
            box = await locator.bounding_box()
            if box is not None:
                vp_info = await page.evaluate(
                    "() => ({width: window.innerWidth, height: window.innerHeight})"
                )
                if (
                    0 <= box["y"] <= vp_info["height"] - box["height"]
                    and 0 <= box["x"] <= vp_info["width"] - box["width"]
                ):
                    return  # ビューポート内
        except Exception:
            # bounding_box が取得出来ない場合はスクロールを試みる
            pass

        # スクロール戦略を実行
        await _scroll_strategies(page, locator, attempt)

        # スクロール直後は描画が落ち着くまで僅かに待機
        await asyncio.sleep(0.1)

    # ここまで到達した場合は要素をビューポート内に収められなかった
    add_debug_log(
        "ensure_element_visible: 要素をビューポート内に表示できませんでした",
        level="DEBUG",
    ) 