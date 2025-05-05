"""
メッセージ管理モジュール

Bedrock API に渡す会話履歴の管理と、ユーザーに表示するメッセージの整形を行います。
"""

import json
import logging
from typing import Dict, Any, List, Optional

from .utils import add_debug_log

logger = logging.getLogger(__name__)


def format_user_query_with_aria_snapshot(user_input: str, aria_snapshot: Optional[Dict]) -> str:
    """ユーザー入力とARIA Snapshotを組み合わせたフォーマット済みテキストを返します"""
    aria_snapshot_str = "ARIA Snapshotを取得できませんでした。"
    if aria_snapshot is not None:
        try:
            aria_snapshot_json = json.dumps(aria_snapshot, ensure_ascii=False, indent=2)
            # 長さ制限を適用
            MAX_ARIA_SNAPSHOT_LENGTH = 100000
            if len(aria_snapshot_json) > MAX_ARIA_SNAPSHOT_LENGTH:
                aria_snapshot_json = aria_snapshot_json[:MAX_ARIA_SNAPSHOT_LENGTH] + "\n... (truncated)"
            aria_snapshot_str = f"現在のページのARIA Snapshot:\n```json\n{aria_snapshot_json}\n```"
        except Exception as e:
            aria_snapshot_str = f"ARIA Snapshotの変換エラー: {e}"
    
    formatted_text = f"""ユーザーからの指示: {user_input}

{aria_snapshot_str}

上記のユーザー指示と現在のページ状態（ARIA Snapshot）を基に応答またはツールを実行してください。"""
    
    return formatted_text


def create_initial_messages(user_input: str, aria_snapshot: Optional[Dict]) -> List[Dict[str, Any]]:
    """初回のメッセージリストを作成します
    
    Args:
        user_input: ユーザーの入力テキスト
        aria_snapshot: 現在のARIA Snapshot
        
    Returns:
        Bedrock API用のメッセージリスト
    """
    # ユーザー入力とARIA Snapshotを組み合わせたテキストを作成
    formatted_user_input = format_user_query_with_aria_snapshot(user_input, aria_snapshot)
    
    # 初回のユーザーメッセージを作成
    initial_user_message = {"role": "user", "content": [{"text": formatted_user_input}]}
    
    return [initial_user_message]


def create_user_facing_messages(user_input: str) -> List[Dict[str, Any]]:
    """ユーザーに表示するためのメッセージリストを作成します
    
    Args:
        user_input: ユーザーの入力テキスト
        
    Returns:
        ユーザーに表示するためのメッセージリスト
    """
    # ユーザーには元の質問のみを表示する形式でメッセージを作成
    user_facing_message = {"role": "user", "content": [{"text": user_input}]}
    
    return [user_facing_message]


def add_assistant_message(messages: List[Dict[str, Any]], assistant_content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """アシスタントのメッセージをリストに追加します
    
    Args:
        messages: 既存のメッセージリスト
        assistant_content: アシスタントの応答コンテンツ
        
    Returns:
        更新されたメッセージリスト
    """
    assistant_message = {"role": "assistant", "content": assistant_content}
    messages.append(assistant_message)
    return messages


def create_tool_result_message(tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """ツール実行結果のユーザーメッセージを作成します
    
    Args:
        tool_results: ツール実行結果のリスト
        
    Returns:
        ツール結果を含むユーザーメッセージ
    """
    merged_content = []
    
    for result in tool_results:
        tool_use_id = result.get('toolUseId')
        tool_result_data = result.get('result', {})
        tool_status = "success" if tool_result_data.get('status') == 'success' else "error"
        
        # ツール結果JSONにはツール実行結果とARIA Snapshot情報を含める
        tool_result_json = {
            "operation_status": tool_result_data.get('status'),
            "message": tool_result_data.get('message', '')
        }
        
        # ツール実行後に取得したARIA Snapshotがあれば含める
        if 'aria_snapshot' in tool_result_data:
            tool_result_json["aria_snapshot"] = tool_result_data.get('aria_snapshot')
            if 'aria_snapshot_message' in tool_result_data:
                tool_result_json["aria_snapshot_message"] = tool_result_data.get('aria_snapshot_message')
        
        # toolResultブロックを作成
        tool_result_block = {
            "toolResult": {
                "toolUseId": tool_use_id,
                "content": [{"json": tool_result_json}],
                "status": tool_status
            }
        }
        
        merged_content.append(tool_result_block)
    
    # マージした内容でuserメッセージを作成
    return {"role": "user", "content": merged_content} 