import threading
import queue
import time
import sys
import asyncio
import os
import json
from agent.utils import add_debug_log, debug_pause, is_debug_mode
import traceback  # トレースバック情報を取得するために追加

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

async def _async_worker():
    """非同期ワーカースレッドとして Playwright と browser-use API を起動・操作します"""
    add_debug_log("ワーカースレッド: 非同期ブラウザワーカー開始")
    
    # browser-useライブラリをインポート
    from browser_use.browser.browser import Browser, BrowserConfig
    from browser_use.browser.context import BrowserContextConfig
    from playwright.async_api import async_playwright

    # Browser設定
    browser_config = BrowserConfig(
        headless=False,
        browser_binary_path=None,  # システムのChromeを使用
        disable_security=True,  # iframe対応のために必要
        deterministic_rendering=False,
        extra_browser_args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins",
            "--disable-site-isolation-trials"
        ]
    )

    # Context設定
    context_config = BrowserContextConfig(
        locale="ja-JP",
        ignore_https_errors=True,
        browser_window_size={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    # Cookieファイルがあれば読み込む
    if os.path.exists(_COOKIE_FILE):
        try:
            with open(_COOKIE_FILE, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            context_config.cookies = cookies
            add_debug_log(f"ワーカースレッド: クッキーを読み込みました: {len(cookies)} 件")
        except Exception as e:
            add_debug_log(f"ワーカースレッド: クッキーの読み込みに失敗: {e}")

    # ブラウザを起動
    add_debug_log("ワーカースレッド: ブラウザを起動します")
    browser = None
    page = None

    try:
        # browser-useを使用してブラウザを起動
        browser = Browser(config=browser_config)
        context = await browser.new_context(config=context_config)
        
        # ページを開く
        page = await context.get_current_page()
        
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
                        
                        # aria-snapshotを取得
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
                                        
                                        // スナップショットに追加 (role, name, ref_id のみ)
                                        // roleがunknownでなく、nameが空でも追加する（代替テキストを設定）
                                        if (isVisible && role !== 'unknown') {
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
                                // エラーが発生したことを示す情報を返すことも検討
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
                        # Locator API を使用してクリック。自動待機やスクロールが組み込まれている
                        await locator.click(timeout=10000) # タイムアウトを設定
                        _res_queue.put({"status": "success", "message": f"ref_id={ref_id} (selector={selector}) の要素をクリックしました"})
                    except Exception as e:
                        current_url = "不明"
                        try:
                            current_url = page.url
                        except Exception as url_e:
                            add_debug_log(f"ワーカースレッド: 要素クリックエラー時のURL取得失敗: {url_e}")
                        error_msg = f"要素クリックエラー (ref_id={ref_id}, selector=[data-ref-id='ref-{ref_id}']): {e}"
                        add_debug_log(f"ワーカースレッド: {error_msg} (URL: {current_url})")
                        _res_queue.put({"status": "error", "message": error_msg})
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
                        cookies = await context.get_cookies()
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


def _ensure_worker_initialized():
    """ワーカースレッドが初期化されていることを確認します"""
    if not _thread_started:
        return initialize_browser()
    return {"status": "success", "message": "ブラウザワーカーは既に初期化されています"} 