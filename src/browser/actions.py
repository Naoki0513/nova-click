from __future__ import annotations

"""browser.actions

Playwright を利用したブラウザワーカースレッドの起動と、
高レベル API (click, input など) を提供するモジュール。
旧 ``browser.py`` からロジックを移行し、``browser.snapshot`` を
利用して ARIA Snapshot 関連処理を分離しています。
"""

import asyncio
import json
import logging
import os
import queue
import sys
import threading
import traceback
from typing import Any, Dict

import main as constants
from ..utils import add_debug_log, log_operation_error
from .utils import (
    get_screen_size,
    is_headless,
)
from . import snapshot as snapshot_mod

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# グローバルキュー/スレッド管理
# ---------------------------------------------------------------------------

_cmd_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
_res_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
_thread_started: bool = False
_browser_thread: threading.Thread | None = None

# Playwright の TimeoutError 用フォールバック (インポート失敗時用)
try:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError  # type: ignore
except ImportError:  # pragma: no cover

    class PlaywrightTimeoutError(Exception):
        """Playwright が無い場合のフォールバックタイムアウト例外"""

Page = Any  # 型エイリアス

# ---------------------------------------------------------------------------
# パブリック API
# ---------------------------------------------------------------------------

def initialize_browser() -> Dict[str, str]:
    """ブラウザワーカースレッドを初期化して開始します"""

    global _thread_started, _browser_thread

    if _thread_started:
        add_debug_log("initialize_browser: すでにスレッドが開始されています")
        return {"status": "success", "message": "ブラウザワーカーはすでに初期化されています"}

    add_debug_log("initialize_browser: ブラウザワーカースレッドを開始")
    _browser_thread = threading.Thread(target=_worker_thread, daemon=True)
    _browser_thread.start()
    _thread_started = True

    add_debug_log("initialize_browser: ブラウザワーカースレッド開始完了")
    return {"status": "success", "message": "ブラウザワーカーを初期化しました"}


def get_aria_snapshot() -> Dict[str, Any]:
    """ブラウザワーカースレッドから ARIA Snapshot 情報を取得します"""

    add_debug_log("browser.get_aria_snapshot: ARIAスナップショット取得要求送信")
    _ensure_worker_initialized()
    _cmd_queue.put({"command": "get_aria_snapshot"})

    try:
        res = _res_queue.get()
        add_debug_log(f"browser.get_aria_snapshot: 応答受信 status={res.get('status')}")

        if res.get("status") == "success":
            raw_snapshot = res.get("aria_snapshot", [])
            filtered_snapshot = [e for e in raw_snapshot if e.get("role") in constants.ALLOWED_ROLES]
            return {
                "status": "success",
                "aria_snapshot": filtered_snapshot,
                "message": res.get("message", "ARIA Snapshot取得成功"),
            }
        error_msg = res.get("message", "不明なエラー")
        add_debug_log(f"browser.get_aria_snapshot: エラー {error_msg}")
        return {"status": "error", "aria_snapshot": [], "message": f"ARIA Snapshot取得エラー: {error_msg}"}
    except queue.Empty:
        add_debug_log("browser.get_aria_snapshot: タイムアウト", level="ERROR")
        return {"status": "error", "aria_snapshot": [], "message": "ARIA Snapshot取得タイムアウト"}


def goto_url(url: str) -> Dict[str, Any]:
    """指定した URL に移動します"""

    add_debug_log(f"browser.goto_url: URL移動: {url}", level="DEBUG")
    _ensure_worker_initialized()
    _cmd_queue.put({"command": "goto", "params": {"url": url}})

    try:
        res = _res_queue.get()
        add_debug_log(f"browser.goto_url: 応答受信: {res}", level="DEBUG")
        return res
    except queue.Empty:
        add_debug_log("browser.goto_url: タイムアウト", level="ERROR")
        return {"status": "error", "message": "タイムアウト (応答なし)"}


def click_element(ref_id: int) -> Dict[str, Any]:
    """指定した要素 (ref_id) をクリックします"""

    if ref_id is None:
        add_debug_log("browser.click_element: ref_idが指定されていません")
        return {"status": "error", "message": "要素を特定するref_idが必要です"}

    add_debug_log(f"browser.click_element: ref_id={ref_id}の要素をクリック")
    _ensure_worker_initialized()
    _cmd_queue.put({"command": "click_element", "params": {"ref_id": ref_id}})

    try:
        res = _res_queue.get()
        add_debug_log(f"browser.click_element: 応答受信 status={res.get('status')}")
        _append_snapshot_to_response(res)
        
        # エラー発生時はINFOレベルでログ出力
        if res.get("status") != "success":
            log_operation_error(
                "click_element",
                res.get("message", "不明なエラー"),
                {"ref_id": ref_id}
            )
            
        return res
    except queue.Empty:
        error_msg = "クリックタイムアウト"
        add_debug_log(f"browser.click_element: {error_msg}", level="ERROR")
        
        # タイムアウトエラーをINFOレベルでログ出力
        log_operation_error("click_element", error_msg, {"ref_id": ref_id})
        
        error_res: Dict[str, Any] = {"status": "error", "message": error_msg, "ref_id": ref_id}
        _append_snapshot_to_response(error_res)
        return error_res


def input_text(text: str, ref_id: int) -> Dict[str, Any]:
    """指定した要素 (ref_id) にテキストを入力します"""

    if ref_id is None:
        add_debug_log("browser.input_text: ref_idが指定されていません")
        return {"status": "error", "message": "要素を特定するref_idが必要です"}
    if text is None:
        add_debug_log("browser.input_text: テキストが指定されていません")
        return {"status": "error", "message": "入力するテキストが必要です"}

    add_debug_log(f"browser.input_text: ref_id={ref_id}にテキスト '{text}' を入力")
    _ensure_worker_initialized()
    _cmd_queue.put({"command": "input_text", "params": {"text": text, "ref_id": ref_id}})

    try:
        res = _res_queue.get()
        add_debug_log(f"browser.input_text: 応答受信 status={res.get('status')}")
        _append_snapshot_to_response(res)
        
        # エラー発生時はINFOレベルでログ出力
        if res.get("status") != "success":
            log_operation_error(
                "input_text",
                res.get("message", "不明なエラー"),
                {"ref_id": ref_id, "text": text}
            )
            
        return res
    except queue.Empty:
        error_msg = "テキスト入力タイムアウト"
        add_debug_log(f"browser.input_text: {error_msg}", level="ERROR")
        
        # タイムアウトエラーをINFOレベルでログ出力
        log_operation_error("input_text", error_msg, {"ref_id": ref_id, "text": text})
        
        error_res: Dict[str, Any] = {"status": "error", "message": error_msg, "ref_id": ref_id, "text": text}
        _append_snapshot_to_response(error_res)
        return error_res


def get_current_url() -> str:
    """現在表示中のページの URL を取得します"""

    add_debug_log("browser.get_current_url: 現在のURL取得")
    _ensure_worker_initialized()
    _cmd_queue.put({"command": "get_current_url"})
    try:
        res = _res_queue.get()
        add_debug_log(f"browser.get_current_url: 応答受信 status={res.get('status')}")
        return res.get("url", "") if res.get("status") == "success" else ""
    except queue.Empty:
        add_debug_log("browser.get_current_url: タイムアウト")
        return ""


def save_cookies() -> Dict[str, Any]:
    """現在のブラウザセッションの Cookie を保存します"""

    add_debug_log("browser.save_cookies: Cookie保存")
    _ensure_worker_initialized()
    _cmd_queue.put({"command": "save_cookies"})
    try:
        res = _res_queue.get()
        add_debug_log(f"browser.save_cookies: 応答受信 status={res.get('status')}")
        return res
    except queue.Empty:
        add_debug_log("browser.save_cookies: タイムアウト")
        return {"status": "error", "message": "タイムアウト"}


def cleanup_browser() -> Dict[str, Any]:
    """ブラウザを終了します"""

    add_debug_log("browser.cleanup_browser: ブラウザ終了")
    _ensure_worker_initialized()
    _cmd_queue.put({"command": "quit"})
    try:
        res = _res_queue.get(timeout=5)
        add_debug_log(f"browser.cleanup_browser: 応答受信 status={res.get('status')}")
        return res
    except queue.Empty:
        add_debug_log("browser.cleanup_browser: タイムアウト - 強制終了します")
        return {"status": "success", "message": "タイムアウトによる強制終了"}

# ---------------------------------------------------------------------------
# 内部ユーティリティ
# ---------------------------------------------------------------------------

def _append_snapshot_to_response(res: Dict[str, Any]) -> None:
    """レスポンス辞書に ARIA Snapshot を追加します (失敗しても握りつぶす)"""

    try:
        aria_snapshot_result = get_aria_snapshot()
        res["aria_snapshot"] = aria_snapshot_result.get("aria_snapshot", [])
        if aria_snapshot_result.get("status") != "success":
            res["aria_snapshot_message"] = aria_snapshot_result.get("message", "ARIA Snapshot取得失敗")
    except Exception as e:  # pragma: no cover
        add_debug_log(f"_append_snapshot_to_response: スナップショット追加失敗: {e}", level="WARNING")


def _ensure_worker_initialized() -> Dict[str, str]:
    """ワーカースレッドが初期化されていることを確認"""

    if not _thread_started:
        return initialize_browser()
    return {"status": "success", "message": "ブラウザワーカーは既に初期化されています"}


# ---------------------------------------------------------------------------
# スレッド・ワーカー関連
# ---------------------------------------------------------------------------

def _worker_thread() -> None:
    """ブラウザワーカーのメインスレッド処理 (同期ラッパ)"""

    add_debug_log("ワーカースレッド: スレッド開始")
    asyncio.run(_async_worker())
    add_debug_log("ワーカースレッド: スレッド終了")


async def _async_worker() -> None:  # noqa: C901
    """非同期ワーカースレッドとして Playwright を直接操作"""

    add_debug_log("ワーカースレッド: 非同期ブラウザワーカー開始")

    screen_width, screen_height = get_screen_size()

    try:
        from playwright.async_api import async_playwright  # type: ignore
    except ImportError:
        add_debug_log("ワーカースレッド: Playwrightがインポートできませんでした", level="ERROR")
        _res_queue.put({"status": "error", "message": "Playwrightがインポートできませんでした"})
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

    browser = await playwright.chromium.launch(headless=is_headless, args=browser_launch_args)

    context = await browser.new_context(
        locale="ja-JP",
        ignore_https_errors=True,
        viewport={"width": screen_width, "height": screen_height},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    )

    # Cookie の読み込み
    if os.path.exists(constants.COOKIE_FILE):
        try:
            with open(constants.COOKIE_FILE, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            add_debug_log(f"ワーカースレッド: クッキーを読み込みました: {len(cookies)} 件")
        except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
            add_debug_log(f"ワーカースレッド: クッキーの読み込みに失敗: {e}")

    page = await context.new_page()

    # 初期ページ表示
    try:
        add_debug_log("ワーカースレッド: 初期ページ(Google)を読み込みます")
        await page.goto("https://www.google.com/", wait_until="networkidle", timeout=constants.DEFAULT_TIMEOUT_MS)
        await page.evaluate("() => { window.focus(); document.body.click(); }")
        add_debug_log("ワーカースレッド: 初期ページの読み込みが完了しました")
    except PlaywrightTimeoutError as e:
        add_debug_log(f"ワーカースレッド: 初期ページの読み込みでエラーが発生しました: {e}")
    except Exception as e:  # pragma: no cover
        add_debug_log(f"ワーカースレッド: 初期ページの読み込みで予期せぬエラーが発生しました: {e}")

    # コマンドループ
    while True:
        try:
            cmd = _cmd_queue.get(block=False)
            command = cmd.get("command")
            params = cmd.get("params", {})

            # 終了処理 ---------------------------------------------------------
            if command == "quit":
                add_debug_log("ワーカースレッド: 終了コマンドを受け取りました")
                _res_queue.put({"status": "success", "message": "ブラウザを終了しました"})
                break

            # ARIA Snapshot ----------------------------------------------------
            elif command == "get_aria_snapshot":
                add_debug_log("ワーカースレッド: ARIA Snapshot取得")
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=constants.DEFAULT_TIMEOUT_MS)
                    snap_result = await snapshot_mod.get_snapshot_with_stats(page)
                    snapshot_data = snap_result.get("snapshot", [])
                    error_count = snap_result.get("errorCount", 0)
                    process_error = snap_result.get("error")

                    if process_error:
                        add_debug_log(f"ワーカースレッド: JavaScript実行中にエラー発生: {process_error}")
                    if error_count > 0:
                        add_debug_log(f"ワーカースレッド: スナップショット取得中に {error_count} 件の要素処理エラーが発生しました。")

                    _res_queue.put({
                        "status": "success",
                        "message": f"ARIA Snapshot取得成功 ({len(snapshot_data)} 要素取得、{error_count} エラー)",
                        "aria_snapshot": snapshot_data,
                    })
                except PlaywrightTimeoutError as e:
                    current_url = page.url if hasattr(page, "url") else "不明"
                    error_msg = f"ARIA Snapshot取得エラー: {e}"
                    add_debug_log(f"ワーカースレッド: {error_msg} (URL: {current_url})")
                    _res_queue.put({"status": "error", "message": error_msg})

            # 要素クリック ------------------------------------------------------
            elif command == "click_element":
                ref_id = params.get("ref_id")
                add_debug_log(f"ワーカースレッド: 要素クリック (ref_id): {ref_id}")
                if ref_id is None:
                    _res_queue.put({"status": "error", "message": "要素を特定するためのref_idが不足しています"})
                    continue

                try:
                    selector = f"[data-ref-id='ref-{ref_id}']"
                    locator = page.locator(selector)
                    try:
                        await locator.click(timeout=constants.DEFAULT_TIMEOUT_MS)
                    except PlaywrightTimeoutError as te_click:
                        error_msg = f"クリックタイムアウト (ref_id={ref_id}): {te_click}"
                        add_debug_log("クリック操作タイムアウト", level="ERROR")
                        log_operation_error("click_element", error_msg, {"ref_id": ref_id})
                        snapshot_list = await snapshot_mod.take_aria_snapshot(page)
                        _res_queue.put({"status": "error", "message": error_msg, "aria_snapshot": snapshot_list})
                        continue
                    except Exception as e_click:
                        msg = str(e_click)
                        if "outside of the viewport" in msg:
                            add_debug_log("要素がビューポート外: 自動スクロール＆再試行を実行", level="WARNING")
                            box = await locator.bounding_box()
                            vp_info = await page.evaluate("() => ({height: window.innerHeight})")
                            if box and isinstance(vp_info, dict):
                                y_coord, height_val, vp_h = box.get("y", 0), box.get("height", 0), vp_info.get("height", 0)
                                scroll_amt = 0
                                if y_coord < 0:
                                    scroll_amt = y_coord - 20
                                elif y_coord + height_val > vp_h:
                                    scroll_amt = y_coord + height_val - vp_h + 20
                                if scroll_amt:
                                    await page.evaluate(f"() => window.scrollBy(0, {scroll_amt})")
                            await locator.evaluate("el => el.scrollIntoView({block: 'center', inline: 'center'})")
                            try:
                                await locator.click(timeout=constants.DEFAULT_TIMEOUT_MS)
                            except Exception:
                                await locator.click(force=True, timeout=constants.DEFAULT_TIMEOUT_MS)
                        else:
                            raise
                    _res_queue.put({"status": "success", "message": f"ref_id={ref_id} の要素をクリックしました"})
                except Exception as e:
                    current_url = page.url if hasattr(page, "url") else "不明"
                    error_msg = f"要素クリック時の予期せぬエラー (ref_id={ref_id}): {e}"
                    add_debug_log(f"ワーカースレッド: {error_msg} (URL: {current_url})")
                    log_operation_error("click_element", error_msg, {"ref_id": ref_id, "url": current_url})
                    tb = traceback.format_exc()
                    _res_queue.put({"status": "error", "message": error_msg, "traceback": tb})

            # テキスト入力 ------------------------------------------------------
            elif command == "input_text":
                text = params.get("text")
                ref_id = params.get("ref_id")
                add_debug_log(f"ワーカースレッド: テキスト入力 (ref_id={ref_id}, text='{text}')")
                if ref_id is None:
                    _res_queue.put({"status": "error", "message": "要素を特定するためのref_idが不足しています"})
                    continue
                if text is None:
                    _res_queue.put({"status": "error", "message": "入力するテキストが指定されていません"})
                    continue

                try:
                    selector = f"[data-ref-id='ref-{ref_id}']"
                    locator = page.locator(selector)
                    try:
                        await locator.fill("", timeout=constants.DEFAULT_TIMEOUT_MS)
                        await locator.fill(text, timeout=constants.DEFAULT_TIMEOUT_MS)
                        await locator.press("Enter", timeout=constants.DEFAULT_TIMEOUT_MS)
                    except PlaywrightTimeoutError as te_input:
                        error_msg = f"テキスト入力タイムアウト (ref_id={ref_id}): {te_input}"
                        add_debug_log("テキスト入力タイムアウト", level="ERROR")
                        log_operation_error("input_text", error_msg, {"ref_id": ref_id, "text": text})
                        snapshot_list = await snapshot_mod.take_aria_snapshot(page)
                        _res_queue.put({"status": "error", "message": error_msg, "aria_snapshot": snapshot_list})
                        continue
                    _res_queue.put({"status": "success", "message": f"ref_id={ref_id} の要素にテキスト '{text}' を入力しました"})
                except Exception as e:
                    current_url = page.url if hasattr(page, "url") else "不明"
                    error_msg = f"テキスト入力時の予期せぬエラー (ref_id={ref_id}, text='{text}'): {e}"
                    add_debug_log(f"ワーカースレッド: {error_msg} (URL: {current_url})")
                    log_operation_error("input_text", error_msg, {"ref_id": ref_id, "text": text, "url": current_url})
                    _res_queue.put({"status": "error", "message": error_msg})

            # Cookie 保存 -------------------------------------------------------
            elif command == "save_cookies":
                add_debug_log("ワーカースレッド: Cookie 保存要求を受信")
                try:
                    cookies = await context.cookies()
                    with open(constants.COOKIE_FILE, "w", encoding="utf-8") as f:
                        json.dump(cookies, f, ensure_ascii=False, indent=2)
                    _res_queue.put({"status": "success", "message": "Cookie を保存しました"})
                except Exception as e:
                    _res_queue.put({"status": "error", "message": f"Cookie 保存失敗: {e}"})

            # 現在 URL ----------------------------------------------------------
            elif command == "get_current_url":
                _res_queue.put({"status": "success", "url": page.url})

            # URL 遷移 ---------------------------------------------------------
            elif command == "goto":
                target_url = params.get("url")
                try:
                    await page.goto(str(target_url), wait_until="load", timeout=constants.DEFAULT_TIMEOUT_MS)
                    _res_queue.put({"status": "success", "message": f"{target_url} に移動しました"})
                except Exception as e:
                    _res_queue.put({"status": "error", "message": f"URL 移動失敗: {e}"})

            # 未知コマンド ------------------------------------------------------
            else:
                add_debug_log(f"ワーカースレッド: 未知のコマンド: {command}")
                _res_queue.put({"status": "error", "message": f"未知のコマンド: {command}"})

        except queue.Empty:
            await asyncio.sleep(0.1)
        except Exception as e:
            add_debug_log(f"ワーカースレッド: 予期せぬエラー: {e}")
            try:
                _res_queue.put({"status": "error", "message": f"予期せぬエラー: {e}"})
            except queue.Full:
                pass

    # finally ブロック ---------------------------------------------------------
    add_debug_log("ワーカースレッド: 終了処理")
    try:
        if "browser" in locals():
            await browser.close()  # type: ignore[attr-defined]
    except Exception as e:  # pragma: no cover
        add_debug_log(f"ワーカースレッド: 終了処理エラー: {e}") 