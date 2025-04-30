import queue
import json
import time
from agent.utils import add_debug_log
from queue import Queue, Empty
from typing import Dict, Any, Optional, Tuple
from .worker import initialize_browser, _ensure_worker_initialized, _cmd_queue, _res_queue


def get_ax_tree(wait_time: float = 0.5):
    """バックブラウザワーカースレッドからAX Tree情報を取得し、
    button, link, combobox要素のみを抽出してフラットリストで返します。"""
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

    # 成功時に結果をフィルタリングして返す
    if result.get('status') == 'success' and 'ax_tree' in result:
        try:
            # JSONシリアライズしてPythonオブジェクトにする
            raw_tree = json.loads(json.dumps(result['ax_tree'], default=lambda o: str(o)))
            # フラットリストにして抽出
            filtered: list = []
            def dfs(node: dict):
                role = node.get('role')
                name = node.get('name')
                if role in ('button', 'link', 'combobox'):
                    filtered.append({'role': role, 'name': name})
                for child in node.get('children', []):
                    dfs(child)
            dfs(raw_tree)
            result['ax_tree'] = filtered
        except Exception as e:
            add_debug_log(f"tools.get_ax_tree: AxTree処理中にエラー: {e}")
            # エラー時は空リストで返却
            return {'status': 'success', 'ax_tree': [], 'message': f'AxTree処理中にエラー: {e}'}
    return result


def click_element(role: str, name: str):
    """指定したroleとnameの要素をクリックし、操作後のAX Treeを取得します"""
    add_debug_log(f"tools.click_element: role={role}, name={name}")
    result = {'status': 'error', 'message': '不明なエラー'} # デフォルトの結果を定義

    try:
        # ワーカースレッドとの通信ロジック
        _cmd_queue.put({'command': 'click_element', 'params': {'role': role, 'name': name}})
        result = _res_queue.get(timeout=10) # ここで結果が上書きされる可能性がある

        # クリック操作が成功した場合、AX Treeを取得して結果に含める
        if result.get('status') == 'success':
            add_debug_log("tools.click_element: 操作成功、AX Tree取得（3秒待機）")
            # クリック後はページ遷移や内容更新の可能性があるため、比較的長めに待機
            ax_tree_result = get_ax_tree(wait_time=3.0)

            # 元のクリック操作の結果を保持しつつ、AX Treeも追加
            result['ax_tree'] = ax_tree_result.get('ax_tree')
            result['ax_tree_message'] = ax_tree_result.get('message') # messageも取得

            # AX Treeの取得に失敗した場合、再試行
            if not result.get('ax_tree') or ax_tree_result.get('status') != 'success':
                add_debug_log("tools.click_element: 最初のAX Tree取得失敗、再試行します（2秒待機）")
                time.sleep(2.0)  # 2秒待機してから再試行
                ax_tree_result = get_ax_tree(wait_time=0)  # 待機時間は0に設定（すでに待機済み）
                result['ax_tree'] = ax_tree_result.get('ax_tree')
                result['ax_tree_message'] = ax_tree_result.get('message') # messageも取得

            # それでも失敗した場合はメッセージを更新
            if not result.get('ax_tree') or ax_tree_result.get('status') != 'success':
                add_debug_log("tools.click_element: AX Tree取得再試行も失敗")
                # すでに ax_tree_message は設定されているはずなので、ここでは何もしないか、特定のメッセージを設定
                if not result.get('ax_tree_message'): # メッセージがなければ設定
                    result['ax_tree_message'] = ax_tree_result.get('message', 'AX Tree取得エラー')

    except queue.Empty:
        add_debug_log("tools.click_element: タイムアウト")
        result = {'status': 'error', 'message': 'click_elementタイムアウト'}
    except Exception as e:
        add_debug_log(f"tools.click_element: 予期せぬエラー: {e}")
        result = {'status': 'error', 'message': f'予期せぬエラー: {e}'}

    # 操作が失敗した場合でもAX Treeを取得する
    if result.get('status') != 'success':
        add_debug_log(f"tools.click_element: 操作失敗 ({result.get('message')})、AX Tree取得試行")
        ax_tree_result_on_fail = get_ax_tree(wait_time=0) # 失敗時は待たない
        result['ax_tree'] = ax_tree_result_on_fail.get('ax_tree')
        result['ax_tree_message'] = ax_tree_result_on_fail.get('message')

    return result


def input_text(role: str, name: str, text: str):
    """指定したroleとnameの要素にテキストを入力しEnterを押し、操作後のAX Treeを取得します"""
    add_debug_log(f"tools.input_text: role={role}, name={name}, text={text}")
    result = {'status': 'error', 'message': '不明なエラー'} # デフォルトの結果を定義

    try:
        # ワーカースレッドとの通信ロジック
        _cmd_queue.put({'command': 'input_text', 'params': {'role': role, 'name': name, 'text': text}})
        result = _res_queue.get(timeout=10) # ここで結果が上書きされる可能性がある

        # テキスト入力操作が成功した場合、AX Treeを取得して結果に含める
        if result.get('status') == 'success':
            add_debug_log("tools.input_text: 操作成功、AX Tree取得（2秒待機）")
            # テキスト入力+Enter後はページ遷移の可能性があるため、やや長めに待機
            ax_tree_result = get_ax_tree(wait_time=2.0)

            # 元の入力操作の結果を保持しつつ、AX Treeも追加
            result['ax_tree'] = ax_tree_result.get('ax_tree')
            result['ax_tree_message'] = ax_tree_result.get('message') # messageも取得

            # AX Treeの取得に失敗した場合、再試行
            if not result.get('ax_tree') or ax_tree_result.get('status') != 'success':
                add_debug_log("tools.input_text: 最初のAX Tree取得失敗、再試行します（2秒待機）")
                time.sleep(2.0)  # 2秒待機してから再試行
                ax_tree_result = get_ax_tree(wait_time=0)  # 待機時間は0に設定（すでに待機済み）
                result['ax_tree'] = ax_tree_result.get('ax_tree')
                result['ax_tree_message'] = ax_tree_result.get('message') # messageも取得

            # それでも失敗した場合はメッセージを更新
            if not result.get('ax_tree') or ax_tree_result.get('status') != 'success':
                add_debug_log("tools.input_text: AX Tree取得再試行も失敗")
                if not result.get('ax_tree_message'): # メッセージがなければ設定
                    result['ax_tree_message'] = ax_tree_result.get('message', 'AX Tree取得エラー')

    except queue.Empty:
        add_debug_log("tools.input_text: タイムアウト")
        result = {'status': 'error', 'message': 'input_textタイムアウト'}
    except Exception as e:
        add_debug_log(f"tools.input_text: 予期せぬエラー: {e}")
        result = {'status': 'error', 'message': f'予期せぬエラー: {e}'}

    # 操作が失敗した場合でもAX Treeを取得する
    if result.get('status') != 'success':
        add_debug_log(f"tools.input_text: 操作失敗 ({result.get('message')})、AX Tree取得試行")
        ax_tree_result_on_fail = get_ax_tree(wait_time=0) # 失敗時は待たない
        result['ax_tree'] = ax_tree_result_on_fail.get('ax_tree')
        result['ax_tree_message'] = ax_tree_result_on_fail.get('message')

    return result


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