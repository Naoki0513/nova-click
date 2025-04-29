import queue
import json
import time
from agent.utils import add_debug_log
from queue import Queue, Empty
from typing import Dict, Any, Optional, Tuple
from .worker import initialize_browser, _ensure_worker_initialized, _cmd_queue, _res_queue


def get_ax_tree(wait_time: float = 0.5):
    """バックブラウザワーカースレッドから AxTree (Accessibility Tree) 情報を取得します

    Args:
        wait_time: AX Tree取得前に待機する秒数（デフォルト0.5秒）

    Note:
        この関数は core.py から直接呼び出されることを想定しています。
        dispatch_browser_tool 経由では呼び出されません。
    """
    if wait_time > 0:
        add_debug_log(f"tools.get_ax_tree: {wait_time}秒待機してからAX Tree取得")
        time.sleep(wait_time)  # AX Tree取得前に指定された時間だけ待機

    add_debug_log("tools.get_ax_tree: AxTree取得要求送信")
    # ワーカースレッドとの通信ロジックはそのまま維持
    _cmd_queue.put({'command': 'get_ax_tree'})
    try:
        result = _res_queue.get(timeout=15)
    except queue.Empty:
        add_debug_log("tools.get_ax_tree: タイムアウト")
        return {'status': 'error', 'message': 'AxTree取得タイムアウト'}

    # JSONでシリアライズ可能にする処理も維持
    if result.get('status') == 'success' and 'ax_tree' in result:
        # JSONシリアライズ不可能なオブジェクトが含まれる場合のエラーハンドリングを強化
        def default_serializer(o):
            try:
                # 基本的な型以外は文字列化を試みる
                return str(o)
            except Exception:
                return '<not serializable>'
        try:
            # シリアライズ可能な形式に変換
            serializable_ax_tree = json.loads(json.dumps(result['ax_tree'], default=default_serializer))
            result['ax_tree'] = serializable_ax_tree
            
            # AX Treeが空または最小限の場合、再試行
            if not result['ax_tree'] or (isinstance(result['ax_tree'], dict) and 
                                        len(result['ax_tree'].get('children', [])) == 0 and
                                        'role' in result['ax_tree'] and 'name' in result['ax_tree'] and 
                                        len(result['ax_tree']) <= 3):
                add_debug_log("tools.get_ax_tree: AX Treeが不完全なため再試行します")
                time.sleep(1.0)  # 1秒待機してから再試行
                return get_ax_tree(0)  # 再帰呼び出し（待機時間は0に設定して待機を追加しない）
                
        except Exception as e:
            add_debug_log(f"tools.get_ax_tree: JSONシリアライズ失敗: {e}")
            # エラーが発生しても、取得自体は成功している可能性があるため、エラーメッセージと共に返す
            return {'status': 'success', # ステータスは success のままにするか検討
                    'ax_tree': result.get('ax_tree'), # 元の（一部シリアライズ不能な）ツリーを返す
                    'message': f'AxTreeの一部要素をJSON変換できませんでした: {e}'}
    return result


def click_element(role: str, name: str):
    """指定したroleとnameの要素をクリックし、操作後のAX Treeを取得します"""
    add_debug_log(f"tools.click_element: role={role}, name={name}")

    # ワーカースレッドとの通信ロジック
    _cmd_queue.put({'command': 'click_element', 'params': {'role': role, 'name': name}})
    try:
        result = _res_queue.get(timeout=10)
        
        # クリック操作が成功した場合、AX Treeを取得して結果に含める
        if result.get('status') == 'success':
            add_debug_log("tools.click_element: 操作成功、AX Tree取得（3秒待機）")
            # クリック後はページ遷移や内容更新の可能性があるため、比較的長めに待機
            ax_tree_result = get_ax_tree(wait_time=3.0)
            
            # 元のクリック操作の結果を保持しつつ、AX Treeも追加
            result['ax_tree'] = ax_tree_result.get('ax_tree')
            
            # AX Treeの取得に失敗した場合、再試行
            if not result.get('ax_tree') or ax_tree_result.get('status') != 'success':
                add_debug_log("tools.click_element: 最初のAX Tree取得失敗、再試行します（2秒待機）")
                time.sleep(2.0)  # 2秒待機してから再試行
                ax_tree_result = get_ax_tree(wait_time=0)  # 待機時間は0に設定（すでに待機済み）
                result['ax_tree'] = ax_tree_result.get('ax_tree')
                
            # それでも失敗した場合はメッセージを追加
            if not result.get('ax_tree') or ax_tree_result.get('status') != 'success':
                add_debug_log("tools.click_element: AX Tree取得再試行も失敗")
                result['ax_tree_message'] = ax_tree_result.get('message', 'AX Tree取得エラー')
        
        return result
    except queue.Empty:
        add_debug_log("tools.click_element: タイムアウト")
        return {'status': 'error', 'message': 'click_elementタイムアウト'}


def input_text(role: str, name: str, text: str):
    """指定したroleとnameの要素にテキストを入力しEnterを押し、操作後のAX Treeを取得します"""
    add_debug_log(f"tools.input_text: role={role}, name={name}, text={text}")

    # ワーカースレッドとの通信ロジック
    _cmd_queue.put({'command': 'input_text', 'params': {'role': role, 'name': name, 'text': text}})
    try:
        result = _res_queue.get(timeout=10)
        
        # テキスト入力操作が成功した場合、AX Treeを取得して結果に含める
        if result.get('status') == 'success':
            add_debug_log("tools.input_text: 操作成功、AX Tree取得（2秒待機）")
            # テキスト入力+Enter後はページ遷移の可能性があるため、やや長めに待機
            ax_tree_result = get_ax_tree(wait_time=2.0)
            
            # 元の入力操作の結果を保持しつつ、AX Treeも追加
            result['ax_tree'] = ax_tree_result.get('ax_tree')
            
            # AX Treeの取得に失敗した場合、再試行
            if not result.get('ax_tree') or ax_tree_result.get('status') != 'success':
                add_debug_log("tools.input_text: 最初のAX Tree取得失敗、再試行します（2秒待機）")
                time.sleep(2.0)  # 2秒待機してから再試行
                ax_tree_result = get_ax_tree(wait_time=0)  # 待機時間は0に設定（すでに待機済み）
                result['ax_tree'] = ax_tree_result.get('ax_tree')
            
            # それでも失敗した場合はメッセージを追加
            if not result.get('ax_tree') or ax_tree_result.get('status') != 'success':
                add_debug_log("tools.input_text: AX Tree取得再試行も失敗")
                result['ax_tree_message'] = ax_tree_result.get('message', 'AX Tree取得エラー')
        
        return result
    except queue.Empty:
        add_debug_log("tools.input_text: タイムアウト")
        return {'status': 'error', 'message': 'input_textタイムアウト'}


def dispatch_browser_tool(tool_name: str, params=None):
    """指定されたツールを実行します"""
    add_debug_log(f"tools.dispatch_browser_tool: tool={tool_name}, params={params}")
    if tool_name == 'click_element':
        if params is None:
            return {'status': 'error', 'message': 'パラメータが指定されていません'}
        return click_element(params.get('role', ''), params.get('name', ''))
    elif tool_name == 'input_text':
        if params is None:
            return {'status': 'error', 'message': 'パラメータが指定されていません'}
        return input_text(params.get('role', ''), params.get('name', ''), params.get('text', ''))
    else:
        add_debug_log(f"tools.dispatch_browser_tool: 不明なツール {tool_name}")
        return {'status': 'error', 'message': f'不明なツール: {tool_name}'} 