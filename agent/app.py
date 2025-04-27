import streamlit as st
import boto3
import base64
import json
from .utils import add_debug_log, display_debug_logs, extract_text_from_assistant_message, clear_conversation_history
from .api_client import call_bedrock_converse_api, display_assistant_message, get_browser_tools_config
from .browser_tools import dispatch_browser_tool
from .prompts import get_system_prompt
from botocore.exceptions import ClientError
from typing import Dict, Any

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
    if "model_id" not in st.session_state:
        # デフォルトモデルをAmazon Nova Proに設定
        st.session_state["model_id"] = "us.amazon.nova-pro-v1:0"

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
            ["us.anthropic.claude-3-7-sonnet-20250219-v1:0", "us.amazon.nova-pro-v1:0"],
            index=0 if st.session_state["model_id"] == "us.anthropic.claude-3-7-sonnet-20250219-v1:0" else 1
        )
        # 選択されたモデルIDをセッション状態に保存
        st.session_state["model_id"] = model_id
        
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
                    display_assistant_message([
                        c for c in msg.get("content", [])
                        if c.get("type") == "text" or (c.get("type") is None and "text" in c)
                    ])

def display_screenshot(browser_container):
    """スクリーンショットの表示"""
    with browser_container:
        if "screenshot_data" in st.session_state:
            st.image(st.session_state["screenshot_data"])

def handle_user_input(user_input, bedrock_session, system_prompt=None):
    """ユーザー入力を処理します。 (Converse APIループ版)"""
    if not user_input:
        return

    add_debug_log(f"ユーザー入力: {user_input}")

    # システムプロンプト設定
    if not system_prompt:
        system_prompt = get_system_prompt()

    # 利用可能なツール仕様を取得
    tool_specs = get_browser_tools_config()
    tool_config = {
        "tools": tool_specs,
        "toolChoice": {"auto": {}}
    }

    # API仕様のメッセージリストを初期化
    messages = []
    # 初回ユーザーメッセージを追加
    messages.append({"role": "user", "content": [{"text": user_input}]})

    # stopReason が 'end_turn' になるまで繰り返す
    while True:
        # API呼び出しおよびエラー処理
        try:
            with st.spinner("回答を生成中..."):
                # 推論設定を取得
                inference_config = get_inference_config(st.session_state["model_id"])
                # リクエストパラメータを構築（topKはadditionalModelRequestFields経由）
                request_params = {
                    "modelId": st.session_state["model_id"],
                    "messages": messages,
                    "system": [{"text": system_prompt}],
                    "inferenceConfig": inference_config,
                    "toolConfig": tool_config
                }
                # Novaモデルではgreedy decodingとしてtopK=1をadditionalModelRequestFieldsで指定
                if "amazon.nova" in st.session_state["model_id"]:
                    # topKはadditionalModelRequestFields内のinferenceConfigとして渡す
                    request_params["additionalModelRequestFields"] = {"inferenceConfig": {"topK": 1}}
                # リクエストログ
                add_debug_log(request_params)
                # API呼び出し
                response = bedrock_session.converse(**request_params)
                # レスポンスログ
                add_debug_log(response)

                # トークン使用量を更新
                usage = response.get("usage", {})
                st.session_state["token_usage"]["inputTokens"] += usage.get("inputTokens", 0)
                st.session_state["token_usage"]["outputTokens"] += usage.get("outputTokens", 0)
                st.session_state["token_usage"]["totalTokens"] += usage.get("inputTokens", 0) + usage.get("outputTokens", 0)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            err_msg = e.response.get("Error", {}).get("Message", str(e))
            add_debug_log(f"API呼び出しエラー: {error_code} - {err_msg}")
            if error_code == "ModelErrorException":
                st.error("モデル内部で予期せぬエラーが発生しました。もう一度お試しください。")
            else:
                st.error(f"APIエラー: {error_code} - {err_msg}")
            break
        except Exception as e:
            err_msg = str(e)
            add_debug_log(f"想定外のエラー: {err_msg}")
            st.error(f"エラーが発生しました: {err_msg}")
            break

        output = response.get("output", {})
        message = output.get("message", {})
        stop_reason = response.get("stopReason")

        # アシスタントのテキスト応答表示
        for content in message.get("content", []):
            if "text" in content and content["text"].strip():
                st.markdown(content["text"])

        # 会話履歴にアシスタントメッセージ追加
        messages.append({"role": "assistant", "content": message.get("content", [])})

        # コンテンツに toolUse が含まれていれば必ず処理
        tool_calls = [c["toolUse"] for c in message.get("content", []) if "toolUse" in c]
        if tool_calls:
            for tool in tool_calls:
                tool_name = tool.get("name") or tool.get("tool_name") or tool.get("toolUseId")
                params = tool.get("input") or {}
                # ツール実行
                st.write(f"ツール実行: {tool_name}")
                if params:
                    st.json(params)
                result = dispatch_browser_tool(tool_name, params)
                st.write("実行結果:")
                st.json(result)

                # toolResult をユーザーメッセージとして追加
                tool_result_block = {
                    "toolResult": {
                        "toolUseId": tool.get("toolUseId"),
                        "content": [{"json": result}],
                        "status": "success"
                    }
                }
                messages.append({"role": "user", "content": [tool_result_block]})
            # ツール結果を踏まえて再度モデルに問い合わせ
            continue

        # end_turnなどでループを抜ける
        break

def get_inference_config(model_id: str) -> Dict[str, Any]:
    """
    モデルごとに最適な推論パラメータを返す
    """
    # 共通で許容される最大値。Nova Pro の推奨は ~3 000
    cfg = {"maxTokens": 3000}

    if "amazon.nova" in model_id:          # Nova 系
        cfg.update({"topP": 1, "temperature": 1})
    elif "anthropic.claude" in model_id:   # Claude 系（必要なら）
        cfg.update({"temperature": 0})   # 例
    return cfg


def run_app():
    """アプリケーションを実行します"""
    # セッション状態の初期化
    initialize_session_state()
    
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
            add_debug_log("認証情報を自動読み込みしました")
        else:
            st.error("認証情報の読み込みに失敗しました。credentials/aws_credentials.json を確認してください。")
    except Exception as e:
        st.error(f"認証情報読み込みエラー: {str(e)}")
    
    # リージョン (非表示)
    region = "us-west-2"
    
    # 入力フォーム - テキスト入力
    with user_input_container:
        user_input = st.text_input("ブラウザへの指示を入力してください")
        if user_input:
            if "credentials" in st.session_state:
                try:
                    # ユーザー入力を表示
                    with st.chat_message("user"):
                        st.markdown(user_input)

                    # Bedrock セッションの作成
                    bedrock_runtime = boto3.client(
                        service_name="bedrock-runtime",
                        region_name=region,
                        aws_access_key_id=st.session_state["credentials"].get("aws_access_key_id"),
                        aws_secret_access_key=st.session_state["credentials"].get("aws_secret_access_key")
                    )

                    # ユーザー入力を処理
                    with st.chat_message("assistant"):
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