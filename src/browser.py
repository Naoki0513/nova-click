"""
ブラウザ操作モジュール

Playwright を使用したブラウザ操作の実装を提供します。
以下の機能を含みます:
- ブラウザの初期化と終了
- 要素のクリック、テキスト入力
- ARIA Snapshotの取得
- URLへの移動
"""

import threading
import queue
import time
import sys
import asyncio
import os
import json
import traceback
import logging
from typing import Dict, Any, List, Optional, Tuple

# 相対インポートに修正
from .utils import add_debug_log, debug_pause, is_debug_mode

# Windows での ProactorEventLoop 設定
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# コマンド／レスポンス用キュー
_cmd_queue = queue.Queue()
_res_queue = queue.Queue()
_thread_started = False
_browser_thread = None

# Cookie ファイルパス
_COOKIE_FILE = "browser_cookies.json"

# 操作可能な要素の role リスト (click_element と input_text がサポートする要素のみ)
ALLOWED_ROLES = ['button', 'link', 'textbox', 'searchbox', 'combobox']

# ブラウザ操作関連のロガー
logger = logging.getLogger(__name__)

# 画面解像度取得用の関数を追加
def _get_screen_size() -> Tuple[int, int]:
    """デバイスの画面解像度を取得して返します。"""
    try:
        if sys.platform == "win32":
            from ctypes import windll
            width = windll.user32.GetSystemMetrics(0)
            height = windll.user32.GetSystemMetrics(1)
        else:
            import tkinter
            root = tkinter.Tk()
            width = root.winfo_screenwidth()
            height = root.winfo_screenheight()
            root.destroy()
        add_debug_log(f"取得した画面解像度: {width}x{height}")
        return width, height
    except Exception as e:
        add_debug_log(f"スクリーンサイズ取得エラー: {e}", level="WARNING")
        return 1920, 1080

def _worker_thread():
    """ブラウザワーカーのメインスレッド処理"""
    add_debug_log("ワーカースレッド: スレッド開始")
    asyncio.run(_async_worker())
    add_debug_log("ワーカースレッド: スレッド終了")


def initialize_browser():
    """ブラウザワーカースレッドを初期化して開始します"""
    global _thread_started, _browser_thread
    
    if _thread_started:
        add_debug_log("initialize_browser: すでにスレッドが開始されています")
        return {"status": "success", "message": "ブラウザワーカーはすでに初期化されています"}
    
    add_debug_log("initialize_browser: ブラウザワーカースレッドを開始")
    _browser_thread = threading.Thread(target=_worker_thread, daemon=True)
    _browser_thread.start()
    _thread_started = True
    
    # ブラウザが起動するまで少し待機
    time.sleep(2.0)
    add_debug_log("initialize_browser: ブラウザワーカースレッド開始完了")
    
    return {"status": "success", "message": "ブラウザワーカーを初期化しました"}


def _ensure_worker_initialized():
    """ワーカースレッドが初期化されていることを確認します"""
    if not _thread_started:
        return initialize_browser()
    return {"status": "success", "message": "ブラウザワーカーは既に初期化されています"}


def get_aria_snapshot(wait_time: float = 0.5):
    """ブラウザワーカースレッドからARIA Snapshot情報を取得し、
    button, link, combobox要素などをフラットリストで返します。"""
    if wait_time > 0:
        add_debug_log(f"browser.get_aria_snapshot: {wait_time}秒待機してからARIA Snapshot取得")
        time.sleep(wait_time)  # ARIA Snapshot取得前に指定された時間だけ待機

    add_debug_log("browser.get_aria_snapshot: ARIAスナップショット取得要求送信")
    _ensure_worker_initialized()
    _cmd_queue.put({'command': 'get_aria_snapshot'})
    try:
        res = _res_queue.get(timeout=10.0)
        add_debug_log(f"browser.get_aria_snapshot: 応答受信 status={res.get('status')}")
        
        if res.get('status') == 'success':
            # 操作可能な要素のスナップショットのみを残す
            raw_snapshot = res.get('aria_snapshot', [])
            filtered_snapshot = [e for e in raw_snapshot if e.get('role') in ALLOWED_ROLES]
            return {
                'status': 'success',
                'aria_snapshot': filtered_snapshot,
                'message': res.get('message', 'ARIA Snapshot取得成功')
            }
        else:
            error_msg = res.get('message', '不明なエラー')
            add_debug_log(f"browser.get_aria_snapshot: エラー {error_msg}")
            return {
                'status': 'error',
                'aria_snapshot': [],
                'message': f"ARIA Snapshot取得エラー: {error_msg}"
            }
    except queue.Empty:
        add_debug_log("browser.get_aria_snapshot: タイムアウト", level="ERROR")
        # タイムアウト時の状態出力と一時停止
        current_url = get_current_url()
        add_debug_log(f"browser.get_aria_snapshot: タイムアウト URL={current_url}", level="ERROR")
        if is_debug_mode():
            debug_pause("ARIA Snapshot取得タイムアウトで停止")
        return {
            'status': 'error',
            'aria_snapshot': [],
            'message': 'ARIA Snapshot取得タイムアウト',
            'current_url': current_url
        }


def goto_url(url: str) -> Dict[str, Any]:
    """指定したURLに移動します"""
    add_debug_log(f"browser.goto_url: URL移動: {url}", level="DEBUG")
    _ensure_worker_initialized()
    _cmd_queue.put({'command': 'goto', 'params': {'url': url}})
    try:
        res = _res_queue.get(timeout=30.0)
        add_debug_log(f"browser.goto_url: 応答受信: {res}", level="DEBUG")
        return res
    except queue.Empty:
        add_debug_log("browser.goto_url: タイムアウト", level="ERROR")
        return {'status': 'error', 'message': 'タイムアウト (応答なし)'}


def click_element(ref_id: int) -> Dict[str, Any]:
    """指定した要素 (ref_idで特定) をクリックします。
    
    Args:
        ref_id: 要素の参照ID (数値、get_aria_snapshot で取得したもの)
    
    Returns:
        操作結果の辞書
    """
    if ref_id is None:
        add_debug_log("browser.click_element: ref_idが指定されていません")
        return {'status': 'error', 'message': '要素を特定するref_idが必要です'}
    
    # クリック実行ログ
    add_debug_log(f"browser.click_element: ref_id={ref_id}の要素をクリック")
    _ensure_worker_initialized()
    _cmd_queue.put({'command': 'click_element', 'params': {'ref_id': ref_id}})
    
    try:
        res = _res_queue.get(timeout=10.0)
        add_debug_log(f"browser.click_element: 応答受信 status={res.get('status')}")
        # クリック後のページ状態を取得してARIA Snapshotを返す
        try:
            aria_snapshot_result = get_aria_snapshot(wait_time=0.5)
            res['aria_snapshot'] = aria_snapshot_result.get('aria_snapshot', [])
            if aria_snapshot_result.get('status') != 'success':
                res['aria_snapshot_message'] = aria_snapshot_result.get('message', 'ARIA Snapshot取得失敗')
        except Exception as e:
            add_debug_log(f"browser.click_element: ARIA Snapshot取得エラー: {e}", level="WARNING")
        return res
    except queue.Empty:
        add_debug_log("browser.click_element: タイムアウト", level="ERROR")
        current_url = get_current_url()
        add_debug_log(f"browser.click_element: タイムアウト URL={current_url}, ref_id={ref_id}", level="ERROR")
        if is_debug_mode():
            debug_pause("クリックタイムアウトで停止")
        error_res = {
            'status': 'error',
            'message': 'クリックタイムアウト',
            'ref_id': ref_id,
            'current_url': current_url
        }
        # クリックに使用したセレクタを追加
        selector = f"[data-ref-id='ref-{ref_id}']"
        error_res['selector'] = selector
        try:
            aria_res = get_aria_snapshot(wait_time=0.5)
            error_res['aria_snapshot'] = aria_res.get('aria_snapshot', [])
            if aria_res.get('status') != 'success':
                error_res['aria_snapshot_message'] = aria_res.get('message', 'ARIA Snapshot取得失敗')
            # 対象要素情報を追加
            elements = error_res.get('aria_snapshot', [])
            element_info = next((e for e in elements if e.get('ref_id') == ref_id), None)
            error_res['element'] = element_info
        except Exception as e:
            error_res['aria_snapshot_message'] = f"ARIA Snapshot取得に失敗: {e}"
        return error_res


def input_text(text: str, ref_id: int) -> Dict[str, Any]:
    """指定した要素 (ref_idで特定) にテキストを入力します。
    
    Args:
        text: 入力するテキスト
        ref_id: 要素の参照ID (数値、get_aria_snapshot で取得したもの)
    
    Returns:
        操作結果の辞書
    """
    if ref_id is None:
        add_debug_log("browser.input_text: ref_idが指定されていません")
        return {'status': 'error', 'message': '要素を特定するref_idが必要です'}
    if text is None:
        add_debug_log("browser.input_text: テキストが指定されていません")
        return {'status': 'error', 'message': '入力するテキストが必要です'}
        
    add_debug_log(f"browser.input_text: ref_id={ref_id}にテキスト '{text}' を入力")
    _ensure_worker_initialized()
    _cmd_queue.put({'command': 'input_text', 'params': {'text': text, 'ref_id': ref_id}})
    
    try:
        res = _res_queue.get(timeout=10.0)
        add_debug_log(f"browser.input_text: 応答受信 status={res.get('status')}")
        
        # 操作実行後のページ状態を取得しARIA Snapshotを返す
        try:
            aria_snapshot_result = get_aria_snapshot(wait_time=0.5)
            res['aria_snapshot'] = aria_snapshot_result.get('aria_snapshot', [])
            if aria_snapshot_result.get('status') != 'success':
                res['aria_snapshot_message'] = aria_snapshot_result.get('message', 'ARIA Snapshot取得失敗')
        except Exception as e:
            add_debug_log(f"browser.input_text: ARIA Snapshot取得エラー: {e}", level="WARNING")
        return res
    except queue.Empty:
        add_debug_log("browser.input_text: タイムアウト", level="ERROR")
        # タイムアウト時の状態出力と一時停止
        current_url = get_current_url()
        add_debug_log(f"browser.input_text: タイムアウト URL={current_url}, ref_id={ref_id}, text='{text}'", level="ERROR")
        if is_debug_mode():
            debug_pause("テキスト入力タイムアウトで停止")
        error_res = {
            'status': 'error',
            'message': 'タイムアウト',
            'ref_id': ref_id,
            'text': text,
            'current_url': current_url
        }
        # エラー時にもARIA Snapshotを取得して含める
        try:
            aria_snapshot_result = get_aria_snapshot(wait_time=0.5)
            error_res['aria_snapshot'] = aria_snapshot_result.get('aria_snapshot', [])
            if aria_snapshot_result.get('status') != 'success':
                error_res['aria_snapshot_message'] = aria_snapshot_result.get('message', 'ARIA Snapshot取得失敗')
        except:
            error_res['aria_snapshot_message'] = "ARIA Snapshot取得に失敗しました"
        return error_res


def get_current_url() -> str:
    """現在表示中のページのURLを取得します"""
    add_debug_log("browser.get_current_url: 現在のURL取得")
    _ensure_worker_initialized()
    _cmd_queue.put({'command': 'get_current_url'})
    try:
        res = _res_queue.get(timeout=5.0)
        add_debug_log(f"browser.get_current_url: 応答受信 status={res.get('status')}")
        if res.get('status') == 'success':
            return res.get('url', '')
        else:
            return ''
    except queue.Empty:
        add_debug_log("browser.get_current_url: タイムアウト")
        return ''


def save_cookies() -> Dict[str, Any]:
    """現在のブラウザセッションのCookieを保存します"""
    add_debug_log("browser.save_cookies: Cookie保存")
    _ensure_worker_initialized()
    _cmd_queue.put({'command': 'save_cookies'})
    try:
        res = _res_queue.get(timeout=5.0)
        add_debug_log(f"browser.save_cookies: 応答受信 status={res.get('status')}")
        return res
    except queue.Empty:
        add_debug_log("browser.save_cookies: タイムアウト")
        return {'status': 'error', 'message': 'タイムアウト'}


def cleanup_browser():
    """ブラウザを終了します"""
    add_debug_log("browser.cleanup_browser: ブラウザ終了")
    _ensure_worker_initialized()
    _cmd_queue.put({'command': 'quit'})
    try:
        res = _res_queue.get(timeout=10.0)
        add_debug_log(f"browser.cleanup_browser: 応答受信 status={res.get('status')}")
        return res
    except queue.Empty:
        add_debug_log("browser.cleanup_browser: タイムアウト")
        return {'status': 'error', 'message': 'タイムアウト'}

async def _async_worker():
    """非同期ワーカースレッドとして Playwright を直接操作します"""
    add_debug_log("ワーカースレッド: 非同期ブラウザワーカー開始")

    # 画面解像度を取得
    screen_width, screen_height = _get_screen_size()

    # --- Playwright 起動 ---
    from playwright.async_api import async_playwright

    playwright = await async_playwright().start()

    # Chromium ブラウザを起動 (従来の BrowserConfig 相当の設定)
    browser_launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins",
        "--disable-site-isolation-trials",
        "--start-maximized",
        "--start-fullscreen",
        f"--window-size={screen_width},{screen_height}"
    ]

    browser = await playwright.chromium.launch(
        headless=False,
        args=browser_launch_args,
    )

    # コンテキストを作成 (従来の BrowserContextConfig 相当)
    context = await browser.new_context(
        locale="ja-JP",
        ignore_https_errors=True,
        viewport={"width": screen_width, "height": screen_height},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    )

    # Cookieファイルがあれば読み込む
    if os.path.exists(_COOKIE_FILE):
        try:
            with open(_COOKIE_FILE, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            # Playwright 形式に合わせて add_cookies でセット
            await context.add_cookies(cookies)
            add_debug_log(f"ワーカースレッド: クッキーを読み込みました: {len(cookies)} 件")
        except Exception as e:
            add_debug_log(f"ワーカースレッド: クッキーの読み込みに失敗: {e}")

    # 新しいページを作成
    page = await context.new_page()

    try:
        # 初期ページとしてGoogleを開く
        try:
            add_debug_log("ワーカースレッド: 初期ページ(Google)を読み込みます")
            await page.goto("https://www.google.com/", wait_until="networkidle", timeout=30000)
            
            # JavaScriptを使ってウィンドウにフォーカスを当てる
            await page.evaluate("""() => {
                window.focus();
                document.body.click();
            }""")
            
            add_debug_log("ワーカースレッド: 初期ページの読み込みが完了しました")
        except Exception as e:
            add_debug_log(f"ワーカースレッド: 初期ページの読み込みでエラーが発生しました: {e}")
        
        # コマンド処理ループ
        while True:
            try:
                cmd = _cmd_queue.get(block=False)
                command = cmd.get("command")
                params = cmd.get("params", {})
                
                if command == "quit":
                    # ブラウザ終了コマンド
                    add_debug_log("ワーカースレッド: 終了コマンドを受け取りました")
                    _res_queue.put({"status": "success", "message": "ブラウザを終了しました"})
                    break
                
                elif command == "goto":
                    # URLに移動
                    url = params.get("url", "")
                    if not url:
                        _res_queue.put({"status": "error", "message": "URLが指定されていません"})
                        continue
                    
                    add_debug_log(f"ワーカースレッド: URL移動 {url}")
                    try:
                        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        _res_queue.put({
                            "status": "success", 
                            "message": f"ページに移動: {url}",
                            "response_status": response.status if response else None
                        })
                    except Exception as e:
                        # エラー情報とトレースバックをログ出力
                        add_debug_log(e, level="ERROR")
                        tb = traceback.format_exc()
                        add_debug_log(f"ワーカースレッド: URL移動エラー詳細\n{tb}", level="DEBUG")
                        # エラー応答にトレースバックを含める
                        error_message = f"URL移動エラー: {e}"
                        _res_queue.put({"status": "error", "message": error_message, "traceback": tb})
                        # デバッグモード時に停止
                        if is_debug_mode():
                            debug_pause("URL移動エラーで停止")
                
                elif command == "get_aria_snapshot":
                    # ページのARIA Snapshotを取得
                    add_debug_log("ワーカースレッド: ARIA Snapshot取得")
                    try:
                        # ページのDOMが読み込まれるのを少し待つ (gotoでnetworkidleは待っているはずだが念のため)
                        try:
                            await page.wait_for_load_state('domcontentloaded', timeout=5000)
                        except Exception as wait_e:
                            add_debug_log(f"ワーカースレッド: domcontentloaded 待機中にタイムアウトまたはエラー: {wait_e}")
                        
                        # aria-snapshotを取得 (JavaScript評価)
                        aria_snapshot = await page.evaluate("""() => {
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
                        }""")
                        
                        # evaluateの結果からスナップショット本体とエラー情報を分離
                        snapshot_data = aria_snapshot.get("snapshot", [])
                        error_count = aria_snapshot.get("errorCount", 0)
                        process_error = aria_snapshot.get("error", None)

                        if process_error:
                             add_debug_log(f"ワーカースレッド: JavaScript実行中にエラー発生: {process_error}")
                        if error_count > 0:
                            add_debug_log(f"ワーカースレッド: スナップショット取得中に {error_count} 件の要素処理エラーが発生しました。")
                        
                        _res_queue.put({
                            "status": "success", 
                            "message": f"ARIA Snapshot取得成功 ({len(snapshot_data)} 要素取得、{error_count} エラー)",
                            "aria_snapshot": snapshot_data # スナップショット本体のみを返す
                        })
                    except Exception as e:
                        current_url = "不明"
                        try:
                            current_url = page.url
                        except Exception as url_e:
                            add_debug_log(f"ワーカースレッド: ARIA Snapshot取得エラー時のURL取得失敗: {url_e}")
                        error_msg = f"ARIA Snapshot取得エラー: {e}"
                        add_debug_log(f"ワーカースレッド: {error_msg} (URL: {current_url})")
                        _res_queue.put({"status": "error", "message": error_msg})
                        # デバッグモードならブラウザを開いた状態で停止
                        if is_debug_mode():
                            debug_pause("ARIA Snapshot取得エラーで停止")
                
                elif command == "click_element":
                    # ref_idで要素を特定してクリック
                    ref_id = params.get("ref_id") # 数値で受け取る
                    add_debug_log(f"ワーカースレッド: 要素クリック (ref_id): {ref_id}")
                    if ref_id is None: # 数値なので None チェック
                        _res_queue.put({"status": "error", "message": "要素を特定するためのref_idが不足しています"})
                        continue
                    try:
                        selector = f"[data-ref-id='ref-{ref_id}']" # セレクタ構築時に "ref-" を付加
                        add_debug_log(f"ワーカースレッド: クリック対象セレクタ: {selector}")
                        locator = page.locator(selector)
                        # 最初のクリック試行（自動スクロール込み）。ビュー外エラー時はバウンディングボックス取得→window.scrollBy→scrollIntoView→再試行→forceクリック
                        try:
                            await locator.click(timeout=10000)
                        except Exception as e_click:
                            msg = str(e_click)
                            if "outside of the viewport" in msg:
                                add_debug_log("要素がビューポート外: 自動スクロール＆再試行を実行", level="WARNING")
                                # バウンディングボックスを取得
                                box = await locator.bounding_box()
                                # ビューポート高さを取得
                                vp = await page.evaluate("() => ({height: window.innerHeight})")
                                if box and isinstance(vp, dict):
                                    y, h, vp_h = box.get("y", 0), box.get("height", 0), vp.get("height", 0)
                                    # 要素位置に応じたスクロール量計算
                                    if y < 0:
                                        scroll_amt = y - 20
                                    elif y + h > vp_h:
                                        scroll_amt = y + h - vp_h + 20
                                    else:
                                        scroll_amt = 0
                                    if scroll_amt:
                                        add_debug_log(f"window.scrollBy(0, {scroll_amt}) でスクロール", level="DEBUG")
                                        await page.evaluate(f"() => window.scrollBy(0, {scroll_amt})")
                                # 要素を中央に配置
                                await locator.evaluate("el => el.scrollIntoView({block: 'center', inline: 'center'})")
                                # 再試行
                                try:
                                    await locator.click(timeout=10000)
                                except Exception:
                                    add_debug_log("再試行失敗: forceオプションで強制クリックを実行", level="WARNING")
                                    await locator.click(force=True, timeout=10000)
                            else:
                                raise
                        _res_queue.put({"status": "success", "message": f"ref_id={ref_id} (selector={selector}) の要素をクリックしました"})
                    except Exception as e:
                        current_url = "不明"
                        try:
                            current_url = page.url
                        except Exception as url_e:
                            add_debug_log(f"ワーカースレッド: 要素クリックエラー時のURL取得失敗: {url_e}")
                        error_msg = f"要素クリックエラー (ref_id={ref_id}, selector=[data-ref-id='ref-{ref_id}']): {e}"
                        add_debug_log(f"ワーカースレッド: {error_msg} (URL: {current_url})")
                        tb = traceback.format_exc()
                        _res_queue.put({"status": "error", "message": error_msg, "traceback": tb})
                        if is_debug_mode():
                            debug_pause("要素クリックエラーで停止")

                elif command == "input_text":
                    # ref_idで要素を特定してテキスト入力
                    text = params.get("text")
                    ref_id = params.get("ref_id") # 数値で受け取る
                    add_debug_log(f"ワーカースレッド: テキスト入力 (ref_id={ref_id}, text='{text}')")

                    if ref_id is None: # 数値なので None チェック
                        _res_queue.put({"status": "error", "message": "要素を特定するためのref_idが不足しています"})
                        continue
                    if text is None:
                        _res_queue.put({"status": "error", "message": "入力するテキストが指定されていません"})
                        continue

                    try:
                        selector = f"[data-ref-id='ref-{ref_id}']" # セレクタ構築時に "ref-" を付加
                        add_debug_log(f"ワーカースレッド: テキスト入力対象セレクタ: {selector}")
                        locator = page.locator(selector)
                        # Locator API を使用して入力。自動待機やスクロールが組み込まれている
                        # クリアしてから入力
                        await locator.fill("", timeout=10000) # fillのタイムアウト
                        await locator.fill(text, timeout=10000) # fillのタイムアウト
                        await locator.press("Enter", timeout=5000) # pressのタイムアウト
                        _res_queue.put({"status": "success", "message": f"ref_id={ref_id} (selector={selector}) の要素にテキスト '{text}' を入力しました"})
                    except Exception as e:
                        current_url = "不明"
                        try:
                            current_url = page.url
                        except Exception as url_e:
                            add_debug_log(f"ワーカースレッド: テキスト入力エラー時のURL取得失敗: {url_e}")
                        error_msg = f"テキスト入力エラー (ref_id={ref_id}, selector=[data-ref-id='ref-{ref_id}'], text='{text}'): {e}"
                        add_debug_log(f"ワーカースレッド: {error_msg} (URL: {current_url})")
                        _res_queue.put({"status": "error", "message": error_msg})
                        if is_debug_mode():
                            debug_pause("テキスト入力エラーで停止")
                
                elif command == "get_current_url":
                    # 現在のURLを取得
                    add_debug_log("ワーカースレッド: 現在のURL取得")
                    try:
                        url = page.url
                        _res_queue.put({"status": "success", "url": url})
                    except Exception as e:
                        add_debug_log(f"ワーカースレッド: URL取得エラー: {e}")
                        _res_queue.put({"status": "error", "message": f"URL取得エラー: {e}"})
                
                elif command == "save_cookies":
                    # Cookieを保存
                    add_debug_log("ワーカースレッド: Cookie保存")
                    try:
                        # Playwright BrowserContext から Cookie を取得
                        cookies = await context.cookies()
                        with open(_COOKIE_FILE, "w", encoding="utf-8") as f:
                            json.dump(cookies, f, ensure_ascii=False, indent=2)
                        _res_queue.put({"status": "success", "message": f"{len(cookies)}件のCookieを保存しました"})
                    except Exception as e:
                        add_debug_log(f"ワーカースレッド: Cookie保存エラー: {e}")
                        _res_queue.put({"status": "error", "message": f"Cookie保存エラー: {e}"})
                
                else:
                    # 未知のコマンド
                    add_debug_log(f"ワーカースレッド: 未知のコマンド: {command}")
                    _res_queue.put({"status": "error", "message": f"未知のコマンド: {command}"})
            
            except queue.Empty:
                # コマンドがない場合は少し待機
                await asyncio.sleep(0.1)
            except Exception as e:
                # その他の例外
                add_debug_log(f"ワーカースレッド: 予期せぬエラー: {e}")
                try:
                    _res_queue.put({"status": "error", "message": f"予期せぬエラー: {e}"})
                except:
                    pass

    finally:
        # 終了処理
        add_debug_log("ワーカースレッド: 終了処理")
        try:
            if browser:
                await browser.close()
        except Exception as e:
            add_debug_log(f"ワーカースレッド: 終了処理エラー: {e}")


def _worker_thread():
    """ブラウザワーカーのメインスレッド処理"""
    add_debug_log("ワーカースレッド: スレッド開始")
    asyncio.run(_async_worker())
    add_debug_log("ワーカースレッド: スレッド終了")


def initialize_browser():
    """ブラウザワーカースレッドを初期化して開始します"""
    global _thread_started, _browser_thread
    
    if _thread_started:
        add_debug_log("initialize_browser: すでにスレッドが開始されています")
        return {"status": "success", "message": "ブラウザワーカーはすでに初期化されています"}
    
    add_debug_log("initialize_browser: ブラウザワーカースレッドを開始")
    _browser_thread = threading.Thread(target=_worker_thread, daemon=True)
    _browser_thread.start()
    _thread_started = True
    
    # ブラウザが起動するまで少し待機
    time.sleep(2.0)
    add_debug_log("initialize_browser: ブラウザワーカースレッド開始完了")
    
    return {"status": "success", "message": "ブラウザワーカーを初期化しました"} 