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
    toolConfig: Dict = None
) -> Tuple[Dict, Dict]:
    """
    Amazon Bedrock Converse APIを呼び出します。
    
    Args:
        user_message: ユーザーメッセージ（文字列、リスト、または辞書）
        conversation_history: これまでの会話履歴
        bedrock_session: Bedrockセッション
        system_prompt: システムプロンプト
        toolConfig: ツール設定
        
    Returns:
        APIレスポンスとトークン使用量の辞書のタプル
    """
    add_debug_log("Bedrock Converse API呼び出し開始", "API")
    
    # リクエストボディの構築
    request = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 8192,
    }
    
    # システムプロンプトがある場合は追加
    if system_prompt:
        request["system"] = system_prompt
    
    # ツール設定がある場合は追加
    if toolConfig:
        request["tools"] = [toolConfig]
    
    # メッセージの設定
    # 会話履歴が空でなければ、そこから会話を構築
    if conversation_history:
        request["messages"] = conversation_history
    else:
        # 空の場合は新しい会話を開始
        request["messages"] = []
    
    # ユーザーメッセージの追加
    if isinstance(user_message, str):
        # 文字列の場合は単純なテキストメッセージ
        user_msg = {"role": "user", "content": [{"type": "text", "text": user_message}]}
    elif isinstance(user_message, list):
        # リストの場合はそのまま使用（マルチモーダルなど）
        user_msg = {"role": "user", "content": user_message}
    elif isinstance(user_message, dict):
        # 辞書の場合は完全なメッセージとして扱う
        user_msg = user_message
    else:
        raise ValueError("user_messageは文字列、リスト、または辞書でなければなりません")
    
    # 最後のメッセージがユーザーからでない場合のみ追加
    if not conversation_history or conversation_history[-1]["role"] != "user":
        request["messages"].append(user_msg)
    
    add_debug_log(f"リクエスト: {json.dumps(request, ensure_ascii=False)[:200]}...", "API")
    
    # API呼び出し
    start_time = time.time()
    try:
        response = bedrock_session.converse(body=json.dumps(request))
        end_time = time.time()
        add_debug_log(f"API呼び出し時間: {end_time - start_time:.2f}秒", "API")
        
        # レスポンスの解析
        response_body = json.loads(response.get("body").read())
        
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
        
        st.session_state["token_usage"]["inputTokens"] += usage.get("input_tokens", 0)
        st.session_state["token_usage"]["outputTokens"] += usage.get("output_tokens", 0)
        st.session_state["token_usage"]["totalTokens"] += usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        
        add_debug_log(f"レスポンス: {json.dumps(response_body, ensure_ascii=False)[:200]}...", "API")
        return response_body, st.session_state["token_usage"]
    
    except Exception as e:
        end_time = time.time()
        add_debug_log(f"API呼び出しエラー: {str(e)}", "エラー")
        return {"error": str(e)}, st.session_state.get("token_usage", {})

def display_assistant_message(message_content: List[Dict[str, Any]]):
    """アシスタントメッセージを表示します。"""
    if not message_content:
        st.info("アシスタントからの返答を待っています...")
        return
        
    for content in message_content:
        if content.get("type") == "text":
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
    """ブラウザツールの設定を取得します"""
    return {
        "type": "function",
        "function": {
            "name": "browser_tools",
            "description": "ブラウザを操作するための様々なツールを提供します",
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "enum": [
                            "initialize_browser",
                            "close_browser",
                            "navigate_to_url",
                            "get_dom",
                            "click_element",
                            "input_text",
                            "take_screenshot",
                            "extract_links"
                        ],
                        "description": "使用するツールの名前"
                    },
                    "params": {
                        "type": "object",
                        "description": "ツールのパラメータ",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "ブラウザで開くURL"
                            },
                            "selector": {
                                "type": "string",
                                "description": "操作対象のDOM要素を指定するCSSセレクタ"
                            },
                            "text": {
                                "type": "string",
                                "description": "入力フィールドに入力するテキスト"
                            },
                            "extract_text_only": {
                                "type": "boolean",
                                "description": "DOMからテキストのみを抽出するかどうか"
                            }
                        }
                    }
                },
                "required": ["tool_name"]
            }
        }
    } 