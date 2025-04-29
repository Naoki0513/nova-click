import boto3
import json
import logging
from typing import Dict, Any, List, Optional, Union, Tuple
from .utils import add_debug_log, load_credentials
from .browser.worker import initialize_browser, _ensure_worker_initialized
from .browser import dispatch_browser_tool
from .prompts import get_system_prompt

logger = logging.getLogger(__name__)

def initialize_agent(credentials_path: str) -> Dict[str, Any]:
    """エージェントを初期化し、必要なリソースをセットアップします"""
    credentials = load_credentials(credentials_path)
    if not credentials:
        return {"status": "error", "message": f"認証情報の読み込みに失敗しました: {credentials_path}"}
    
    browser_status = initialize_browser()
    if browser_status.get("status") != "success":
        return {"status": "error", "message": f"ブラウザの初期化に失敗しました: {browser_status.get('message')}"}
    
    return {"status": "success", "credentials": credentials, "browser_status": browser_status}

def get_inference_config(model_id: str) -> Dict[str, Any]:
    """モデルごとに最適な推論パラメータを返す"""
    cfg = {"maxTokens": 3000}

    if "amazon.nova" in model_id:          # Nova 系
        cfg.update({"topP": 1, "temperature": 1})
    elif "anthropic.claude" in model_id:   # Claude 系（必要なら）
        cfg.update({"temperature": 0})   # 例
    return cfg

def get_browser_tools_config() -> List[Dict[str, Any]]:
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

def update_token_usage(response: Dict[str, Any], token_usage: Dict[str, int]) -> Dict[str, int]:
    """トークン使用量を更新する"""
    usage = response.get("usage", {})
    token_usage["inputTokens"] += usage.get("inputTokens", 0)
    token_usage["outputTokens"] += usage.get("outputTokens", 0)
    token_usage["totalTokens"] += usage.get("inputTokens", 0) + usage.get("outputTokens", 0)
    return token_usage

def handle_user_query(
    user_input: str, 
    bedrock_session,
    system_prompt: str,
    model_id: str,
    session_state: Optional[Dict] = None
) -> Dict[str, Any]:
    """ユーザー入力を処理して応答を返す"""
    result = {
        "status": "success",
        "messages": [],
        "token_usage": session_state.get("token_usage", {}) if session_state else {
            "inputTokens": 0,
            "outputTokens": 0,
            "totalTokens": 0,
            "cacheReadInputTokens": 0,
            "cacheWriteInputTokens": 0
        }
    }
    
    init_status = _ensure_worker_initialized()
    if init_status.get('status') != 'success':
        return {"status": "error", "message": f"ブラウザワーカーの初期化に失敗しました: {init_status.get('message')}"}

    add_debug_log(f"ユーザー入力: {user_input}")

    tool_specs = get_browser_tools_config()
    tool_config = {
        "tools": tool_specs,
        "toolChoice": {"auto": {}}
    }

    messages = []
    messages.append({"role": "user", "content": [{"text": user_input}]})

    while True:
        try:
            inference_config = get_inference_config(model_id)
            request_params = {
                "modelId": model_id,
                "messages": messages,
                "system": [{"text": system_prompt}],
                "inferenceConfig": inference_config,
                "toolConfig": tool_config
            }
            if "amazon.nova" in model_id:
                request_params["additionalModelRequestFields"] = {"inferenceConfig": {"topK": 1}}
            add_debug_log(request_params)
            response = bedrock_session.converse(**request_params)
            add_debug_log(response)

            result["token_usage"] = update_token_usage(response, result["token_usage"])
        except Exception as e:
            err_msg = str(e)
            add_debug_log(f"API呼び出しエラー: {err_msg}")
            return {"status": "error", "message": f"APIエラー: {err_msg}"}

        output = response.get("output", {})
        message = output.get("message", {})
        stop_reason = response.get("stopReason")

        assistant_message = {"role": "assistant", "content": message.get("content", [])}
        messages.append(assistant_message)
        result["messages"].append(assistant_message)

        tool_calls = [c["toolUse"] for c in message.get("content", []) if "toolUse" in c]
        if tool_calls:
            for tool in tool_calls:
                tool_name = tool.get("name") or tool.get("tool_name") or tool.get("toolUseId")
                params = tool.get("input") or {}
                logger.info(f"ツール実行: {tool_name}")
                if params:
                    logger.debug(f"パラメータ: {json.dumps(params, ensure_ascii=False)}")
                tool_result = dispatch_browser_tool(tool_name, params)
                logger.info(f"実行結果: {json.dumps(tool_result, ensure_ascii=False)}")

                if tool_result.get('status') == 'error':
                    error_message = f"ツール '{tool_name}' の実行に失敗しました: {tool_result.get('message')}"
                    logger.error(error_message)
                    error_response = {"role": "assistant", "content": [{"text": f"エラーのため処理を中断しました: {tool_result.get('message')}"}]}
                    messages.append(error_response)
                    result["messages"].append(error_response)
                    result["status"] = "error"
                    result["message"] = error_message
                    return result

                tool_result_block = {
                    "role": "user",
                    "content": [{
                        "toolResult": {
                            "toolUseId": tool.get("toolUseId"),
                            "content": [{"json": tool_result}],
                            "status": "success"
                        }
                    }]
                }
                messages.append(tool_result_block)
                result["messages"].append(tool_result_block)
            continue

        break
    
    return result
