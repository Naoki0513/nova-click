import queue
import json
from agent.utils import add_debug_log
from .worker import initialize_browser, _ensure_worker_initialized, shutdown_browser, _cmd_queue, _res_queue


def get_raw_html():
    """バックブラウザワーカースレッドから Raw HTML を取得します"""
    add_debug_log("tools.get_raw_html: Raw HTML取得要求送信")
    init_status = _ensure_worker_initialized()
    if init_status.get('status') != 'success':
        return init_status

    def _fetch_raw():
        _cmd_queue.put({'command': 'get_raw_html'})
        try:
            return _res_queue.get(timeout=10)
        except queue.Empty:
            add_debug_log("tools.get_raw_html: Raw HTML取得タイムアウト")
            return {'status': 'error', 'message': 'Raw HTML取得タイムアウト'}

    res = _fetch_raw()
    if res.get('status') != 'success':
        add_debug_log("tools.get_raw_html: エラー検出、再初期化してリトライ")
        shutdown_browser()
        init_res = initialize_browser()
        if init_res.get('status') != 'success':
            return init_res
        res = _fetch_raw()
    return res


def get_structured_dom(highlight_elements=False, focus_element=-1, viewport_expansion=0, debug_mode=False):
    """バックブラウザワーカースレッドから構造化DOM情報を取得します"""
    add_debug_log(f"tools.get_structured_dom: params={{highlight={highlight_elements}, focus={focus_element}, expansion={viewport_expansion}, debug={debug_mode}}}")
    init_status = _ensure_worker_initialized()
    if init_status.get('status') != 'success':
        return init_status

    params = {
        'highlight_elements': highlight_elements,
        'focus_element': focus_element,
        'viewport_expansion': viewport_expansion,
        'debug_mode': debug_mode,
    }

    def _fetch_structured():
        _cmd_queue.put({'command': 'get_structured_dom', 'params': params})
        try:
            return _res_queue.get(timeout=20)
        except queue.Empty:
            add_debug_log("tools.get_structured_dom: タイムアウト")
            return {'status': 'error', 'message': '構造化DOM取得タイムアウト'}

    res = _fetch_structured()
    if res.get('status') != 'success':
        add_debug_log("tools.get_structured_dom: エラー検出、再初期化してリトライ")
        shutdown_browser()
        init_res = initialize_browser()
        if init_res.get('status') != 'success':
            return init_res
        res = _fetch_structured()
    return res


def get_ax_tree():
    """バックブラウザワーカースレッドから AxTree (Accessibility Tree) 情報を取得します"""
    add_debug_log("tools.get_ax_tree: AxTree取得要求送信")
    init_status = _ensure_worker_initialized()
    if init_status.get('status') != 'success':
        return init_status

    def _fetch_ax():
        _cmd_queue.put({'command': 'get_ax_tree'})
        try:
            result = _res_queue.get(timeout=15)
        except queue.Empty:
            add_debug_log("tools.get_ax_tree: タイムアウト")
            return {'status': 'error', 'message': 'AxTree取得タイムアウト'}
        # JSONでシリアライズ可能にする
        if result.get('status') == 'success' and 'ax_tree' in result:
            try:
                result['ax_tree'] = json.loads(json.dumps(result['ax_tree'], default=lambda o: '<not serializable>'))
            except Exception as e:
                add_debug_log(f"tools.get_ax_tree: JSONシリアライズ失敗: {e}")
                return {'status': 'error', 'message': f'AxTreeの結果をJSON変換できませんでした: {e}'}
        return result

    res = _fetch_ax()
    if res.get('status') != 'success':
        add_debug_log("tools.get_ax_tree: エラー検出、再初期化してリトライ")
        shutdown_browser()
        init_res = initialize_browser()
        if init_res.get('status') != 'success':
            return init_res
        res = _fetch_ax()
    return res


def click_element(role: str, name: str):
    """指定したroleとnameの要素をクリックします"""
    add_debug_log(f"tools.click_element: role={role}, name={name}")
    init_status = _ensure_worker_initialized()
    if init_status.get('status') != 'success':
        return init_status

    def _fetch_click():
        _cmd_queue.put({'command': 'click_element', 'params': {'role': role, 'name': name}})
        try:
            return _res_queue.get(timeout=10)
        except queue.Empty:
            add_debug_log("tools.click_element: タイムアウト")
            return {'status': 'error', 'message': 'click_elementタイムアウト'}

    res = _fetch_click()
    if res.get('status') != 'success':
        add_debug_log("tools.click_element: エラー検出、再初期化してリトライ")
        shutdown_browser()
        init_res = initialize_browser()
        if init_res.get('status') != 'success':
            return init_res
        res = _fetch_click()
    return res


def input_text(role: str, name: str, text: str):
    """指定したroleとnameの要素にテキストを入力しEnterを押します"""
    add_debug_log(f"tools.input_text: role={role}, name={name}, text={text}")
    init_status = _ensure_worker_initialized()
    if init_status.get('status') != 'success':
        return init_status

    def _fetch_input():
        _cmd_queue.put({'command': 'input_text', 'params': {'role': role, 'name': name, 'text': text}})
        try:
            return _res_queue.get(timeout=10)
        except queue.Empty:
            add_debug_log("tools.input_text: タイムアウト")
            return {'status': 'error', 'message': 'input_textタイムアウト'}

    res = _fetch_input()
    if res.get('status') != 'success':
        add_debug_log("tools.input_text: エラー検出、再初期化してリトライ")
        shutdown_browser()
        init_res = initialize_browser()
        if init_res.get('status') != 'success':
            return init_res
        res = _fetch_input()
    return res


def dispatch_browser_tool(tool_name: str, params=None):
    """指定されたツールを実行します"""
    add_debug_log(f"tools.dispatch_browser_tool: tool={tool_name}, params={params}")
    if tool_name == 'initialize_browser':
        return initialize_browser()
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
    elif tool_name == 'click_element':
        return click_element(params.get('role'), params.get('name'))
    elif tool_name == 'input_text':
        return input_text(params.get('role'), params.get('name'), params.get('text'))
    else:
        add_debug_log(f"tools.dispatch_browser_tool: 不明なツール {tool_name}")
        return {'status': 'error', 'message': f'不明なツール: {tool_name}'} 