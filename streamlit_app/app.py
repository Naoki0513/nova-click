import streamlit as st
import boto3
import base64
import json
from agent.utils import add_debug_log, display_debug_logs, extract_text_from_assistant_message, clear_conversation_history
from agent.api.client import display_assistant_message
from agent.core import get_system_prompt, get_inference_config, handle_user_query
from agent.browser.worker import initialize_browser, shutdown_browser, _ensure_worker_initialized
from typing import Dict, Any

def initialize_session_state():
    """セッション状態の初期化"""
    if "conversation_history" not in st.session_state:
        st.session_state["conversation_history"] = []
    if "debug_logs" not in st.session_state:
        st.session_state["debug_logs"] = {}
    if "token_usage" not in st.session_state:
        st.session_state["token_usage"] = {
            "inputTokens": 0,
            "outputTokens": 0,
            "totalTokens": 0,
            "cacheReadInputTokens": 0,
            "cacheWriteInputTokens": 0
        }
    if "browser" not in st.session_state:
        st.session_state["browser"] = None
    if "page" not in st.session_state:
        st.session_state["page"] = None
    if "model_id" not in st.session_state:
        st.session_state["model_id"] = "us.amazon.nova-pro-v1:0"

def setup_page_layout():
    """ページレイアウトの設定"""
    with st.sidebar:
        st.title("ブラウザ操作エージェント")
        
        model_id = st.selectbox(
            "モデルID",
            ["us.anthropic.claude-3-7-sonnet-20250219-v1:0", "us.amazon.nova-pro-v1:0"],
            index=0 if st.session_state["model_id"] == "us.anthropic.claude-3-7-sonnet-20250219-v1:0" else 1
        )
        st.session_state["model_id"] = model_id
        
        if st.button("会話履歴をクリア"):
            clear_conversation_history()
            st.success("会話履歴をクリアしました")
    
    main_container = st.container()
    token_usage_container = st.container()
    conversation_container = st.container()
    user_input_container = st.container()
    browser_container = st.container()
    debug_container = st.container()
    
    st.session_state["log_placeholder"] = debug_container
    
    return main_container, token_usage_container, conversation_container, user_input_container, browser_container, debug_container

def display_token_usage(token_usage_container):
    """トークン使用量とコストを表示"""
    with token_usage_container:
        if "token_usage" in st.session_state:
            usage = st.session_state["token_usage"]
            
            input_cost = usage['inputTokens'] * 0.000003
            output_cost = usage['outputTokens'] * 0.000015
            
            cache_read_cost = usage.get('cacheReadInputTokens', 0) * 0.0000003
            cache_write_cost = usage.get('cacheWriteInputTokens', 0) * 0.00000375
            
            total_cost = input_cost + output_cost + cache_read_cost + cache_write_cost
            
            cols = st.columns([1, 1, 1, 1, 1, 1, 4])  # 列数を増やして右側に余白を作る
            with cols[0]:
                st.metric("入力トークン", f"{usage['inputTokens']:,}")
            with cols[1]:
                st.metric("出力トークン", f"{usage['outputTokens']:,}")
            with cols[2]:
                st.metric("合計トークン", f"{usage['totalTokens']:,}")
            with cols[3]:
                st.metric("キャッシュ読取", f"{usage.get('cacheReadInputTokens', 0):,}")
            with cols[4]:
                st.metric("キャッシュ書込", f"{usage.get('cacheWriteInputTokens', 0):,}")
            with cols[5]:
                st.metric("総コスト", f"${total_cost:.6f}")
        
        st.markdown("---")

def display_conversation_history(conversation_container):
    """会話履歴の表示"""
    with conversation_container:
        for i, msg in enumerate(st.session_state.get("conversation_history", [])):
            role = msg.get("role")
            
            if role == "user":
                with st.chat_message("user"):
                    st.markdown(extract_text_from_assistant_message(msg))
            
            elif role == "assistant":
                with st.chat_message("assistant"):
                    display_assistant_message([
                        c for c in msg.get("content", [])
                        if c.get("type") == "text" or (c.get("type") is None and "text" in c)
                    ])

def display_screenshot(browser_container):
    """スクリーンショットの表示"""
    with browser_container:
        if "screenshot_data" in st.session_state:
            st.image(st.session_state["screenshot_data"])

# Streamlitアプリケーションのメイン実行部分
st.set_page_config(page_title="ブラウザ操作エージェント", layout="wide")

initialize_session_state()

main_container, token_usage_container, conversation_container, user_input_container, browser_container, debug_container = setup_page_layout()

display_token_usage(token_usage_container)

with main_container:
    st.header("ブラウザを通じてWebを操作できます")
    st.markdown("指示を入力してください。例: 「Amazonで商品を検索して」「Googleマップで最寄りの駅を表示して」")

display_conversation_history(conversation_container)

display_screenshot(browser_container)

try:
    credentials_path = "credentials/aws_credentials.json"
    from agent.utils import load_credentials
    credentials = load_credentials(credentials_path)
    if credentials:
        st.session_state["credentials"] = credentials
        add_debug_log("認証情報を自動読み込みしました")
    else:
        st.error("認証情報の読み込みに失敗しました。credentials/aws_credentials.json を確認してください。")
except Exception as e:
    st.error(f"認証情報読み込みエラー: {str(e)}")

region = "us-west-2"

with user_input_container:
    user_input = st.text_input("ブラウザへの指示を入力してください")
    if user_input:
        if "credentials" in st.session_state:
            try:
                with st.chat_message("user"):
                    st.markdown(user_input)

                bedrock_runtime = boto3.client(
                    service_name="bedrock-runtime",
                    region_name=region,
                    aws_access_key_id=st.session_state["credentials"].get("aws_access_key_id"),
                    aws_secret_access_key=st.session_state["credentials"].get("aws_secret_access_key")
                )

                with st.chat_message("assistant"):
                    result = handle_user_query(
                        user_input,
                        bedrock_runtime,
                        get_system_prompt(),
                        st.session_state["model_id"],
                        st.session_state
                    )
                    
                    if "messages" in result:
                        st.session_state["conversation_history"].extend(result["messages"])
            except Exception as e:
                st.error(f"エラーが発生しました: {str(e)}")
        else:
            st.error("認証情報を読み込めませんでした。credentials/aws_credentials.json を確認してください。")

display_debug_logs()
