import threading
import queue
import time
import sys
import asyncio
import os
import json
from agent.utils import add_debug_log
from .dom import _construct_dom_tree

# Windows での ProactorEventLoop 設定
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Playwright 操作をスレッド内で完結させるためのコマンド/レスポンスキュー
_cmd_queue = queue.Queue()
_res_queue = queue.Queue()
_thread_started = False
_browser_thread = None

# buildDomTree.js のパス
BUILD_DOM_TREE_JS_PATH = os.path.join(os.path.dirname(__file__), 'js', 'buildDomTree.js')


def _browser_worker():
    """バックブラウザ操作用スレッド関数"""
    # buildDomTree.js の内容を読み込む
    build_dom_tree_js_code = ""
    if os.path.exists(BUILD_DOM_TREE_JS_PATH):
        try:
            with open(BUILD_DOM_TREE_JS_PATH, 'r', encoding='utf-8') as f:
                build_dom_tree_js_code = f.read()
            add_debug_log(f"ワーカースレッド: {BUILD_DOM_TREE_JS_PATH} の読み込み成功")
        except Exception as e:
            add_debug_log(f"ワーカースレッド: {BUILD_DOM_TREE_JS_PATH} の読み込みエラー: {e}")
    else:
        add_debug_log(f"ワーカースレッド: {BUILD_DOM_TREE_JS_PATH} が見つかりません。構造化DOM取得は利用できません。")

    from playwright.sync_api import sync_playwright
    add_debug_log("ワーカースレッド: Playwright 開始")
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(channel='chrome', headless=False)
    page = browser.new_page()
    page.goto("https://www.google.com")
    add_debug_log("ワーカースレッド: Google を開きました")
    add_debug_log("ワーカースレッド: 初期化完了")
    try:
        while True:
            cmd_data = _cmd_queue.get()
            cmd = cmd_data.get('command')
            params = cmd_data.get('params', {})

            if cmd == 'get_raw_html':
                try:
                    dom = page.content()
                    add_debug_log("ワーカースレッド: Raw HTML取得成功")
                    _res_queue.put({'status': 'success', 'html': dom})
                except Exception as e:
                    add_debug_log(f"ワーカースレッド: Raw HTML取得エラー: {e}")
                    _res_queue.put({'status': 'error', 'message': f'Raw HTML取得エラー: {e}'})

            elif cmd == 'get_structured_dom':
                if not build_dom_tree_js_code:
                    _res_queue.put({'status': 'error', 'message': f'構造化DOM取得に必要な {BUILD_DOM_TREE_JS_PATH} が読み込めていません。'})
                else:
                    try:
                        js_args = {
                            'doHighlightElements': params.get('highlight_elements', False),
                            'focusHighlightIndex': params.get('focus_element', -1),
                            'viewportExpansion': params.get('viewport_expansion', 0),
                            'debugMode': params.get('debug_mode', False),
                        }
                        eval_page = page.evaluate(build_dom_tree_js_code, js_args)
                        element_tree, selector_map = _construct_dom_tree(eval_page)
                        add_debug_log("ワーカースレッド: 構造化DOM取得成功")
                        _res_queue.put({'status': 'success', 'element_tree': element_tree, 'selector_map': selector_map})
                    except Exception as e:
                        add_debug_log(f"ワーカースレッド: 構造化DOM取得エラー: {e}")
                        _res_queue.put({'status': 'error', 'message': f'構造化DOM取得エラー: {e}'})

            elif cmd == 'get_ax_tree':
                try:
                    ax_tree = page.accessibility.snapshot(root=None)
                    if ax_tree is None:
                        add_debug_log("ワーカースレッド: AxTree取得結果がNoneでした。")
                        _res_queue.put({'status': 'success', 'ax_tree': None, 'message': 'AxTreeが取得できませんでした(結果がNone)。'})
                    else:
                        add_debug_log("ワーカースレッド: AxTree取得成功")
                        _res_queue.put({'status': 'success', 'ax_tree': ax_tree})
                except Exception as e:
                    add_debug_log(f"ワーカースレッド: AxTree取得エラー: {e}")
                    _res_queue.put({'status': 'error', 'message': f'AxTree取得エラー: {e}'})

            elif cmd == 'click_element':
                role = params.get('role')
                name = params.get('name')
                try:
                    locator = page.get_by_role(role, name=name)
                    locator.click()
                    add_debug_log(f"ワーカースレッド: {role} '{name}' をクリックしました")
                    _res_queue.put({'status': 'success'})
                except Exception as e:
                    add_debug_log(f"ワーカースレッド: click_element エラー: {e}")
                    _res_queue.put({'status': 'error', 'message': f'click_elementエラー: {e}'})

            elif cmd == 'input_text':
                role = params.get('role')
                name = params.get('name')
                text = params.get('text')
                try:
                    locator = page.get_by_role(role, name=name)
                    locator.fill(text)
                    locator.press('Enter')
                    add_debug_log(f"ワーカースレッド: {role} '{name}' に '{text}' を入力しました")
                    _res_queue.put({'status': 'success'})
                except Exception as e:
                    add_debug_log(f"ワーカースレッド: input_text エラー: {e}")
                    _res_queue.put({'status': 'error', 'message': f'input_textエラー: {e}'})

            elif cmd == 'exit':
                break

            else:
                add_debug_log(f"ワーカースレッド: 不明なコマンド: {cmd}")
                _res_queue.put({'status': 'error', 'message': f'不明なコマンド: {cmd}'})
    finally:
        browser.close()
        playwright.stop()
        add_debug_log("ワーカースレッド: 終了")


def initialize_browser():
    """ブラウザ操作用バックブラウザワーカースレッドを起動または再起動"""
    global _thread_started, _browser_thread
    add_debug_log("initialize_browser: バックブラウザワーカー起動要求")
    if _browser_thread is None or not _browser_thread.is_alive():
        t = threading.Thread(target=_browser_worker, daemon=True)
        t.start()
        _browser_thread = t
        _thread_started = True
        time.sleep(2)
        add_debug_log("initialize_browser: ワーカースレッド起動完了待ち終了")
        return {'status': 'success', 'message': 'バックブラウザワーカースレッドを起動しました'}
    add_debug_log("initialize_browser: ワーカースレッドは既に起動済み")
    return {'status': 'success', 'message': 'ブラウザは既に初期化されています'}


def _ensure_worker_initialized():
    """ワーカースレッドが起動していることを確認・初期化する"""
    global _thread_started, _browser_thread
    if not _thread_started or _browser_thread is None or not _browser_thread.is_alive():
        init_res = initialize_browser()
        if init_res.get('status') != 'success':
            return init_res
    return {'status': 'success'}


def shutdown_browser():
    """バックブラウザワーカースレッドを終了し、状態をリセット"""
    global _thread_started, _browser_thread
    if _thread_started:
        try:
            _cmd_queue.put({'command': 'exit'})
            add_debug_log("shutdown_browser: 終了コマンド送信")
            if _browser_thread is not None:
                _browser_thread.join(timeout=1)
            _thread_started = False
            _browser_thread = None
            return {'status': 'success', 'message': 'ブラウザワーカースレッドを終了しました'}
        except Exception as e:
            add_debug_log(f"shutdown_browser: エラー発生 {e}")
            return {'status': 'error', 'message': f'ブラウザ終了時にエラーが発生しました: {e}'}
    return {'status': 'info', 'message': 'ブラウザワーカースレッドは起動していません'} 