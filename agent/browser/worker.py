import threading
import queue
import time
import sys
import asyncio
import os
import json
from agent.utils import add_debug_log

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
    # 必要なクラスをインポート
    from browser_use.browser.browser import Browser, BrowserConfig
    from browser_use.browser.context import BrowserContextConfig

    # Browser 設定
    cfg = BrowserConfig(
        headless=False,
        disable_security=False,
        deterministic_rendering=True,
    )
    browser_factory = Browser(config=cfg)
    # Playwright ブラウザ起動
    await browser_factory.get_playwright_browser()
    # コンテキスト作成（クッキー永続化、ロケール、タイムゾーン設定）
    ctx_config = BrowserContextConfig(
        cookies_file=_COOKIE_FILE,
        locale="en-US",
        timezone_id="America/New_York",
    )
    ctx = await browser_factory.new_context(config=ctx_config)
    page = await ctx.get_current_page()

    # 初期ページを開く
    await page.goto("https://www.google.com", wait_until="networkidle", timeout=30000)
    add_debug_log("ワーカースレッド: Google を開きました")

    try:
        while True:
            cmd_data = _cmd_queue.get()
            cmd = cmd_data.get("command")
            params = cmd_data.get("params", {})

            if cmd == "get_ax_tree":
                try:
                    # AX Tree取得前に短い待機を入れて、ページの初期化を確実にする
                    await asyncio.sleep(0.5)
                    # ページが確実に読み込まれていることを確認
                    await page.wait_for_load_state("domcontentloaded", timeout=5000)
                    
                    # AX Treeを取得
                    ax_tree = await page.accessibility.snapshot(root=None, interesting_only=False)
                    if ax_tree is None:
                        add_debug_log("AxTree取得結果がNoneでした")
                        _res_queue.put({"status": "success", "ax_tree": None, "message": "AxTreeが取得できませんでした"})
                    else:
                        add_debug_log("AxTree取得成功")
                        _res_queue.put({"status": "success", "ax_tree": ax_tree})
                except Exception as e:
                    add_debug_log(f"AxTree取得エラー: {e}")
                    _res_queue.put({"status": "error", "message": str(e)})

            elif cmd == "navigate":
                url = params.get("url", "")
                try:
                    # タイムアウトを増やし、待機条件を厳格化して安定性を向上
                    response = await page.goto(url, wait_until="networkidle", timeout=30000)
                    add_debug_log(f"ワーカースレッド: {url} に移動しました")
                    
                    # 成功した場合でもページの初期化を確実にするため短い待機
                    await asyncio.sleep(1.0)
                    
                    _res_queue.put({"status": "success", "url": response.url if response else url})
                except Exception as e:
                    add_debug_log(f"navigateエラー: {e}")
                    _res_queue.put({"status": "error", "message": str(e)})

            elif cmd == "click_element":
                role = params.get("role")
                name = params.get("name")
                try:
                    locator = page.get_by_role(role, name=name)
                    # 操作前に要素が存在することを確認し、タイムアウト設定を増加
                    await locator.wait_for(state="visible", timeout=5000)
                    await locator.click(timeout=10000)
                    add_debug_log(f"ワーカースレッド: {role} '{name}' をクリックしました")
                    
                    # クリック後にDOMの更新を待機
                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=5000)
                    except Exception as wait_error:
                        add_debug_log(f"クリック後のDOM更新待機中にエラー（無視）: {wait_error}")
                    
                    _res_queue.put({"status": "success"})
                except Exception as e:
                    add_debug_log(f"click_elementエラー: {e}")
                    _res_queue.put({"status": "error", "message": str(e)})

            elif cmd == "input_text":
                role = params.get("role")
                name = params.get("name")
                text = params.get("text")
                try:
                    locator = page.get_by_role(role, name=name)
                    # 操作前に要素が存在することを確認し、タイムアウト設定を増加
                    await locator.wait_for(state="visible", timeout=5000)
                    await locator.fill(text, timeout=10000)
                    await locator.press("Enter", timeout=5000)
                    add_debug_log(f"ワーカースレッド: {role} '{name}' に '{text}' を入力しました")
                    
                    # Enter押下後にDOMの更新を待機
                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=5000)
                    except Exception as wait_error:
                        add_debug_log(f"入力後のDOM更新待機中にエラー（無視）: {wait_error}")
                    
                    _res_queue.put({"status": "success"})
                except Exception as e:
                    add_debug_log(f"input_textエラー: {e}")
                    _res_queue.put({"status": "error", "message": str(e)})

            elif cmd == "execute_javascript":
                script = params.get("script", "")
                try:
                    result = await page.evaluate(script)
                    add_debug_log("ワーカースレッド: JavaScript を実行しました")
                    _res_queue.put({"status": "success", "result": result})
                except Exception as e:
                    add_debug_log(f"execute_javascriptエラー: {e}")
                    _res_queue.put({"status": "error", "message": str(e)})

            elif cmd == "screenshot":
                try:
                    data = await page.screenshot(type="png", full_page=True)
                    import base64
                    encoded = base64.b64encode(data).decode("utf-8")
                    add_debug_log("ワーカースレッド: スクリーンショットを撮影しました")
                    _res_queue.put({"status": "success", "data": encoded})
                except Exception as e:
                    add_debug_log(f"screenshotエラー: {e}")
                    _res_queue.put({"status": "error", "message": str(e)})

            elif cmd == "exit":
                add_debug_log("ワーカースレッド: exit コマンド受信、終了します")
                break

            else:
                add_debug_log(f"ワーカースレッド: 不明なコマンド '{cmd}'")
                _res_queue.put({"status": "error", "message": f"不明なコマンド: {cmd}"})

    finally:
        # コンテキスト終了前にクッキーを保存
        try:
            await ctx.save_cookies()
        except Exception:
            pass
        await ctx.close()
        await browser_factory.close()
        add_debug_log("ワーカースレッド: 終了しました")


def _browser_worker():
    asyncio.run(_async_worker())


def initialize_browser():
    """ワーカースレッドを起動または再起動します"""
    global _thread_started, _browser_thread
    add_debug_log("initialize_browser: バックブラウザワーカー起動要求")
    if _browser_thread is None or not _browser_thread.is_alive():
        t = threading.Thread(target=_browser_worker, daemon=True)
        t.start()
        _browser_thread = t
        _thread_started = True
        time.sleep(2)
        add_debug_log("initialize_browser: ワーカースレッド起動完了")
        return {"status": "success", "message": "バックブラウザワーカースレッドを起動しました"}
    add_debug_log("initialize_browser: ワーカースレッドは既に起動済み")
    return {"status": "success", "message": "ブラウザは既に初期化されています"}


def _ensure_worker_initialized():
    """ワーカースレッドが起動済みか確認し、未起動なら初期化します"""
    global _thread_started, _browser_thread
    if not _thread_started or _browser_thread is None or not _browser_thread.is_alive():
        return initialize_browser()
    return {"status": "success"} 