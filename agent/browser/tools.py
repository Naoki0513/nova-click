import queue
import json
import time
from agent.utils import add_debug_log
from queue import Queue, Empty
from typing import Dict, Any, Optional, Tuple
from .worker import initialize_browser, _ensure_worker_initialized, _cmd_queue, _res_queue


def get_aria_snapshot(wait_time: float = 0.5):
    """ブラウザワーカースレッドからARIA Snapshot情報を取得し、
    button, link, combobox要素などをフラットリストで返します。"""
    if wait_time > 0:
        add_debug_log(f"tools.get_aria_snapshot: {wait_time}秒待機してからARIA Snapshot取得")
        time.sleep(wait_time)  # ARIA Snapshot取得前に指定された時間だけ待機

    add_debug_log("tools.get_aria_snapshot: ARIAスナップショット取得要求送信")
    _ensure_worker_initialized()
    _cmd_queue.put({'command': 'get_aria_snapshot'})
    try:
        res = _res_queue.get(timeout=10.0)
        add_debug_log(f"tools.get_aria_snapshot: 応答受信 status={res.get('status')}")
        
        if res.get('status') == 'success':
            return {
                'status': 'success',
                'aria_snapshot': res.get('aria_snapshot', []),
                'message': res.get('message', 'ARIA Snapshot取得成功')
            }
        else:
            error_msg = res.get('message', '不明なエラー')
            add_debug_log(f"tools.get_aria_snapshot: エラー {error_msg}")
            return {
                'status': 'error',
                'aria_snapshot': [],
                'message': f"ARIA Snapshot取得エラー: {error_msg}"
            }
    except Empty:
        add_debug_log("tools.get_aria_snapshot: タイムアウト")
        return {
            'status': 'error',
            'aria_snapshot': [],
            'message': 'ARIA Snapshot取得タイムアウト'
        }


def goto_url(url: str) -> Dict[str, Any]:
    """指定したURLに移動します"""
    add_debug_log(f"tools.goto_url: {url}に移動")
    _ensure_worker_initialized()
    _cmd_queue.put({'command': 'goto', 'params': {'url': url}})
    try:
        res = _res_queue.get(timeout=30.0)
        add_debug_log(f"tools.goto_url: 応答受信 status={res.get('status')}")
        return res
    except Empty:
        add_debug_log("tools.goto_url: タイムアウト")
        return {'status': 'error', 'message': 'タイムアウト'}


def click_element(ref_id: str) -> Dict[str, Any]:
    """指定した要素 (ref_idで特定) をクリックします。
    
    Args:
        ref_id: 要素の参照ID (get_aria_snapshot で取得したもの)
    
    Returns:
        操作結果の辞書
    """
    params = {}
    if ref_id:
        params['ref_id'] = ref_id
    else:
        add_debug_log("tools.click_element: ref_idが指定されていません")
        return {'status': 'error', 'message': '要素を特定するref_idが必要です'}
    
    add_debug_log(f"tools.click_element: ref_id={ref_id}の要素をクリック")
    _ensure_worker_initialized()
    _cmd_queue.put({'command': 'click_element', 'params': params})
    
    try:
        res = _res_queue.get(timeout=10.0)
        add_debug_log(f"tools.click_element: 応答受信 status={res.get('status')}")
        
        # 操作実行後にARIA Snapshotを取得
        aria_snapshot_result = get_aria_snapshot(wait_time=0.5)
        
        # 結果にARIA Snapshotを追加
        res['aria_snapshot'] = aria_snapshot_result.get('aria_snapshot', [])
        if aria_snapshot_result.get('status') != 'success':
            res['aria_snapshot_message'] = aria_snapshot_result.get('message', 'ARIA Snapshot取得失敗')
        
        return res
    except Empty:
        add_debug_log("tools.click_element: タイムアウト")
        error_res = {'status': 'error', 'message': 'タイムアウト'}
        
        # エラー時にもARIA Snapshotを取得して含める
        try:
            aria_snapshot_result = get_aria_snapshot(wait_time=0.5)
            error_res['aria_snapshot'] = aria_snapshot_result.get('aria_snapshot', [])
            if aria_snapshot_result.get('status') != 'success':
                error_res['aria_snapshot_message'] = aria_snapshot_result.get('message', 'ARIA Snapshot取得失敗')
        except:
            error_res['aria_snapshot_message'] = "ARIA Snapshot取得に失敗しました"
        
        return error_res


def input_text(text: str, ref_id: str) -> Dict[str, Any]:
    """指定した要素 (ref_idで特定) にテキストを入力します。
    
    Args:
        text: 入力するテキスト
        ref_id: 要素の参照ID (get_aria_snapshot で取得したもの)
    
    Returns:
        操作結果の辞書
    """
    params = { 'text': text }
    if ref_id:
        params['ref_id'] = ref_id
    else:
        add_debug_log("tools.input_text: ref_idが指定されていません")
        return {'status': 'error', 'message': '要素を特定するref_idが必要です'}
        
    add_debug_log(f"tools.input_text: ref_id={ref_id}にテキスト '{text}' を入力")
    _ensure_worker_initialized()
    _cmd_queue.put({'command': 'input_text', 'params': params})
    
    try:
        res = _res_queue.get(timeout=10.0)
        add_debug_log(f"tools.input_text: 応答受信 status={res.get('status')}")
        
        # 操作実行後にARIA Snapshotを取得
        aria_snapshot_result = get_aria_snapshot(wait_time=0.5)
        
        # 結果にARIA Snapshotを追加
        res['aria_snapshot'] = aria_snapshot_result.get('aria_snapshot', [])
        if aria_snapshot_result.get('status') != 'success':
            res['aria_snapshot_message'] = aria_snapshot_result.get('message', 'ARIA Snapshot取得失敗')
        
        return res
    except Empty:
        add_debug_log("tools.input_text: タイムアウト")
        error_res = {'status': 'error', 'message': 'タイムアウト'}
        
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
    add_debug_log("tools.get_current_url: 現在のURL取得")
    _ensure_worker_initialized()
    _cmd_queue.put({'command': 'get_current_url'})
    try:
        res = _res_queue.get(timeout=5.0)
        add_debug_log(f"tools.get_current_url: 応答受信 status={res.get('status')}")
        if res.get('status') == 'success':
            return res.get('url', '')
        else:
            return ''
    except Empty:
        add_debug_log("tools.get_current_url: タイムアウト")
        return ''


def save_cookies() -> Dict[str, Any]:
    """現在のブラウザセッションのCookieを保存します"""
    add_debug_log("tools.save_cookies: Cookie保存")
    _ensure_worker_initialized()
    _cmd_queue.put({'command': 'save_cookies'})
    try:
        res = _res_queue.get(timeout=5.0)
        add_debug_log(f"tools.save_cookies: 応答受信 status={res.get('status')}")
        return res
    except Empty:
        add_debug_log("tools.save_cookies: タイムアウト")
        return {'status': 'error', 'message': 'タイムアウト'}


def cleanup_browser():
    """ブラウザを終了します"""
    add_debug_log("tools.cleanup_browser: ブラウザ終了")
    _ensure_worker_initialized()
    _cmd_queue.put({'command': 'quit'})
    try:
        res = _res_queue.get(timeout=10.0)
        add_debug_log(f"tools.cleanup_browser: 応答受信 status={res.get('status')}")
        return res
    except Empty:
        add_debug_log("tools.cleanup_browser: タイムアウト")
        return {'status': 'error', 'message': 'タイムアウト'}


def find_element_by_role_name(aria_snapshot, role=None, name=None):
    """ARIA Snapshotから特定のroleとnameを持つ要素を探します。
    
    Args:
        aria_snapshot: ARIAスナップショットのリスト
        role: 要素のロール（button, link等）
        name: 要素の表示名
        
    Returns:
        マッチする要素のデータ（辞書）。見つからない場合はNone。
    """
    if not aria_snapshot:
        return None
    
    for item in aria_snapshot:
        item_role = item.get('role', '')
        item_name = item.get('name', '')
        
        # roleとnameの両方が指定されている場合は両方一致する必要がある
        if role and name:
            if item_role == role and name in item_name:
                return item
        # roleのみ指定されている場合
        elif role and not name:
            if item_role == role:
                return item
        # nameのみ指定されている場合
        elif name and not role:
            if name in item_name:
                return item
    
    return None


def extract_interactive_elements(aria_snapshot):
    """ARIAスナップショットから対話可能なUI要素を抽出します。
    
    Args:
        aria_snapshot: ARIAスナップショットのリスト
        
    Returns:
        Dict[str, list]: カテゴリ別の要素リスト
    """
    if not aria_snapshot:
        return {}
    
    result = {
        'buttons': [],
        'links': [],
        'inputs': [],
        'other': []
    }
    
    for item in aria_snapshot:
        role = item.get('role', '').lower()
        if role == 'button':
            result['buttons'].append(item)
        elif role == 'link':
            result['links'].append(item)
        elif role in ['textbox', 'searchbox', 'combobox']:
            result['inputs'].append(item)
        else:
            result['other'].append(item)
    
    return result


def dispatch_browser_tool(tool_name: str, params=None):
    """指定されたツールを実行します"""
    add_debug_log(f"tools.dispatch_browser_tool: tool={tool_name}, params={params}")
    result = None
    
    if tool_name == 'click_element':
        if params is None or 'ref_id' not in params:
            result = {'status': 'error', 'message': 'パラメータ ref_id が指定されていません'}
        else:
            result = click_element(params.get('ref_id'))
    elif tool_name == 'input_text':
        if params is None or 'ref_id' not in params or 'text' not in params:
            result = {'status': 'error', 'message': 'パラメータ text または ref_id が指定されていません'}
        else:
            result = input_text(
                params.get('text'), 
                params.get('ref_id')
            )
    else:
        add_debug_log(f"tools.dispatch_browser_tool: 不明なツール {tool_name}")
        result = {'status': 'error', 'message': f'不明なツール: {tool_name}'}
    
    # ARIA Snapshotがない場合は自動取得を試みる
    if result and 'aria_snapshot' not in result:
        try:
            aria_snapshot_result = get_aria_snapshot(wait_time=0.3)
            result['aria_snapshot'] = aria_snapshot_result.get('aria_snapshot', [])
            if aria_snapshot_result.get('status') != 'success':
                result['aria_snapshot_message'] = aria_snapshot_result.get('message', 'ARIA Snapshot取得失敗')
        except Exception as e:
            add_debug_log(f"tools.dispatch_browser_tool: ARIA Snapshot自動取得エラー: {e}")
            result['aria_snapshot_message'] = "ARIA Snapshot自動取得に失敗しました"
    
    return result 