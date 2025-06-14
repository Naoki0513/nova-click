"""browser.actions

A module that provides browser worker thread initialization and high-level APIs
(click, input, etc.) using Playwright. Logic has been migrated from the former
``browser.py`` and uses ``browser.snapshot`` to separate ARIA Snapshot processing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import threading
import traceback
from typing import Any, Dict

import main as constants

from ..utils import add_debug_log, log_operation_error
from . import snapshot as snapshot_mod
from .utils import ensure_element_visible, get_screen_size, is_headless

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global queue/thread management
# ---------------------------------------------------------------------------

_cmd_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
_res_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
_thread_started: bool = False
_browser_thread: threading.Thread | None = None

# Fallback for Playwright's TimeoutError (for import failure)
try:
    from playwright.async_api import \
        TimeoutError as PlaywrightTimeoutError  # type: ignore
except ImportError:  # pragma: no cover

    class PlaywrightTimeoutError(Exception):
        """Fallback timeout exception for when Playwright is not available"""


Page = Any  # 型エイリアス

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def initialize_browser() -> Dict[str, str]:
    """Initializes and starts the browser worker thread"""

    global _thread_started, _browser_thread

    if _thread_started:
        add_debug_log("initialize_browser: Thread is already started")
        return {
            "status": "success",
            "message": "Browser worker is already initialized",
        }

    add_debug_log("initialize_browser: Starting browser worker thread")
    _browser_thread = threading.Thread(target=_worker_thread, daemon=True)
    _browser_thread.start()
    _thread_started = True

    add_debug_log("initialize_browser: Browser worker thread started successfully")
    return {"status": "success", "message": "Browser worker initialized"}


def get_aria_snapshot() -> Dict[str, Any]:
    """Gets ARIA Snapshot information from the browser worker thread"""

    add_debug_log("browser.get_aria_snapshot: Sending ARIA snapshot request")
    _ensure_worker_initialized()
    _cmd_queue.put({"command": "get_aria_snapshot"})

    try:
        res = _res_queue.get()
        add_debug_log(f"browser.get_aria_snapshot: Response received status={res.get('status')}")

        if res.get("status") == "success":
            raw_snapshot = res.get("aria_snapshot", [])
            filtered_snapshot = [
                e for e in raw_snapshot if e.get("role") in constants.ALLOWED_ROLES
            ]
            return {
                "status": "success",
                "aria_snapshot": filtered_snapshot,
                "message": res.get("message", "ARIA Snapshot retrieved successfully"),
            }
        error_msg = res.get("message", "Unknown error")
        add_debug_log(f"browser.get_aria_snapshot: Error {error_msg}")
        return {
            "status": "error",
            "aria_snapshot": [],
            "message": f"ARIA Snapshot retrieval error: {error_msg}",
        }
    except queue.Empty:
        add_debug_log("browser.get_aria_snapshot: Timeout", level="ERROR")
        return {
            "status": "error",
            "aria_snapshot": [],
            "message": "ARIA Snapshot retrieval timeout",
        }


def goto_url(url: str) -> Dict[str, Any]:
    """Navigates to the specified URL"""

    add_debug_log(f"browser.goto_url: Navigate to URL: {url}", level="DEBUG")
    _ensure_worker_initialized()
    _cmd_queue.put({"command": "goto", "params": {"url": url}})

    try:
        res = _res_queue.get()
        add_debug_log(f"browser.goto_url: Response received: {res}", level="DEBUG")
        return res
    except queue.Empty:
        add_debug_log("browser.goto_url: Timeout", level="ERROR")
        return {"status": "error", "message": "Timeout (no response)"}


def click_element(ref_id: int) -> Dict[str, Any]:
    """Clicks the specified element (ref_id)"""

    if ref_id is None:
        add_debug_log("browser.click_element: ref_id is not specified")
        return {"status": "error", "message": "ref_id is required to identify the element"}

    add_debug_log(f"browser.click_element: Clicking element with ref_id={ref_id}")
    _ensure_worker_initialized()
    _cmd_queue.put({"command": "click_element", "params": {"ref_id": ref_id}})

    try:
        res = _res_queue.get()
        add_debug_log(f"browser.click_element: Response received status={res.get('status')}")
        _append_snapshot_to_response(res)

        # Log errors at INFO level
        if res.get("status") != "success":
            log_operation_error(
                "click_element", res.get("message", "Unknown error"), {"ref_id": ref_id}
            )

        return res
    except queue.Empty:
        error_msg = "Click timeout"
        add_debug_log(f"browser.click_element: {error_msg}", level="ERROR")

        # Log timeout error at INFO level
        log_operation_error("click_element", error_msg, {"ref_id": ref_id})

        error_res: Dict[str, Any] = {
            "status": "error",
            "message": error_msg,
            "ref_id": ref_id,
        }
        _append_snapshot_to_response(error_res)
        return error_res


def input_text(text: str, ref_id: int) -> Dict[str, Any]:
    """Inputs text to the specified element (ref_id)"""

    if ref_id is None:
        add_debug_log("browser.input_text: ref_id is not specified")
        return {"status": "error", "message": "ref_id is required to identify the element"}
    if text is None:
        add_debug_log("browser.input_text: Text is not specified")
        return {"status": "error", "message": "Text to input is required"}

    add_debug_log(f"browser.input_text: Inputting text '{text}' to ref_id={ref_id}")
    _ensure_worker_initialized()
    _cmd_queue.put(
        {"command": "input_text", "params": {"text": text, "ref_id": ref_id}}
    )

    try:
        res = _res_queue.get()
        add_debug_log(f"browser.input_text: Response received status={res.get('status')}")
        _append_snapshot_to_response(res)

        # Log errors at INFO level
        if res.get("status") != "success":
            log_operation_error(
                "input_text",
                res.get("message", "Unknown error"),
                {"ref_id": ref_id, "text": text},
            )

        return res
    except queue.Empty:
        error_msg = "Text input timeout"
        add_debug_log(f"browser.input_text: {error_msg}", level="ERROR")

        # Log timeout error at INFO level
        log_operation_error("input_text", error_msg, {"ref_id": ref_id, "text": text})

        error_res: Dict[str, Any] = {
            "status": "error",
            "message": error_msg,
            "ref_id": ref_id,
            "text": text,
        }
        _append_snapshot_to_response(error_res)
        return error_res


def get_current_url() -> str:
    """Gets the URL of the currently displayed page"""

    add_debug_log("browser.get_current_url: Getting current URL")
    _ensure_worker_initialized()
    _cmd_queue.put({"command": "get_current_url"})
    try:
        res = _res_queue.get()
        add_debug_log(f"browser.get_current_url: Response received status={res.get('status')}")
        return res.get("url", "") if res.get("status") == "success" else ""
    except queue.Empty:
        add_debug_log("browser.get_current_url: Timeout")
        return ""


def save_cookies() -> Dict[str, Any]:
    """Saves cookies from the current browser session"""

    add_debug_log("browser.save_cookies: Saving cookies")
    _ensure_worker_initialized()
    _cmd_queue.put({"command": "save_cookies"})
    try:
        res = _res_queue.get()
        add_debug_log(f"browser.save_cookies: Response received status={res.get('status')}")
        return res
    except queue.Empty:
        add_debug_log("browser.save_cookies: Timeout")
        return {"status": "error", "message": "Timeout"}


def take_screenshot(filepath: str = None, full_page: bool = True) -> Dict[str, Any]:
    """Takes a screenshot of the current page
    
    Args:
        filepath: Path to save the screenshot (optional)
        full_page: Whether to capture the full page or just viewport
        
    Returns:
        Dict with status, message, and filepath
    """
    add_debug_log(f"browser.take_screenshot: Taking screenshot, filepath={filepath}")
    _ensure_worker_initialized()
    _cmd_queue.put({
        "command": "take_screenshot", 
        "params": {"filepath": filepath, "full_page": full_page}
    })
    try:
        res = _res_queue.get(timeout=30)
        add_debug_log(f"browser.take_screenshot: Response received status={res.get('status')}")
        return res
    except queue.Empty:
        add_debug_log("browser.take_screenshot: Timeout")
        return {"status": "error", "message": "Screenshot timeout"}


def cleanup_browser() -> Dict[str, Any]:
    """Closes the browser"""

    add_debug_log("browser.cleanup_browser: Closing browser")
    _ensure_worker_initialized()
    _cmd_queue.put({"command": "quit"})
    try:
        res = _res_queue.get(timeout=5)
        add_debug_log(f"browser.cleanup_browser: Response received status={res.get('status')}")
        return res
    except queue.Empty:
        add_debug_log("browser.cleanup_browser: Timeout - forcing termination")
        return {"status": "success", "message": "Forced termination due to timeout"}


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------


def _append_snapshot_to_response(res: Dict[str, Any]) -> None:
    """Adds ARIA Snapshot to the response dictionary (swallows failures)"""

    try:
        aria_snapshot_result = get_aria_snapshot()
        res["aria_snapshot"] = aria_snapshot_result.get("aria_snapshot", [])
        if aria_snapshot_result.get("status") != "success":
            res["aria_snapshot_message"] = aria_snapshot_result.get(
                "message", "ARIA Snapshot retrieval failed"
            )
    except Exception as e:  # pragma: no cover
        add_debug_log(
            f"_append_snapshot_to_response: Failed to add snapshot: {e}",
            level="WARNING",
        )


def _ensure_worker_initialized() -> Dict[str, str]:
    """Ensures the worker thread is initialized"""

    if not _thread_started:
        return initialize_browser()
    return {"status": "success", "message": "Browser worker is already initialized"}


# ---------------------------------------------------------------------------
# Thread and worker related
# ---------------------------------------------------------------------------


def _worker_thread() -> None:
    """Main thread process for browser worker (synchronous wrapper)"""

    add_debug_log("Worker thread: Thread started")
    asyncio.run(_async_worker())
    add_debug_log("Worker thread: Thread ended")


async def _async_worker() -> None:  # noqa: C901
    """Operates Playwright directly as an asynchronous worker thread"""

    add_debug_log("Worker thread: Asynchronous browser worker started")

    screen_width, screen_height = get_screen_size()

    try:
        from playwright.async_api import async_playwright  # type: ignore
    except ImportError:
        add_debug_log(
            "Worker thread: Failed to import Playwright", level="ERROR"
        )
        _res_queue.put(
            {"status": "error", "message": "Failed to import Playwright"}
        )
        return

    playwright = await async_playwright().start()

    browser_launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins",
        "--disable-site-isolation-trials",
        "--start-maximized",
        "--start-fullscreen",
        f"--window-size={screen_width},{screen_height}",
    ]

    browser = await playwright.chromium.launch(
        headless=is_headless, args=browser_launch_args
    )

    context = await browser.new_context(
        locale="en-US",
        ignore_https_errors=True,
        viewport={"width": screen_width, "height": screen_height},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    )

    # Load cookies
    cookie_file = getattr(constants, 'COOKIE_FILE', 'browser_cookies.json')
    if os.path.exists(cookie_file):
        try:
            with open(cookie_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            add_debug_log(
                f"Worker thread: Cookies loaded: {len(cookies)} items"
            )
        except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
            add_debug_log(f"Worker thread: Failed to load cookies: {e}")

    page = await context.new_page()

    # Initial page display
    try:
        add_debug_log("Worker thread: Loading initial page")
        default_url = getattr(constants, 'DEFAULT_INITIAL_URL', 'https://www.google.com')
        default_timeout = getattr(constants, 'DEFAULT_TIMEOUT_MS', 3000)
        await page.goto(
            default_url,
            wait_until="networkidle",
            timeout=default_timeout,
        )
        await page.evaluate("() => { window.focus(); document.body.click(); }")
        add_debug_log(
            f"Worker thread: Initial page ({default_url}) loaded successfully"
        )
    except PlaywrightTimeoutError as e:
        add_debug_log(
            f"Worker thread: Error occurred while loading initial page: {e}"
        )
    except Exception as e:  # pragma: no cover
        add_debug_log(
            f"Worker thread: Unexpected error occurred while loading initial page: {e}"
        )

    # Command loop
    while True:
        try:
            cmd = _cmd_queue.get(block=False)
            command = cmd.get("command")
            params = cmd.get("params", {})

            # Termination process ---------------------------------------------
            if command == "quit":
                add_debug_log("Worker thread: Received quit command")
                _res_queue.put(
                    {"status": "success", "message": "Browser closed"}
                )
                break

            # ARIA Snapshot ----------------------------------------------------
            elif command == "get_aria_snapshot":
                add_debug_log("Worker thread: Get ARIA Snapshot")
                try:
                    timeout_ms = getattr(constants, 'DEFAULT_TIMEOUT_MS', 3000)
                    await page.wait_for_load_state(
                        "domcontentloaded", timeout=timeout_ms
                    )
                    snap_result = await snapshot_mod.get_snapshot_with_stats(page)
                    snapshot_data = snap_result.get("snapshot", [])
                    error_count = snap_result.get("errorCount", 0)
                    process_error = snap_result.get("error")

                    if process_error:
                        add_debug_log(
                            f"Worker thread: Error during JavaScript execution: {process_error}"
                        )
                    if error_count > 0:
                        add_debug_log(
                            f"Worker thread: {error_count} element processing errors occurred during snapshot retrieval."
                        )

                    _res_queue.put(
                        {
                            "status": "success",
                            "message": f"ARIA Snapshot retrieved successfully ({len(snapshot_data)} elements, {error_count} errors)",
                            "aria_snapshot": snapshot_data,
                        }
                    )
                except PlaywrightTimeoutError as e:
                    current_url = page.url if hasattr(page, "url") else "unknown"
                    error_msg = f"ARIA Snapshot retrieval error: {e}"
                    add_debug_log(f"Worker thread: {error_msg} (URL: {current_url})")
                    _res_queue.put({"status": "error", "message": error_msg})

            # Element click ----------------------------------------------------
            elif command == "click_element":
                ref_id = params.get("ref_id")
                add_debug_log(f"Worker thread: Element click (ref_id): {ref_id}")
                if ref_id is None:
                    _res_queue.put(
                        {
                            "status": "error",
                            "message": "ref_id is required to identify the element",
                        }
                    )
                    continue

                try:
                    selector = f"[data-ref-id='ref-{ref_id}']"
                    locator = page.locator(selector)

                    # Call utility to ensure element is within viewport
                    await ensure_element_visible(page, locator)

                    try:
                        timeout_ms = getattr(constants, 'DEFAULT_TIMEOUT_MS', 3000)
                        await locator.click(timeout=timeout_ms)
                    except PlaywrightTimeoutError as te_click:
                        error_msg = (
                            f"Click timeout (ref_id={ref_id}): {te_click}"
                        )
                        add_debug_log("Click operation timeout", level="ERROR")
                        log_operation_error(
                            "click_element", error_msg, {"ref_id": ref_id}
                        )
                        snapshot_list = await snapshot_mod.take_aria_snapshot(page)
                        _res_queue.put(
                            {
                                "status": "error",
                                "message": error_msg,
                                "aria_snapshot": snapshot_list,
                            }
                        )
                        continue
                    except Exception:
                        # Try one last time with ``force=True`` if normal click fails
                        timeout_ms = getattr(constants, 'DEFAULT_TIMEOUT_MS', 3000)
                        await locator.click(
                            force=True, timeout=timeout_ms
                        )
                    _res_queue.put(
                        {
                            "status": "success",
                            "message": f"Clicked element with ref_id={ref_id}",
                        }
                    )
                except Exception as e:
                    current_url = page.url if hasattr(page, "url") else "unknown"
                    error_msg = f"Unexpected error during element click (ref_id={ref_id}): {e}"
                    add_debug_log(f"Worker thread: {error_msg} (URL: {current_url})")
                    log_operation_error(
                        "click_element",
                        error_msg,
                        {"ref_id": ref_id, "url": current_url},
                    )
                    tb = traceback.format_exc()
                    _res_queue.put(
                        {"status": "error", "message": error_msg, "traceback": tb}
                    )

            # Text input ------------------------------------------------------
            elif command == "input_text":
                text = params.get("text")
                ref_id = params.get("ref_id")
                add_debug_log(
                    f"Worker thread: Text input (ref_id={ref_id}, text='{text}')"
                )
                if ref_id is None:
                    _res_queue.put(
                        {
                            "status": "error",
                            "message": "ref_id is required to identify the element",
                        }
                    )
                    continue
                if text is None:
                    _res_queue.put(
                        {
                            "status": "error",
                            "message": "Text to input is not specified",
                        }
                    )
                    continue

                try:
                    selector = f"[data-ref-id='ref-{ref_id}']"
                    locator = page.locator(selector)

                    # Ensure element is within viewport
                    await ensure_element_visible(page, locator)

                    try:
                        await locator.fill("", timeout=constants.DEFAULT_TIMEOUT_MS)
                        await locator.fill(text, timeout=constants.DEFAULT_TIMEOUT_MS)
                        await locator.press(
                            "Enter", timeout=constants.DEFAULT_TIMEOUT_MS
                        )
                    except PlaywrightTimeoutError as te_input:
                        error_msg = (
                            f"Text input timeout (ref_id={ref_id}): {te_input}"
                        )
                        add_debug_log("Text input timeout", level="ERROR")
                        log_operation_error(
                            "input_text", error_msg, {"ref_id": ref_id, "text": text}
                        )
                        snapshot_list = await snapshot_mod.take_aria_snapshot(page)
                        _res_queue.put(
                            {
                                "status": "error",
                                "message": error_msg,
                                "aria_snapshot": snapshot_list,
                            }
                        )
                        continue
                    _res_queue.put(
                        {
                            "status": "success",
                            "message": f"Input text '{text}' to element with ref_id={ref_id}",
                        }
                    )
                except Exception as e:
                    current_url = page.url if hasattr(page, "url") else "unknown"
                    error_msg = f"Unexpected error during text input (ref_id={ref_id}, text='{text}'): {e}"
                    add_debug_log(f"Worker thread: {error_msg} (URL: {current_url})")
                    log_operation_error(
                        "input_text",
                        error_msg,
                        {"ref_id": ref_id, "text": text, "url": current_url},
                    )
                    _res_queue.put({"status": "error", "message": error_msg})

            # Save cookies -------------------------------------------------------
            elif command == "save_cookies":
                add_debug_log("Worker thread: Received cookie save request")
                try:
                    cookies = await context.cookies()
                    with open(constants.COOKIE_FILE, "w", encoding="utf-8") as f:
                        json.dump(cookies, f, ensure_ascii=False, indent=2)
                    _res_queue.put(
                        {"status": "success", "message": "Cookies saved successfully"}
                    )
                except Exception as e:
                    _res_queue.put(
                        {"status": "error", "message": f"Failed to save cookies: {e}"}
                    )

            # Current URL ----------------------------------------------------------
            elif command == "get_current_url":
                _res_queue.put({"status": "success", "url": page.url})

            # URL navigation ---------------------------------------------------------
            elif command == "goto":
                target_url = params.get("url")
                try:
                    await page.goto(
                        str(target_url),
                        wait_until="load",
                        timeout=constants.DEFAULT_TIMEOUT_MS,
                    )
                    _res_queue.put(
                        {"status": "success", "message": f"Navigated to {target_url}"}
                    )
                except Exception as e:
                    _res_queue.put({"status": "error", "message": f"URL navigation failed: {e}"})

            # Screenshot -------------------------------------------------------------
            elif command == "take_screenshot":
                filepath = params.get("filepath")
                full_page = params.get("full_page", True)
                try:
                    import time
                    if not filepath:
                        timestamp = int(time.time())
                        filepath = f"screenshots/screenshot_{timestamp}.png"
                    
                    # Create directory if it doesn't exist
                    directory = os.path.dirname(filepath)
                    if directory:
                        os.makedirs(directory, exist_ok=True)
                    
                    # Take screenshot
                    await page.screenshot(path=filepath, full_page=full_page)
                    
                    _res_queue.put({
                        "status": "success",
                        "message": f"Screenshot saved successfully",
                        "filepath": os.path.abspath(filepath),
                        "size": os.path.getsize(filepath) if os.path.exists(filepath) else 0
                    })
                except Exception as e:
                    _res_queue.put({
                        "status": "error",
                        "message": f"Screenshot failed: {str(e)}"
                    })

            # Unknown command ------------------------------------------------------
            else:
                add_debug_log(f"Worker thread: Unknown command: {command}")
                _res_queue.put(
                    {"status": "error", "message": f"Unknown command: {command}"}
                )

        except queue.Empty:
            await asyncio.sleep(0.1)
        except Exception as e:
            add_debug_log(f"Worker thread: Unexpected error: {e}")
            try:
                _res_queue.put({"status": "error", "message": f"Unexpected error: {e}"})
            except queue.Full:
                pass

    # finally block ---------------------------------------------------------
    add_debug_log("Worker thread: Cleanup process")
    try:
        if "browser" in locals():
            await browser.close()  # type: ignore[attr-defined]
    except Exception as e:  # pragma: no cover
        add_debug_log(f"Worker thread: Cleanup process error: {e}")
