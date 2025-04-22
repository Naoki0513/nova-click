import streamlit as st
import boto3
import base64
from .utils import add_debug_log, display_debug_logs, extract_text_from_assistant_message, clear_conversation_history, update_readme
from .api_client import call_bedrock_converse_api, display_assistant_message, get_browser_tools_config
from .browser_tools import dispatch_browser_tool
from .prompts import get_system_prompt

# セッション状態の初期化
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

def setup_page_layout():
    """ページレイアウトの設定"""
    # ページ設定
    st.set_page_config(page_title="ブラウザ操作エージェント", layout="wide")
    
    # サイドバーの設定
    with st.sidebar:
        st.title("ブラウザ操作エージェント")
        
        # モデル選択
        model_id = st.selectbox(
            "モデルID",
            ["us.anthropic.claude-3-7-sonnet-20250219-v1:0", "amazon.nova-pro-v1:0"]
        )
        
        # 会話履歴のクリアボタン
        if st.button("会話履歴をクリア"):
            clear_conversation_history()
            st.success("会話履歴をクリアしました")
    
    # コンテナの定義
    main_container = st.container()
    token_usage_container = st.container()
    conversation_container = st.container()
    user_input_container = st.container()
    browser_container = st.container()
    debug_container = st.container()
    
    # デバッグログのプレースホルダーを設定
    st.session_state["log_placeholder"] = debug_container
    
    return main_container, token_usage_container, conversation_container, user_input_container, browser_container, debug_container

def display_token_usage(token_usage_container):
    """トークン使用量とコストを表示"""
    with token_usage_container:
        if "token_usage" in st.session_state:
            usage = st.session_state["token_usage"]
            
            # コスト計算 (Claude-3-7-Sonnet の価格)
            input_cost = usage['inputTokens'] * 0.000003
            output_cost = usage['outputTokens'] * 0.000015
            
            # キャッシュ関連のコスト計算
            cache_read_cost = usage.get('cacheReadInputTokens', 0) * 0.0000003
            cache_write_cost = usage.get('cacheWriteInputTokens', 0) * 0.00000375
            
            # 総コストの計算
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
        
        # 水平線で区切り
        st.markdown("---")

def display_conversation_history(conversation_container):
    """会話履歴の表示"""
    with conversation_container:
        # 会話履歴の表示
        for i, msg in enumerate(st.session_state.get("conversation_history", [])):
            role = msg.get("role")
            
            if role == "user":
                with st.chat_message("user"):
                    st.markdown(extract_text_from_assistant_message(msg))
            
            elif role == "assistant":
                with st.chat_message("assistant"):
                    display_assistant_message([c for c in msg.get("content", []) if c.get("type") == "text"])

def display_screenshot(browser_container):
    """スクリーンショットの表示"""
    with browser_container:
        if "screenshot_data" in st.session_state:
            st.image(st.session_state["screenshot_data"])

def handle_user_input(user_input, bedrock_session, system_prompt=None):
    """ユーザー入力を処理します。"""
    if not user_input:
        return
    
    add_debug_log(f"ユーザー入力: {user_input}", "会話")
    
    # ユーザーのメッセージを会話履歴に追加
    st.session_state["conversation_history"].append({
        "role": "user",
        "content": [{"type": "text", "text": user_input}]
    })
    
    # システムプロンプトの設定（未指定の場合はデフォルト値を使用）
    if not system_prompt:
        system_prompt = get_system_prompt()
    
    # ツール設定
    toolConfig = get_browser_tools_config()
    
    # APIを呼び出す
    with st.spinner("回答を生成中..."):
        response, token_usage = call_bedrock_converse_api(
            user_input,
            st.session_state["conversation_history"],
            bedrock_session,
            system_prompt,
            toolConfig
        )
    
    # レスポンスからアシスタントの応答を取得
    if "error" in response:
        st.error(f"APIエラー: {response['error']}")
        return
    
    assistant_message = response.get("message", {})
    tool_calls = []
    
    # アシスタントのメッセージを会話履歴に追加
    st.session_state["conversation_history"].append(assistant_message)
    
    # ツール呼び出しがあるか確認
    for content in assistant_message.get("content", []):
        if content.get("type") == "tool_use":
            tool_calls.append(content)
    
    # テキスト応答を表示
    display_assistant_message([c for c in assistant_message.get("content", []) if c.get("type") == "text"])
    
    # ツール呼び出しがある場合は処理
    for tool_call in tool_calls:
        tool_input = tool_call.get("input", {})
        tool_name = tool_input.get("tool_name")
        params = tool_input.get("params", {})
        
        # ツール実行中のメッセージ
        with st.status(f"ツール実行中: {tool_name}", expanded=True):
            st.write(f"ツール: {tool_name}")
            if params:
                st.write("パラメータ:")
                st.json(params)
                
            # ツールのディスパッチ
            tool_result = dispatch_browser_tool(tool_name, params)
            
            # ツール結果を表示
            if tool_result:
                st.write("実行結果:")
                st.json(tool_result)
                
                # ツール結果を会話履歴に追加
                tool_result_content = {
                    "type": "tool_result",
                    "tool_use_id": tool_call.get("id"),
                    "result": tool_result
                }
                
                # 会話履歴の最後のメッセージを更新
                st.session_state["conversation_history"][-1]["content"].append(tool_result_content)
    
    # ツール結果を踏まえた続きの回答を取得
    if tool_calls:
        with st.spinner("ツール実行結果を分析中..."):
            follow_up_response, token_usage = call_bedrock_converse_api(
                "",  # 空のメッセージで続きを要求
                st.session_state["conversation_history"],
                bedrock_session,
                system_prompt,
                toolConfig
            )
        
        if "error" not in follow_up_response:
            follow_up_message = follow_up_response.get("message", {})
            
            # 会話履歴を更新
            st.session_state["conversation_history"][-1] = follow_up_message
            
            # 続きの応答を表示
            display_assistant_message([c for c in follow_up_message.get("content", []) if c.get("type") == "text"])
            
            # 新しいツール呼び出しがあれば再帰的に処理
            new_tool_calls = [c for c in follow_up_message.get("content", []) if c.get("type") == "tool_use"]
            if new_tool_calls:
                # 現在はシンプル化のため、再帰処理は略
                pass

def run_app():
    """アプリケーションを実行します"""
    # セッション状態の初期化
    initialize_session_state()
    
    # README.mdを更新
    update_readme()
    
    # ページレイアウトの設定
    main_container, token_usage_container, conversation_container, user_input_container, browser_container, debug_container = setup_page_layout()
    
    # トークン使用量の表示
    display_token_usage(token_usage_container)
    
    # メインコンテナにタイトルを表示
    with main_container:
        st.header("ブラウザを通じてWebを操作できます")
        st.markdown("指示を入力してください。例: 「Amazonで商品を検索して」「Googleマップで最寄りの駅を表示して」")
    
    # 会話履歴の表示
    display_conversation_history(conversation_container)
    
    # スクリーンショットの表示
    display_screenshot(browser_container)
    
    # 認証情報の読み込み
    try:
        credentials_path = "credentials/aws_credentials.json"
        from .utils import load_credentials
        credentials = load_credentials(credentials_path)
        if credentials:
            st.session_state["credentials"] = credentials
            add_debug_log("認証情報を自動読み込みしました", "認証")
        else:
            st.error("認証情報の読み込みに失敗しました。credentials/aws_credentials.json を確認してください。")
    except Exception as e:
        st.error(f"認証情報読み込みエラー: {str(e)}")
    
    # リージョン (非表示)
    region = "us-west-2"
    
    # 入力フォーム - チャットUIに変更
    with user_input_container:
        user_input = st.chat_input("ブラウザへの指示を入力してください")
        
        if user_input:
            if "credentials" in st.session_state:
                try:
                    # ユーザー入力を表示
                    with st.chat_message("user"):
                        st.markdown(user_input)
                    
                    # Bedrockセッションの作成
                    bedrock_runtime = boto3.client(
                        service_name="bedrock-runtime",
                        region_name=region,
                        aws_access_key_id=st.session_state["credentials"].get("aws_access_key_id"),
                        aws_secret_access_key=st.session_state["credentials"].get("aws_secret_access_key")
                    )
                    
                    # ユーザー入力を処理
                    with st.chat_message("assistant"):
                        with st.spinner("回答を生成中..."):
                            handle_user_input(
                                user_input,
                                bedrock_runtime,
                                get_system_prompt()
                            )
                except Exception as e:
                    st.error(f"エラーが発生しました: {str(e)}")
            else:
                st.error("認証情報を読み込めませんでした。credentials/aws_credentials.json を確認してください。")
    
    # デバッグログを表示
    display_debug_logs() 