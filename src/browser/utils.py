"""browser.utils

Browser operation related utility functions module.

Main responsibilities:
1. Headless mode determination (environment variable ``HEADLESS``)
2. Screen resolution retrieval (`get_screen_size`)

``is_headless`` is a constant imported by other modules and
is determined when the module is loaded.
"""

import asyncio
import logging
import os
import sys
from typing import TYPE_CHECKING, Tuple

import main as constants  # Import timeout constants

# Reuse debug log from root utils
from ..utils import add_debug_log

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Headless mode determination
# ---------------------------------------------------------------------------

is_headless: bool = os.environ.get("HEADLESS", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Pre-loading GUI-related libraries
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    import ctypes  # type: ignore  # noqa: WPS433  # Required for Windows API calls

    TKINTER_MODULE = None  # Don't use tkinter on Windows
else:
    # Try to load tkinter on UNIX-based systems (OSX/Linux) if not headless
    if not is_headless:
        try:
            import tkinter as TKINTER_MODULE  # type: ignore
        except ImportError:
            logger.warning(
                "Could not import tkinter. Using default screen size."
            )
            TKINTER_MODULE = None
    else:
        TKINTER_MODULE = None

# Adjust asyncio event loop policy on Windows platform
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# ---------------------------------------------------------------------------
# Screen size retrieval
# ---------------------------------------------------------------------------


def get_screen_size() -> Tuple[int, int]:  # noqa: D401
    """Get device screen resolution.

    Returns 1920x1080 in headless mode.
    """

    if is_headless:
        add_debug_log("Headless mode: Using default screen resolution 1920x1080")
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
            add_debug_log(
                "tkinter not available: Using default screen resolution", level="WARNING"
            )
            return 1920, 1080

        add_debug_log(f"Detected screen resolution: {width}x{height}")
        return int(width), int(height)
    except (NameError, AttributeError) as exc:
        add_debug_log(f"Screen size retrieval error: {exc}", level="WARNING")
        return 1920, 1080
    except Exception as exc:  # pragma: no cover
        if TKINTER_MODULE is not None and isinstance(exc, TKINTER_MODULE.TclError):  # type: ignore[attr-defined]
            add_debug_log(
                f"Screen size retrieval error (tkinter): {exc}", level="WARNING"
            )
        else:
            add_debug_log(f"Screen size retrieval error (unknown): {exc}", level="WARNING")
        return 1920, 1080


# Playwright type hints (avoid runtime dependency)
if TYPE_CHECKING:  # pragma: no cover
    from playwright.async_api import Locator, Page

__all__ = [
    "is_headless",
    "get_screen_size",
    "ensure_element_visible",
]

# ---------------------------------------------------------------------------
# Scroll utilities
# ---------------------------------------------------------------------------


async def _scroll_strategies(page: "Page", locator: "Locator", attempt: int) -> None:
    """Execute different scroll strategies based on attempt number.

    Attempt 0: Center element with `scrollIntoView`
    Attempt 1: Scroll to page top (for navigation menus at the top)
    Attempt 2: Scroll to page bottom (for footers)
    Further attempts: Do nothing
    """

    try:
        if attempt == 0:
            # Center the element itself
            await locator.evaluate(
                "el => el.scrollIntoView({block: 'center', inline: 'center'})"
            )
        elif attempt == 1:
            # Scroll to page top
            await page.evaluate("() => window.scrollTo({top: 0, behavior: 'auto'})")
        elif attempt == 2:
            # Scroll to page bottom
            await page.evaluate(
                "() => window.scrollTo({top: document.body.scrollHeight, behavior: 'auto'})"
            )
    except Exception as exc:  # pragma: no cover
        # Swallow exceptions in scroll strategies
        add_debug_log(f"_scroll_strategies: Scroll failed: {exc}", level="DEBUG")


async def ensure_element_visible(
    page: "Page", locator: "Locator", max_attempts: int = 3
) -> None:  # noqa: D401
    """Attempt to automatically scroll to ensure element is in viewport.

    While Playwright automatically scrolls when operating on elements, some elements
    like those in navigation bars that only appear when scrolling to the top of the
    page, or elements hidden behind sticky headers, may require special handling.

    This tries the following strategies up to `max_attempts` times:

    1. Use `scrollIntoView` to center the element
    2. Scroll to page top
    3. Scroll to page bottom

    If the element is still outside the viewport, the caller should handle the exception.
    """

    for attempt in range(max_attempts):
        try:
            # Check if element is already in viewport (can get bounding_box)
            box = await locator.bounding_box(timeout=constants.DEFAULT_TIMEOUT_MS)
            if box is not None:
                vp_info = await page.evaluate(
                    "() => ({width: window.innerWidth, height: window.innerHeight})"
                )
                # If all conditions are met, the element is in the viewport
                is_in_viewport = (
                    0 <= box["y"] <= vp_info["height"] - box["height"]
                    and 0 <= box["x"] <= vp_info["width"] - box["width"]
                )
                if is_in_viewport:
                    return  # Element is in viewport
        except Exception:
            # If can't get bounding_box, try scrolling
            pass

        # Execute scroll strategy
        await _scroll_strategies(page, locator, attempt)

        # Wait briefly after scrolling for rendering to settle
        await asyncio.sleep(0.1)

    # If reached here, couldn't fit element in viewport
    add_debug_log(
        "ensure_element_visible: Could not bring element into viewport",
        level="DEBUG",
    )
