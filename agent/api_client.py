import streamlit as st
import json
import time
from typing import List, Dict, Any, Tuple, Union
from .utils import add_debug_log

def call_bedrock_converse_api(
    user_message: Union[str, List, Dict],
    conversation_history: List,
    bedrock_session,
    system_prompt: str = None,
    toolConfig: Dict = None,
    modelId: str = None
) -> Tuple[Dict, Dict]:
    """
    Amazon Bedrock Converse APIを呼び出します。
    
    Args:
        user_message: ユーザーメッセージ（文字列、リスト、または辞書）
        conversation_history: これまでの会話履歴
        bedrock_session: Bedrockセッション
        system_prompt: システムプロンプト
        toolConfig: ツール設定
        modelId: 使用するモデルのID
        
    Returns:
        APIレスポンスとトークン使用量の辞書のタプル
    """
    add_debug_log("Bedrock Converse API呼び出し開始")
    
    # リクエストパラメータの構築
    request_params = {
        "modelId": modelId,
    }
    
    # メッセージの設定をAPI仕様に合わせて整形
    messages = []
    for msg in conversation_history:
        content_list = []
        for c in msg.get("content", []):
            # テキストメッセージの整形
            if c.get("type") == "text":
                content_list.append({"text": c.get("text", "")})
            # ツール呼び出しの整形
            elif c.get("type") == "tool_use":
                content_list.append({"toolUse": {
                    "toolUseId": c.get("id"),
                    "name": c.get("input", {}).get("tool_name"),
                    "input": c.get("input")
                }})
            # ツール結果の整形
            elif c.get("type") == "tool_result":
                content_list.append({"toolResult": {
                    "toolUseId": c.get("tool_use_id"),
                    "content": [{"json": c.get("result")}],
                    "status": "success"
                }})
        if content_list:
            messages.append({"role": msg.get("role"), "content": content_list})

    # 新しいユーザーメッセージを追加
    if isinstance(user_message, str):
        messages.append({"role": "user", "content": [{"text": user_message}]})
    elif isinstance(user_message, list):
        # 既にAPI仕様に沿ったリストと想定
        messages.append({"role": "user", "content": user_message})
    elif isinstance(user_message, dict):
        messages.append(user_message)
    else:
        raise ValueError("user_messageは文字列、リスト、または辞書でなければなりません")

    request_params["messages"] = messages
    
    # システムプロンプトがある場合は追加
    if system_prompt:
        request_params["system"] = [{"text": system_prompt}]
    
    # 推論設定の追加
    request_params["inferenceConfig"] = {
        "maxTokens": 8192,
    }
    
    # ツール設定がある場合は追加
    if toolConfig:
        # toolConfig がリストか単一かを判定
        if isinstance(toolConfig, list):
            specs = toolConfig
        else:
            specs = [toolConfig]
        request_params["toolConfig"] = {
            "tools": specs
        }
    
    add_debug_log(request_params)
    
    # API呼び出し
    start_time = time.time()
    try:
        response = bedrock_session.converse(**request_params)
        end_time = time.time()
        add_debug_log(f"API呼び出し時間: {end_time - start_time:.2f}秒")
        
        # レスポンスの解析
        response_body = response
        
        # 使用量情報の更新
        usage = response_body.get("usage", {})
        if "token_usage" not in st.session_state:
            st.session_state["token_usage"] = {
                "inputTokens": 0,
                "outputTokens": 0,
                "totalTokens": 0,
                "cacheReadInputTokens": 0,
                "cacheWriteInputTokens": 0
            }
        
        st.session_state["token_usage"]["inputTokens"] += usage.get("inputTokens", 0)
        st.session_state["token_usage"]["outputTokens"] += usage.get("outputTokens", 0)
        st.session_state["token_usage"]["totalTokens"] += usage.get("inputTokens", 0) + usage.get("outputTokens", 0)
        
        add_debug_log(response_body)
        return response_body, st.session_state["token_usage"]
    
    except Exception as e:
        end_time = time.time()
        add_debug_log(f"API呼び出しエラー: {str(e)}")
        return {"error": str(e)}, st.session_state.get("token_usage", {})

def display_assistant_message(message_content: List[Dict[str, Any]]):
    """アシスタントメッセージを表示します。"""
    if not message_content:
        st.info("アシスタントからの返答を待っています...")
        return
        
    for content in message_content:
        # 'type'キーが"text"または'type'がなく'text'キーがある場合はテキストとみなす
        content_type = content.get("type")
        if content_type == "text" or (content_type is None and "text" in content):
            text = content.get("text", "")
            if text.strip():  # 空でない場合のみ表示
                st.markdown(text)
        elif content.get("type") == "tool_use":
            tool_name = content.get("name", "")
            st.info(f"ツール実行: {tool_name}")
        elif content.get("type") == "tool_result":
            result = content.get("result", {})
            # 結果が文字列の場合はそのまま表示
            if isinstance(result, str):
                st.code(result, language="text")
            else:
                # 日本語を正しく表示するためにensure_asciiをFalseに設定
                st.code(json.dumps(result, indent=2, ensure_ascii=False), language="json")

def get_browser_tools_config():
    """利用可能なブラウザ操作ツールの設定を取得します (初期化 & DOM情報取得)"""
    return [
        {
            "toolSpec": {
                "name": "initialize_browser",
                "description": "Playwrightを使って通常のChromeブラウザを起動します",
                "inputSchema": { "json": { "type": "object" } }
            }
        },
        {
            "toolSpec": {
                "name": "get_dom_info",
                "description": "現在のページのDOM情報を取得します",
                "inputSchema": { "json": { "type": "object" } }
            }
        }
    ] 