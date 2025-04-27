import streamlit as st
from .utils import add_debug_log
import threading
import queue
import time
import sys
import asyncio
import os # os モジュールをインポート
import json # json モジュールをインポート
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple

# Windows での ProactorEventLoop 設定
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Playwright 操作をスレッド内で完結させるためのコマンド/レスポンスキュー
_cmd_queue = queue.Queue()
_res_queue = queue.Queue()
_thread_started = False
_browser_thread = None  # ワーカースレッドオブジェクトを保持

# buildDomTree.js のパス (プロジェクトルートからの相対パスなどを想定)
# このファイルが実際にこのパスに存在する必要があります。
BUILD_DOM_TREE_JS_PATH = os.path.join(os.path.dirname(__file__), 'js', 'buildDomTree.js') # jsディレクトリを作成し、その中に配置する想定

# browser-use の DomService._build_dom_tree, _construct_dom_tree を模した Python 側のデータ構造とパーサーを追加
@dataclass
class ViewportInfo:
    width: int
    height: int

class DOMBaseNode:
    pass

@dataclass
class DOMTextNode(DOMBaseNode):
    text: str
    is_visible: bool
    parent: Optional['DOMElementNode'] = None

@dataclass
class DOMElementNode(DOMBaseNode):
    tag_name: str
    xpath: str
    attributes: Dict[str, Any]
    children: List[DOMBaseNode]
    is_visible: bool
    is_interactive: bool
    is_top_element: bool
    is_in_viewport: bool
    highlight_index: Optional[int]
    shadow_root: bool
    parent: Optional['DOMElementNode'] = None
    viewport_info: Optional[ViewportInfo] = None

# JS の buildDomTree.js から返される eval_page を Python 側でツリー構築するユーティリティ

def _parse_node(node_data: Dict[str, Any]) -> Tuple[Optional[DOMBaseNode], List[int]]:
    if not node_data:
        return None, []
    if node_data.get('type') == 'TEXT_NODE':
        text_node = DOMTextNode(
            text=node_data.get('text', ''),
            is_visible=node_data.get('isVisible', False),
            parent=None
        )
        return text_node, []
    viewport = None
    if 'viewport' in node_data:
        vp = node_data['viewport']
        viewport = ViewportInfo(width=vp.get('width', 0), height=vp.get('height', 0))
    element_node = DOMElementNode(
        tag_name=node_data.get('tagName', ''),
        xpath=node_data.get('xpath', ''),
        attributes=node_data.get('attributes', {}),
        children=[],
        is_visible=node_data.get('isVisible', False),
        is_interactive=node_data.get('isInteractive', False),
        is_top_element=node_data.get('isTopElement', False),
        is_in_viewport=node_data.get('isInViewport', False),
        highlight_index=node_data.get('highlightIndex'),
        shadow_root=node_data.get('shadowRoot', False),
        parent=None,
        viewport_info=viewport,
    )
    children_ids = node_data.get('children', []) or []
    return element_node, children_ids


def _construct_dom_tree(eval_page: Dict[str, Any]) -> Tuple[Optional[DOMElementNode], Dict[int, DOMElementNode]]:
    js_node_map = eval_page.get('map', {}) or {}
    js_root_id = str(eval_page.get('rootId'))
    selector_map: Dict[int, DOMElementNode] = {}
    node_map: Dict[str, DOMBaseNode] = {}
    for id_str, node_data in js_node_map.items():
        node, children_ids = _parse_node(node_data)
        if node is None:
            continue
        node_map[id_str] = node
        if isinstance(node, DOMElementNode) and node.highlight_index is not None:
            selector_map[node.highlight_index] = node
        if isinstance(node, DOMElementNode):
            for child_id in children_ids:
                child = node_map.get(str(child_id))
                if child:
                    child.parent = node
                    node.children.append(child)
    root_node = node_map.get(js_root_id)
    return root_node, selector_map

def _browser_worker():
    """バックグラウザ操作用スレッド関数"""
    # buildDomTree.js の内容を読み込む
    build_dom_tree_js_code = ""
    if os.path.exists(BUILD_DOM_TREE_JS_PATH):
        try:
            with open(BUILD_DOM_TREE_JS_PATH, 'r', encoding='utf-8') as f:
                build_dom_tree_js_code = f.read()
            add_debug_log(f"ワーカースレッド: {BUILD_DOM_TREE_JS_PATH} の読み込み成功")
        except Exception as e:
            add_debug_log(f"ワーカースレッド: {BUILD_DOM_TREE_JS_PATH} の読み込みエラー: {str(e)}")
            # エラーが発生しても処理は続行するが、構造化DOM取得は失敗する
    else:
        add_debug_log(f"ワーカースレッド: {BUILD_DOM_TREE_JS_PATH} が見つかりません。構造化DOM取得は利用できません。")


    from playwright.sync_api import sync_playwright
    add_debug_log("ワーカースレッド: Playwright 開始")
    playwright = sync_playwright().start()
    # headless=False のままとするが、デバッグ目的でなければ True に変更推奨
    browser = playwright.chromium.launch(channel='chrome', headless=False)
    page = browser.new_page()
    page.goto("https://www.google.com") # 例としてGoogleを開く
    add_debug_log("ワーカースレッド: Google を開きました")
    add_debug_log("ワーカースレッド: 初期化完了")
    try:
        while True:
            cmd_data = _cmd_queue.get()
            cmd = cmd_data['command']
            params = cmd_data.get('params', {})

            if cmd == 'get_raw_html':
                try:
                    dom = page.content()
                    add_debug_log("ワーカースレッド: Raw HTML取得成功")
                    _res_queue.put({'status': 'success', 'html': dom})
                except Exception as e:
                    add_debug_log(f"ワーカースレッド: Raw HTML取得エラー: {str(e)}")
                    _res_queue.put({'status': 'error', 'message': f'Raw HTML取得エラー: {str(e)}'})

            elif cmd == 'get_structured_dom':
                if not build_dom_tree_js_code:
                    _res_queue.put({'status': 'error', 'message': f'構造化DOM取得に必要な {BUILD_DOM_TREE_JS_PATH} が読み込めていません。'})
                    continue
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
                    add_debug_log(f"ワーカースレッド: 構造化DOM取得エラー: {str(e)}")
                    _res_queue.put({'status': 'error', 'message': f'構造化DOM取得エラー: {str(e)}'})

            elif cmd == 'get_ax_tree':
                try:
                    # accessibility.snapshot() は None を返すことがあるため注意
                    # root=None とするとページ全体のツリーを取得
                    ax_tree = page.accessibility.snapshot(root=None)
                    if ax_tree is None:
                         add_debug_log("ワーカースレッド: AxTree取得結果がNoneでした。")
                         _res_queue.put({'status': 'success', 'ax_tree': None, 'message': 'AxTreeが取得できませんでした(結果がNone)。要素が表示されていない可能性があります。'})
                    else:
                        add_debug_log("ワーカースレッド: AxTree取得成功")
                        _res_queue.put({'status': 'success', 'ax_tree': ax_tree})
                except Exception as e:
                    add_debug_log(f"ワーカースレッド: AxTree取得エラー: {str(e)}")
                    _res_queue.put({'status': 'error', 'message': f'AxTree取得エラー: {str(e)}'})

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
    # スレッドが未作成または終了している場合は新規起動
    if _browser_thread is None or not _browser_thread.is_alive():
        t = threading.Thread(target=_browser_worker, daemon=True)
        t.start()
        _browser_thread = t
        _thread_started = True
        # ワーカースレッドの初期化完了を少し待つ
        time.sleep(2)  # 初期化処理に時間がかかるため待機時間を設ける
        add_debug_log("initialize_browser: ワーカースレッド起動完了待ち終了")
        return {'status': 'success', 'message': 'バックブラウザワーカースレッドを起動しました'}
    add_debug_log("initialize_browser: ワーカースレッドは既に起動済み")
    return {'status': 'success', 'message': 'ブラウザは既に初期化されています'}

def _ensure_worker_initialized():
    """ワーカースレッドが起動していることを確認・初期化する"""
    global _thread_started, _browser_thread
    # スレッドが未作成または終了している場合は再起動
    if not _thread_started or _browser_thread is None or not _browser_thread.is_alive():
        init_res = initialize_browser()
        if init_res['status'] != 'success':
            return init_res
    return {'status': 'success'}

def get_raw_html():
    """バックブラウザワーカースレッドから Raw HTML を取得"""
    add_debug_log("get_raw_html: Raw HTML取得要求送信")
    init_status = _ensure_worker_initialized()
    if init_status['status'] != 'success':
        return init_status

    # 内部取得処理 (リトライ1回)
    def _fetch_raw():
        _cmd_queue.put({'command': 'get_raw_html'})
        try:
            return _res_queue.get(timeout=10)
        except queue.Empty:
            add_debug_log("get_raw_html: Raw HTML取得タイムアウト")
            return {'status': 'error', 'message': 'Raw HTML取得タイムアウト'}

    # 1回目
    res = _fetch_raw()
    if res.get('status') != 'success':
        add_debug_log("get_raw_html: エラー検出、ブラウザを再初期化してリトライします")
        shutdown_browser()
        init_res = initialize_browser()
        if init_res.get('status') != 'success':
            return init_res
        # 再試行
        res = _fetch_raw()
    return res

def get_structured_dom(highlight_elements=False, focus_element=-1, viewport_expansion=0, debug_mode=False):
    """
    バックグラウザワーカースレッドから構造化されたDOM情報を取得 (browser-use風)
    Args:
        highlight_elements (bool): 要素をハイライトするかどうか
        focus_element (int): フォーカスする要素のインデックス
        viewport_expansion (int): ビューポートの拡張ピクセル数
        debug_mode (bool): デバッグモードを有効にするか
    """
    add_debug_log(f"get_structured_dom: 構造化DOM取得要求送信 (params: highlight={highlight_elements}, focus={focus_element}, expansion={viewport_expansion}, debug={debug_mode})")
    init_status = _ensure_worker_initialized()
    if init_status['status'] != 'success':
        return init_status

    params = {
        'highlight_elements': highlight_elements,
        'focus_element': focus_element,
        'viewport_expansion': viewport_expansion,
        'debug_mode': debug_mode,
    }
    # 内部取得処理 (リトライ1回)
    def _fetch_structured():
        _cmd_queue.put({'command': 'get_structured_dom', 'params': params})
        try:
            return _res_queue.get(timeout=20)
        except queue.Empty:
            add_debug_log("get_structured_dom: 構造化DOM取得タイムアウト")
            return {'status': 'error', 'message': '構造化DOM取得タイムアウト'}

    # 1回目
    res = _fetch_structured()
    if res.get('status') != 'success':
        add_debug_log("get_structured_dom: エラー検出、ブラウザを再初期化してリトライします")
        shutdown_browser()
        init_res = initialize_browser()
        if init_res.get('status') != 'success':
            return init_res
        # 再試行
        res = _fetch_structured()
    return res

def get_ax_tree():
    """バックブラウザワーカースレッドから AxTree (Accessibility Tree) 情報を取得"""
    add_debug_log("get_ax_tree: AxTree取得要求送信")
    init_status = _ensure_worker_initialized()
    if init_status['status'] != 'success':
        return init_status

    # 内部取得処理 (リトライ1回含む)
    def _fetch_ax():
        _cmd_queue.put({'command': 'get_ax_tree'})
        try:
            result = _res_queue.get(timeout=15)
        except queue.Empty:
            add_debug_log("get_ax_tree: AxTree取得タイムアウト")
            return {'status': 'error', 'message': 'AxTree取得タイムアウト'}
        # JSONシリアライズを試行
        if result.get('status') == 'success' and 'ax_tree' in result:
            try:
                result['ax_tree'] = json.loads(json.dumps(result['ax_tree'], default=lambda o: '<not serializable>'))
            except Exception as e:
                add_debug_log(f"get_ax_tree: AxTreeのJSONシリアライズに失敗: {e}")
                return {'status': 'error', 'message': f'AxTreeの結果をJSON形式に変換できませんでした: {e}'}
        return result

    # 1回目
    res = _fetch_ax()
    if res.get('status') != 'success':
        add_debug_log("get_ax_tree: エラー検出、ブラウザを再初期化してリトライします")
        shutdown_browser()
        init_res = initialize_browser()
        if init_res.get('status') != 'success':
            return init_res
        # 再試行
        res = _fetch_ax()
    return res

def dispatch_browser_tool(tool_name, params=None):
    """ツール呼び出しをバックブラウザワーカーに橋渡し"""
    add_debug_log(f"ツール呼び出し: {tool_name}, params: {params}")
    params = params if params is not None else {} # paramsがNoneの場合に空辞書をセット

    if tool_name == 'initialize_browser':
        return initialize_browser()
    elif tool_name == 'get_dom_info':
        # get_dom_infoはアクセシビリティツリーを返す
        return get_ax_tree()
    elif tool_name == 'get_raw_html':
        return get_raw_html()
    elif tool_name == 'get_structured_dom':
        return get_structured_dom(
            highlight_elements=params.get('highlight_elements', False),
            focus_element=params.get('focus_element', -1),
            viewport_expansion=params.get('viewport_expansion', 0),
            debug_mode=params.get('debug_mode', False)
        )
    elif tool_name == 'get_ax_tree':
        return get_ax_tree()
    # 他のツール呼び出しを追加する場合はここに追加
    # elif tool_name == 'click_element':
    #    return click_element(params.get('selector'))
    # elif tool_name == 'input_text':
    #    return input_text(params.get('selector'), params.get('text'))
    else:
        add_debug_log(f"不明なツール: {tool_name}")
        return {'status': 'error', 'message': f'不明なツール: {tool_name}'}

# ワーカースレッド終了処理 (アプリケーション終了時などに呼び出す)
def shutdown_browser():
    """バックブラウザワーカースレッドを終了し、状態をリセット"""
    global _thread_started, _browser_thread
    if _thread_started:
        try:
            _cmd_queue.put({'command': 'exit'})
            add_debug_log("shutdown_browser: 終了コマンド送信")
            # スレッドが終了するのを少し待つ
            if _browser_thread is not None:
                _browser_thread.join(timeout=1)
            _thread_started = False
            _browser_thread = None
            return {'status': 'success', 'message': 'ブラウザワーカースレッドを終了しました'}
        except Exception as e:
            add_debug_log(f"shutdown_browser: エラー発生 {str(e)}")
            return {'status': 'error', 'message': f'ブラウザ終了時にエラーが発生しました: {str(e)}'}
    return {'status': 'info', 'message': 'ブラウザワーカースレッドは起動していません'}

# アプリケーション終了時に shutdown_browser を呼び出す例 (Streamlit用)
# import atexit
# atexit.register(shutdown_browser)
# 注: Streamlit 環境や他のフレームワークでは適切に終了処理を組み込む方法が異なる場合があります 