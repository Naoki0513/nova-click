import json
import time
import logging
from typing import List, Dict, Any, Tuple, Union, Optional
from agent.utils import add_debug_log

logger = logging.getLogger(__name__)


def call_bedrock_converse_api(
    user_message: Union[str, List, Dict],
    conversation_history: List,
    bedrock_session,
    system_prompt: Optional[str] = None,
    toolConfig: Optional[Dict] = None,
    modelId: Optional[str] = None,
    token_usage: Optional[Dict] = None
) -> Tuple[Dict, Dict]:
    """
    Amazon Bedrock Converse APIを呼び出します。
    """
    add_debug_log("Bedrock Converse API呼び出し開始")
    request_params = {"modelId": modelId} if modelId else {}

    # メッセージの整形
    messages = []
    for msg in conversation_history:
        content_list = []
        for c in msg.get("content", []):
            if c.get("type") == "text":
                content_list.append({"text": c.get("text", "")})
            elif c.get("type") == "tool_use":
                content_list.append({"toolUse": {
                    "toolUseId": c.get("id"),
                    "name": c.get("input", {}).get("tool_name"),
                    "input": c.get("input")
                }})
            elif c.get("type") == "tool_result":
                content_list.append({"toolResult": {
                    "toolUseId": c.get("tool_use_id"),
                    "content": [{"json": c.get("result")}],
                    "status": "success"
                }})
        if content_list:
            messages.append({"role": msg.get("role"), "content": content_list})

    # ユーザーメッセージの追加
    if isinstance(user_message, str):
        messages.append({"role": "user", "content": [{"text": user_message}]})
    elif isinstance(user_message, list):
        messages.append({"role": "user", "content": user_message})
    elif isinstance(user_message, dict):
        messages.append(user_message)
    else:
        raise ValueError("user_messageは文字列、リスト、または辞書でなければなりません")

    request_params["messages"] = messages
    if system_prompt:
        request_params["system"] = [{"text": system_prompt}]
    # 推論設定
    request_params["inferenceConfig"] = {"maxTokens": 8192}
    if toolConfig:
        specs = toolConfig if isinstance(toolConfig, list) else [toolConfig]
        request_params["toolConfig"] = {"tools": specs}

    add_debug_log(request_params)
    start_time = time.time()
    try:
        response = bedrock_session.converse(**request_params)
        end_time = time.time()
        add_debug_log(f"API呼び出し時間: {end_time - start_time:.2f}秒")
        response_body = response

        # トークン使用量更新
        if token_usage is None:
            token_usage = {
                "inputTokens": 0,
                "outputTokens": 0,
                "totalTokens": 0,
                "cacheReadInputTokens": 0,
                "cacheWriteInputTokens": 0
            }
        
        usage = response_body.get("usage", {})
        token_usage["inputTokens"] += usage.get("inputTokens", 0)
        token_usage["outputTokens"] += usage.get("outputTokens", 0)
        token_usage["totalTokens"] += usage.get("inputTokens", 0) + usage.get("outputTokens", 0)

        add_debug_log(response_body)
        return response_body, token_usage
    except Exception as e:
        add_debug_log(f"API呼び出しエラー: {str(e)}")
        return {"error": str(e)}, token_usage or {}


def format_assistant_message(message_content: List[Dict[str, Any]]) -> str:
    """アシスタントメッセージをフォーマットして返します。"""
    if not message_content:
        return "アシスタントからの返答を待っています..."
    
    formatted_output = []
    for content in message_content:
        content_type = content.get("type")
        if content_type == "text" or (content_type is None and "text" in content):
            text = content.get("text", "")
            if text.strip():
                formatted_output.append(text)
        elif content.get("type") == "tool_use":
            tool_name = content.get("name", "")
            formatted_output.append(f"ツール実行: {tool_name}")
        elif content.get("type") == "tool_result":
            result = content.get("result", {})
            if isinstance(result, str):
                formatted_output.append(f"結果:\n{result}")
            else:
                formatted_output.append(f"結果:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
    
    return "\n\n".join(formatted_output)


def get_browser_tools_config():
    """利用可能なブラウザ操作ツールの設定を取得します"""
    return [
        {
            "toolSpec": {
                "name": "get_ax_tree",
                "description": "ページの構造理解と操作対象特定のため、操作前後に呼び出す必要があることを追記します。現在のページのアクセシビリティツリー（AX Tree）を取得します。",
                "inputSchema": { "json": { "type": "object" } }
            }
        },
        {
            "toolSpec": {
                "name": "click_element",
                "description": "AX Treeから正確な role と name を特定してから使うことを追記します。アクセシビリティツリーを基に指定されたroleとnameの要素をクリックします",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "role": { "type": "string" },
                            "name": { "type": "string" }
                        },
                        "required": ["role", "name"]
                    }
                }
            }
        },
        {
            "toolSpec": {
                "name": "input_text",
                "description": "AX Treeから正確な role と name を特定してから使うこと、Enterキーを押すことを追記します。アクセシビリティツリーを基に指定されたroleとnameの要素にテキストを入力してEnterキーを押します",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "role": { "type": "string" },
                            "name": { "type": "string" },
                            "text": { "type": "string" }
                        },
                        "required": ["role", "name", "text"]
                    }
                }
            }
        }
    ]
