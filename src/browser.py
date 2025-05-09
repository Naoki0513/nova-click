"""
ブラウザ操作モジュール

Playwright を使用したブラウザ操作の実装を提供します。
以下の機能を含みます:
- ブラウザの初期化と終了
- 要素のクリック、テキスト入力
- ARIA Snapshotの取得
- URLへの移動
"""

import asyncio
import json
import logging
import os
import queue
import sys
import threading
import traceback
from typing import Any

from . import constants
from .utils import add_debug_log

logger = logging.getLogger(__name__)

is_headless = os.environ.get("HEADLESS", "false").lower() == "true"

if sys.platform == "win32":
    import ctypes
    TKINTER_MODULE = None 
else:
    if not is_headless:
        try:
            import tkinter as TKINTER_MODULE
        except ImportError:
            logger.warning(
                "tkinterをインポートできませんでした。デフォルトの画面サイズを使用します。"
            )
            TKINTER_MODULE = None
    else:
        TKINTER_MODULE = None

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

_cmd_queue: queue.Queue[dict[str, Any]] = queue.Queue()
_res_queue: queue.Queue[dict[str, Any]] = queue.Queue()
_thread_started = False
_browser_thread: threading.Thread | None = None


logger = logging.getLogger(__name__)

try:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
except ImportError:
    class PlaywrightTimeoutError(Exception):
        """Playwrightのタイムアウトエラーのフォールバック定義。
        
        Playwrightをインポートできない場合に使用される代替クラス。
        """

Page = Any


def is_debug_mode() -> bool:
    """常に False を返すスタブ（旧デバッグモード互換用）"""
    return False


def debug_pause(msg: str = "") -> None:
    """デバッグモードの一時停止を無効化するスタブ"""
    add_debug_log(f"debug_pause 呼び出し: {msg} (スタブ)")

def _get_screen_size() -> tuple[int, int]:
    """デバイスの画面解像度を取得して返します。ヘッドレスモードの場合はデフォルト値を返します。"""
    if is_headless:
        add_debug_log("ヘッドレスモード: デフォルト画面解像度 1920x1080 を使用")
        return 1920, 1080

    try:
        if sys.platform == "win32":
            user32 = ctypes.windll.user32
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)
        elif TKINTER_MODULE:
            root = TKINTER_MODULE.Tk()
            width = root.winfo_screenwidth()
            height = root.winfo_screenheight()
            root.destroy()
        else:
            add_debug_log(
                "tkinterが利用できません: デフォルト画面解像度を使用", level="WARNING"
            )
            return 1920, 1080

        add_debug_log(f"取得した画面解像度: {width}x{height}")
        return width, height
    except (ctypes.ArgumentError, AttributeError) as e:
        add_debug_log(f"スクリーンサイズ取得エラー: {e}", level="WARNING")
        return 1920, 1080
    except Exception as e:
        if TKINTER_MODULE is not None and isinstance(e, TKINTER_MODULE.TclError):
            add_debug_log(f"スクリーンサイズ取得エラー (tkinter): {e}", level="WARNING")
        else:
            add_debug_log(f"スクリーンサイズ取得エラー (不明): {e}", level="WARNING")
        return 1920, 1080


def _worker_thread() -> None:
    """ブラウザワーカーのメインスレッド処理"""
    add_debug_log("ワーカースレッド: スレッド開始")
    asyncio.run(_async_worker())
    add_debug_log("ワーカースレッド: スレッド終了")


def initialize_browser():
    """ブラウザワーカースレッドを初期化して開始します"""
    global _thread_started, _browser_thread

    if _thread_started:
        add_debug_log("initialize_browser: すでにスレッドが開始されています")
        return {
            "status": "success",
            "message": "ブラウザワーカーはすでに初期化されています",
        }

    add_debug_log("initialize_browser: ブラウザワーカースレッドを開始")
    _browser_thread = threading.Thread(target=_worker_thread, daemon=True)
    _browser_thread.start()
    _thread_started = True

    add_debug_log("initialize_browser: ブラウザワーカースレッド開始完了")

    return {"status": "success", "message": "ブラウザワーカーを初期化しました"}


def _ensure_worker_initialized() -> dict[str, str]:
    """ワーカースレッドが初期化されていることを確認します"""
    if not _thread_started:
        return initialize_browser()
    return {"status": "success", "message": "ブラウザワーカーは既に初期化されています"}


def get_aria_snapshot() -> dict[str, Any]:
    """ブラウザワーカースレッドからARIA Snapshot情報を取得し、
    button, link, combobox要素などをフラットリストで返します。"""
    add_debug_log("browser.get_aria_snapshot: ARIAスナップショット取得要求送信")
    _ensure_worker_initialized()
    _cmd_queue.put({"command": "get_aria_snapshot"})
    try:
        res = _res_queue.get()
        add_debug_log(f"browser.get_aria_snapshot: 応答受信 status={res.get('status')}")

        if res.get("status") == "success":
            raw_snapshot = res.get("aria_snapshot", [])
            filtered_snapshot = [
                e for e in raw_snapshot if e.get("role") in constants.ALLOWED_ROLES
            ]
            return {
                "status": "success",
                "aria_snapshot": filtered_snapshot,
                "message": res.get("message", "ARIA Snapshot取得成功"),
            }
        else:
            error_msg = res.get("message", "不明なエラー")
            add_debug_log(f"browser.get_aria_snapshot: エラー {error_msg}")
            return {
                "status": "error",
                "aria_snapshot": [],
                "message": f"ARIA Snapshot取得エラー: {error_msg}",
            }
    except queue.Empty:
        add_debug_log("browser.get_aria_snapshot: タイムアウト", level="ERROR")
        return {
            "status": "error",
            "aria_snapshot": [],
            "message": "ARIA Snapshot取得タイムアウト",
        }


def goto_url(url: str) -> dict[str, Any]:
    """指定したURLに移動します"""
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


def click_element(ref_id: int) -> dict[str, Any]:
    """指定した要素 (ref_idで特定) をクリックします。

    Args:
        ref_id: 要素の参照ID (数値、get_aria_snapshot で取得したもの)

    Returns:
        操作結果の辞書
    """
    if ref_id is None:
        add_debug_log("browser.click_element: ref_idが指定されていません")
        return {"status": "error", "message": "要素を特定するref_idが必要です"}

    add_debug_log(f"browser.click_element: ref_id={ref_id}の要素をクリック")
    _ensure_worker_initialized()
    _cmd_queue.put({"command": "click_element", "params": {"ref_id": ref_id}})

    try:
        res = _res_queue.get()
        add_debug_log(f"browser.click_element: 応答受信 status={res.get('status')}")
        try:
            aria_snapshot_result = get_aria_snapshot()
            res["aria_snapshot"] = aria_snapshot_result.get("aria_snapshot", [])
            if aria_snapshot_result.get("status") != "success":
                res["aria_snapshot_message"] = aria_snapshot_result.get(
                    "message", "ARIA Snapshot取得失敗"
                )
        except queue.Empty as e:
            add_debug_log(
                f"browser.click_element: ARIA Snapshot取得エラー: {e}", level="WARNING"
            )
        except RuntimeError as e:
            add_debug_log(
                f"browser.click_element: ARIA Snapshot取得ランタイムエラー: {e}",
                level="WARNING",
            )
        return res
    except queue.Empty:
        add_debug_log("browser.click_element: タイムアウト", level="ERROR")
        error_res = {
            "status": "error",
            "message": "クリックタイムアウト",
            "ref_id": ref_id,
        }
        selector = f"[data-ref-id='ref-{ref_id}']"
        error_res["selector"] = selector
        try:
            aria_res = get_aria_snapshot()
            error_res["aria_snapshot"] = aria_res.get("aria_snapshot", [])
            if aria_res.get("status") != "success":
                error_res["aria_snapshot_message"] = aria_res.get(
                    "message", "ARIA Snapshot取得失敗"
                )
            elements = error_res.get("aria_snapshot", [])
            element_info = next(
                (e for e in elements if e.get("ref_id") == ref_id), None
            )
            error_res["element"] = element_info
        except queue.Empty as e:
            error_res["aria_snapshot_message"] = (
                f"ARIA Snapshot取得に失敗(キュー空): {e}"
            )
        except RuntimeError as e:
            error_res["aria_snapshot_message"] = (
                f"ARIA Snapshot取得に失敗(ランタイムエラー): {e}"
            )
        return error_res


def input_text(text: str, ref_id: int) -> dict[str, Any]:
    """指定した要素 (ref_idで特定) にテキストを入力します。

    Args:
        text: 入力するテキスト
        ref_id: 要素の参照ID (数値、get_aria_snapshot で取得したもの)

    Returns:
        操作結果の辞書
    """
    if ref_id is None:
        add_debug_log("browser.input_text: ref_idが指定されていません")
        return {"status": "error", "message": "要素を特定するref_idが必要です"}
    if text is None:
        add_debug_log("browser.input_text: テキストが指定されていません")
        return {"status": "error", "message": "入力するテキストが必要です"}

    add_debug_log(f"browser.input_text: ref_id={ref_id}にテキスト '{text}' を入力")
    _ensure_worker_initialized()
    _cmd_queue.put(
        {"command": "input_text", "params": {"text": text, "ref_id": ref_id}}
    )

    try:
        res = _res_queue.get()
        add_debug_log(f"browser.input_text: 応答受信 status={res.get('status')}")

        try:
            aria_snapshot_result = get_aria_snapshot()
            res["aria_snapshot"] = aria_snapshot_result.get("aria_snapshot", [])
            if aria_snapshot_result.get("status") != "success":
                res["aria_snapshot_message"] = aria_snapshot_result.get(
                    "message", "ARIA Snapshot取得失敗"
                )
        except queue.Empty as e:
            add_debug_log(
                f"browser.input_text: ARIA Snapshot取得エラー: {e}", level="WARNING"
            )
        except RuntimeError as e:
            add_debug_log(
                f"browser.input_text: ARIA Snapshot取得ランタイムエラー: {e}",
                level="WARNING",
            )
        return res
    except queue.Empty:
        add_debug_log("browser.input_text: タイムアウト", level="ERROR")
        error_res = {
            "status": "error",
            "message": "タイムアウト",
            "ref_id": ref_id,
            "text": text,
        }
        try:
            aria_snapshot_result = get_aria_snapshot()
            error_res["aria_snapshot"] = aria_snapshot_result.get("aria_snapshot", [])
            if aria_snapshot_result.get("status") != "success":
                error_res["aria_snapshot_message"] = aria_snapshot_result.get(
                    "message", "ARIA Snapshot取得失敗"
                )
        except queue.Empty:
            error_res["aria_snapshot_message"] = "ARIA Snapshot取得に失敗しました"
        return error_res


def get_current_url() -> str:
    """現在表示中のページのURLを取得します"""
    add_debug_log("browser.get_current_url: 現在のURL取得")
    _ensure_worker_initialized()
    _cmd_queue.put({"command": "get_current_url"})
    try:
        res = _res_queue.get()
        add_debug_log(f"browser.get_current_url: 応答受信 status={res.get('status')}")
        if res.get("status") == "success":
            return res.get("url", "")
        else:
            return ""
    except queue.Empty:
        add_debug_log("browser.get_current_url: タイムアウト")
        return ""


def save_cookies() -> dict[str, Any]:
    """現在のブラウザセッションのCookieを保存します"""
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


def cleanup_browser() -> dict[str, Any]:
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


async def _async_worker() -> None:
    """非同期ワーカースレッドとして Playwright を直接操作します"""
    add_debug_log("ワーカースレッド: 非同期ブラウザワーカー開始")

    screen_width, screen_height = _get_screen_size()

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        add_debug_log("ワーカースレッド: Playwrightがインポートできませんでした", level="ERROR")
        _res_queue.put(
            {"status": "error", "message": "Playwrightがインポートできませんでした"}
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
        headless=os.environ.get("HEADLESS", "false").lower() == "true",
        args=browser_launch_args,
    )

    context = await browser.new_context(
        locale="ja-JP",
        ignore_https_errors=True,
        viewport={"width": screen_width, "height": screen_height},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
            (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    )

    if os.path.exists(constants.COOKIE_FILE):
        try:
            with open(
                constants.COOKIE_FILE, "r", encoding="utf-8"
            ) as f:
                cookies = json.load(f)
            # Playwright 形式に合わせて add_cookies でセット
            await context.add_cookies(cookies)
            add_debug_log(
                f"ワーカースレッド: クッキーを読み込みました: {len(cookies)} 件"
            )
        except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
            add_debug_log(f"ワーカースレッド: クッキーの読み込みに失敗: {e}")

    # 新しいページを作成
    page = await context.new_page()

    try:
        # 初期ページとしてGoogleを開く
        try:
            add_debug_log("ワーカースレッド: 初期ページ(Google)を読み込みます")
            await page.goto(
                "https://www.google.com/",
                wait_until="networkidle",
                timeout=constants.DEFAULT_TIMEOUT_MS,
            )

            # JavaScriptを使ってウィンドウにフォーカスを当てる
            await page.evaluate(
                """() => {
                window.focus();
                document.body.click();
            }"""
            )

            add_debug_log("ワーカースレッド: 初期ページの読み込みが完了しました")
        except PlaywrightTimeoutError as e:
            add_debug_log(
                f"ワーカースレッド: 初期ページの読み込みでエラーが発生しました: {e}"
            )
        except Exception as e:
            add_debug_log(
                f"ワーカースレッド: 初期ページの読み込みで予期せぬエラーが発生しました: {e}"
            )

        # コマンド処理ループ
        while True:
            try:
                cmd = _cmd_queue.get(block=False)
                command = cmd.get("command")
                params = cmd.get("params", {})

                if command == "quit":
                    # ブラウザ終了コマンド
                    add_debug_log("ワーカースレッド: 終了コマンドを受け取りました")
                    _res_queue.put(
                        {"status": "success", "message": "ブラウザを終了しました"}
                    )
                    break

                elif command == "get_aria_snapshot":
                    # ページのARIA Snapshotを取得
                    add_debug_log("ワーカースレッド: ARIA Snapshot取得")
                    try:
                        # DOM読み込み待ち
                        await page.wait_for_load_state(
                            "domcontentloaded", timeout=constants.DEFAULT_TIMEOUT_MS
                        )

                        # aria-snapshotを取得 (JavaScript評価)
                        aria_snapshot = await page.evaluate(
                            """() => {
                            const snapshotResult = [];
                            let refIdCounter = 1;
                            let errorCount = 0; // エラーカウント用
                            
                            try {
                                // ドキュメント内のすべての対話可能な要素を取得
                                const interactiveElements = document.querySelectorAll('button, a, input, select, textarea, [role="button"], [role="link"], [role="checkbox"], [role="radio"], [role="tab"], [role="combobox"], [role="textbox"], [role="searchbox"]');
                                
                                interactiveElements.forEach(element => {
                                    try { // 個々の要素処理のエラーハンドリング開始
                                        // 要素のロールを判断
                                        let role = element.getAttribute('role');
                                        if (!role) {
                                            // HTMLタグに基づいてロールを推定
                                            switch (element.tagName.toLowerCase()) {
                                                case 'button': role = 'button'; break;
                                                case 'a': role = 'link'; break;
                                                case 'input':
                                                    switch (element.type) {
                                                        case 'text': role = 'textbox'; break;
                                                        case 'checkbox': role = 'checkbox'; break;
                                                        case 'radio': role = 'radio'; break;
                                                        case 'search': role = 'searchbox'; break;
                                                        default: role = element.type; break;
                                                    }
                                                    break;
                                                case 'select': role = 'combobox'; break;
                                                case 'textarea': role = 'textbox'; break;
                                                default: role = 'unknown'; break;
                                            }
                                        }
                                        
                                        // 要素のテキスト内容やラベル、名前を取得
                                        let name = '';
                                        
                                        // aria-labelやaria-labelledbyを優先
                                        if (element.hasAttribute('aria-label')) {
                                            name = element.getAttribute('aria-label');
                                        } else if (element.hasAttribute('aria-labelledby')) {
                                            const labelledById = element.getAttribute('aria-labelledby');
                                            const labelElement = document.getElementById(labelledById);
                                            if (labelElement) {
                                                name = labelElement.textContent.trim();
                                            }
                                        } else if (element.hasAttribute('placeholder')) {
                                            name = element.getAttribute('placeholder');
                                        } else if (element.hasAttribute('name')) {
                                            name = element.getAttribute('name');
                                        } else if (element.hasAttribute('title')) {
                                            name = element.getAttribute('title');
                                        } else if (element.hasAttribute('alt')) {
                                            name = element.getAttribute('alt');
                                        } else {
                                            // テキストコンテンツを取得
                                            name = element.textContent.trim();
                                            
                                            // 入力要素の場合、関連するラベルを探す
                                            if (element.tagName.toLowerCase() === 'input' && element.id) {
                                                const labels = document.querySelectorAll(`label[for="${element.id}"]`);
                                                if (labels.length > 0) {
                                                    name = labels[0].textContent.trim();
                                                }
                                            }
                                        }
                                        
                                        // 一意のref-idを生成（数値）と属性用文字列
                                        const refIdValue = refIdCounter++;
                                        const refIdAttr = `ref-${refIdValue}`;
                                        
                                        // 要素にカスタムデータ属性としてref-idを付与 (ref-{数字} 形式)
                                        element.setAttribute('data-ref-id', refIdAttr);
                                        
                                        // 要素の可視性をチェック
                                        const rect = element.getBoundingClientRect();
                                        const isVisible = rect.width > 0 && rect.height > 0 && 
                                                         window.getComputedStyle(element).visibility !== 'hidden' &&
                                                         window.getComputedStyle(element).display !== 'none';
                                        
                                        // disabled または readonly 要素は除外
                                        const isDisabled = element.disabled === true || element.hasAttribute('disabled');
                                        const isReadOnly = element.readOnly === true || element.hasAttribute('readonly');
                                        
                                        // スナップショットに追加 (role, name, ref_id のみ)
                                        // 操作可能でvisibleかつrole!==unknownの場合のみ追加
                                        if (!isDisabled && !isReadOnly && isVisible && role !== 'unknown') {
                                            snapshotResult.push({
                                                role: role,
                                                name: name || 'Unnamed Element', // nameが空の場合の代替テキスト
                                                ref_id: refIdValue // 数値のref_idを返す
                                            });
                                        }
                                    } catch (el_error) {
                                        // 個々の要素処理でエラーが発生しても、他の要素の処理を続ける
                                        console.error('Error processing element:', element, el_error);
                                        errorCount++;
                                    }
                                }); // forEach end
                            } catch (main_error) {
                                // querySelectorAllなどでエラーが発生した場合
                                console.error('Error during main snapshot process:', main_error);
                                // エラーが発生したことを示す情報を返す
                                return { error: `Snapshot process error: ${main_error.message}`, errorCount: errorCount, snapshot: snapshotResult };
                            }
                            
                            // スナップショット本体とエラーカウントを返す
                            return { snapshot: snapshotResult, errorCount: errorCount }; 
                        }"""
                        )

                        # evaluateの結果からスナップショット本体とエラー情報を分離
                        snapshot_data = aria_snapshot.get("snapshot", [])
                        error_count = aria_snapshot.get("errorCount", 0)
                        process_error = aria_snapshot.get("error", None)

                        if process_error:
                            add_debug_log(
                                f"ワーカースレッド: JavaScript実行中にエラー発生: {process_error}"
                            )
                        if error_count > 0:
                            add_debug_log(
                                f"ワーカースレッド: スナップショット取得中に {error_count} 件の要素処理エラーが発生しました。"
                            )

                        _res_queue.put(
                            {
                                "status": "success",
                                "message": f"ARIA Snapshot取得成功 ({len(snapshot_data)} 要素取得、{error_count} エラー)",
                                "aria_snapshot": snapshot_data,  # スナップショット本体のみを返す
                            }
                        )
                    except PlaywrightTimeoutError as e:
                        current_url = "不明"
                        try:
                            current_url = page.url
                        except Exception as url_e:
                            add_debug_log(
                                f"ワーカースレッド: ARIA Snapshot取得エラー時のURL取得失敗: {url_e}"
                            )
                        error_msg = f"ARIA Snapshot取得エラー: {e}"
                        add_debug_log(
                            f"ワーカースレッド: {error_msg} (URL: {current_url})"
                        )
                        _res_queue.put({"status": "error", "message": error_msg})
                        # デバッグモード時に停止
                        if is_debug_mode():
                            debug_pause("ARIA Snapshot取得エラーで停止")

                elif command == "click_element":
                    # ref_idで要素を特定してクリック
                    ref_id = params.get("ref_id")  # 数値で受け取る
                    add_debug_log(f"ワーカースレッド: 要素クリック (ref_id): {ref_id}")
                    if ref_id is None:  # 数値なので None チェック
                        _res_queue.put(
                            {
                                "status": "error",
                                "message": "要素を特定するためのref_idが不足しています",
                            }
                        )
                        continue
                    try:
                        selector = f"[data-ref-id='ref-{ref_id}']"  # セレクタ構築時に "ref-" を付加
                        add_debug_log(
                            f"ワーカースレッド: クリック対象セレクタ: {selector}"
                        )
                        locator = page.locator(selector)
                        # クリック試行（自動スクロール込み）。ビュー外エラー時はバウンディングボックス取得→window.scrollBy→scrollIntoView→再試行→forceクリック
                        try:
                            await locator.click(
                                timeout=constants.DEFAULT_TIMEOUT_MS
                            )
                        except PlaywrightTimeoutError as te_click:
                            add_debug_log("クリック操作タイムアウト", level="ERROR")
                            snapshot_list = await _take_aria_snapshot(page)
                            _res_queue.put(
                                {
                                    "status": "error",
                                    "message": f"クリックタイムアウト (ref_id={ref_id}): {te_click}",
                                    "aria_snapshot": snapshot_list,
                                }
                            )
                            continue
                        except Exception as e_click:
                            # fallback branch
                            msg = str(e_click)
                            if "outside of the viewport" in msg:
                                add_debug_log(
                                    "要素がビューポート外: 自動スクロール＆再試行を実行",
                                    level="WARNING",
                                )
                                # バウンディングボックスを取得
                                box = await locator.bounding_box()
                                # ビューポート高さを取得
                                vp_info = await page.evaluate(
                                    "() => ({height: window.innerHeight})"
                                )
                                if box and isinstance(vp_info, dict):
                                    y_coord, height_val, vp_h = (
                                        box.get("y", 0),
                                        box.get("height", 0),
                                        vp_info.get("height", 0),
                                    )
                                    # 要素位置に応じたスクロール量計算
                                    scroll_amt = 0
                                    if y_coord < 0:
                                        scroll_amt = y_coord - 20
                                    elif y_coord + height_val > vp_h:
                                        scroll_amt = y_coord + height_val - vp_h + 20

                                    if scroll_amt:
                                        add_debug_log(
                                            f"window.scrollBy(0, {scroll_amt}) でスクロール",
                                            level="DEBUG",
                                        )
                                        await page.evaluate(
                                            f"() => window.scrollBy(0, {scroll_amt})"
                                        )
                                # 要素を中央に配置
                                await locator.evaluate(
                                    "el => el.scrollIntoView({block: 'center', inline: 'center'})"
                                )
                                # 再試行
                                try:
                                    await locator.click(
                                        timeout=constants.DEFAULT_TIMEOUT_MS
                                    )
                                except Exception:
                                    add_debug_log(
                                        "再試行失敗: forceオプションで強制クリックを実行",
                                        level="WARNING",
                                    )
                                    await locator.click(
                                        force=True, timeout=constants.DEFAULT_TIMEOUT_MS
                                    )
                            else:
                                raise
                        _res_queue.put(
                            {
                                "status": "success",
                                "message": f"ref_id={ref_id} (selector={selector}) の要素をクリックしました",
                            }
                        )
                    except Exception as e:
                        # locator.bounding_box() やその他の予期せぬエラー
                        current_url = "不明"
                        try:
                            current_url = page.url
                        except Exception as url_e:
                            add_debug_log(
                                f"ワーカースレッド: 要素クリック時の予期せぬエラーでのURL取得失敗: {url_e}"
                            )
                        error_msg = (
                            f"要素クリック時の予期せぬエラー (ref_id={ref_id}, "
                            f"selector=[data-ref-id='ref-{ref_id}']): {e}"
                        )
                        add_debug_log(
                            f"ワーカースレッド: {error_msg} (URL: {current_url})"
                        )
                        tb = traceback.format_exc()
                        _res_queue.put(
                            {"status": "error", "message": error_msg, "traceback": tb}
                        )
                        if is_debug_mode():
                            debug_pause("要素クリック時の予期せぬエラーで停止")

                elif command == "input_text":
                    # ref_idで要素を特定してテキスト入力
                    text = params.get("text")
                    ref_id = params.get("ref_id")  # 数値で受け取る
                    add_debug_log(
                        f"ワーカースレッド: テキスト入力 (ref_id={ref_id}, text='{text}')"
                    )

                    if ref_id is None:  # 数値なので None チェック
                        _res_queue.put(
                            {
                                "status": "error",
                                "message": "要素を特定するためのref_idが不足しています",
                            }
                        )
                        continue
                    if text is None:
                        _res_queue.put(
                            {
                                "status": "error",
                                "message": "入力するテキストが指定されていません",
                            }
                        )
                        continue

                    try:
                        selector = f"[data-ref-id='ref-{ref_id}']"  # セレクタ構築時に "ref-" を付加
                        add_debug_log(
                            f"ワーカースレッド: テキスト入力対象セレクタ: {selector}"
                        )
                        locator = page.locator(selector)
                        # Locator API を使用して入力。自動待機やスクロールが組み込まれている
                        # クリアしてから入力
                        try:
                            await locator.fill(
                                "", timeout=constants.DEFAULT_TIMEOUT_MS
                            )
                            await locator.fill(
                                text, timeout=constants.DEFAULT_TIMEOUT_MS
                            )
                            await locator.press(
                                "Enter", timeout=constants.DEFAULT_TIMEOUT_MS
                            )
                        except PlaywrightTimeoutError as te_input:
                            add_debug_log("テキスト入力タイムアウト", level="ERROR")
                            snapshot_list = await _take_aria_snapshot(page)
                            _res_queue.put(
                                {
                                    "status": "error",
                                    "message": f"テキスト入力タイムアウト (ref_id={ref_id}): {te_input}",
                                    "aria_snapshot": snapshot_list,
                                }
                            )
                            continue
                        _res_queue.put(
                            {
                                "status": "success",
                                "message": (
                                    f"ref_id={ref_id} (selector={selector}) "
                                    f"の要素にテキスト '{text}' を入力しました"
                                ),
                            }
                        )
                    except Exception as e:
                        # locator.fill や locator.press("Enter") での予期せぬエラー
                        current_url = "不明"
                        try:
                            current_url = page.url
                        except Exception as url_e:
                            add_debug_log(
                                f"ワーカースレッド: テキスト入力時の予期せぬエラーでのURL取得失敗: {url_e}"
                            )
                        error_msg = (
                            f"テキスト入力時の予期せぬエラー (ref_id={ref_id}, "
                            f"selector=[data-ref-id='ref-{ref_id}'], text='{text}'): {e}"
                        )
                        add_debug_log(
                            f"ワーカースレッド: {error_msg} (URL: {current_url})"
                        )
                        _res_queue.put({"status": "error", "message": error_msg})
                        if is_debug_mode():
                            debug_pause("テキスト入力時の予期せぬエラーで停止")

                else:
                    # 未知のコマンド
                    add_debug_log(f"ワーカースレッド: 未知のコマンド: {command}")
                    _res_queue.put(
                        {"status": "error", "message": f"未知のコマンド: {command}"}
                    )

            except queue.Empty:
                # コマンドがない場合は少し待機
                await asyncio.sleep(0.1)
            except Exception as e:
                # その他の例外
                add_debug_log(f"ワーカースレッド: 予期せぬエラー: {e}")
                try:
                    _res_queue.put(
                        {"status": "error", "message": f"予期せぬエラー: {e}"}
                    )
                except queue.Full:
                    pass

    finally:
        # 終了処理
        add_debug_log("ワーカースレッド: 終了処理")
        try:
            if 'browser' in locals():
                await browser.close()
        except Exception as e:
            add_debug_log(f"ワーカースレッド: 終了処理エラー: {e}")


async def _take_aria_snapshot(page: Any) -> list[dict[str, Any]]:
    """非同期で現在ページの簡易ARIA Snapshot(list)を取得します。

    ワーカー内部から使用するため、`get_aria_snapshot` キューコマンドを利用しません。
    失敗時は空リストを返します。
    """
    try:
        # DOMContentLoaded を待つ
        try:
            await page.wait_for_load_state(
                "domcontentloaded", timeout=constants.DEFAULT_TIMEOUT_MS
            )
        except PlaywrightTimeoutError:
            # ページ読み込みが完了しなくてもスナップショット取得を試みる
            pass

        aria_snapshot = await page.evaluate(
            """() => {
            const snapshotResult = [];
            let refIdCounter = 1;
            const interactiveElements = document.querySelectorAll('button, a, input, select, textarea, [role="button"], [role="link"], [role="checkbox"], [role="radio"], [role="tab"], [role="combobox"], [role="textbox"], [role="searchbox"]');
            interactiveElements.forEach(element => {
                let role = element.getAttribute('role');
                if (!role) {
                    switch (element.tagName.toLowerCase()) {
                        case 'button': role = 'button'; break;
                        case 'a': role = 'link'; break;
                        case 'input':
                            switch (element.type) {
                                case 'text': role = 'textbox'; break;
                                case 'checkbox': role = 'checkbox'; break;
                                case 'radio': role = 'radio'; break;
                                case 'search': role = 'searchbox'; break;
                                default: role = element.type; break;
                            }
                            break;
                        case 'select': role = 'combobox'; break;
                        case 'textarea': role = 'textbox'; break;
                        default: role = 'unknown'; break;
                    }
                }

                let name = '';
                if (element.hasAttribute('aria-label')) {
                    name = element.getAttribute('aria-label');
                } else if (element.hasAttribute('placeholder')) {
                    name = element.getAttribute('placeholder');
                } else if (element.hasAttribute('name')) {
                    name = element.getAttribute('name');
                } else {
                    name = (element.textContent || '').trim();
                }

                const refIdValue = refIdCounter++;
                element.setAttribute('data-ref-id', `ref-${refIdValue}`);

                const rect = element.getBoundingClientRect();
                const isVisible = rect.width > 0 && rect.height > 0;

                if (isVisible && role !== 'unknown') {
                    snapshotResult.push({ role, name, ref_id: refIdValue });
                }
            });
            return snapshotResult;
        }"""
        )

        return aria_snapshot if isinstance(aria_snapshot, list) else []
    except PlaywrightTimeoutError as e:
        add_debug_log(f"_take_aria_snapshot 失敗: {e}", level="WARNING")
        return []
    except Exception as e:
        add_debug_log(f"_take_aria_snapshot 予期せぬ失敗: {e}", level="WARNING")
        return []
