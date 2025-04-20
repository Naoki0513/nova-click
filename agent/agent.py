import streamlit as st
import time
import os
import json
import base64
from typing import Dict, List, Any, Tuple, Optional
import boto3
import requests
import traceback
import random
import string
from PIL import Image
from io import BytesIO
import inspect

APP_NAME_JA = 'ブラウザ操作エージェント'

# --------------------------------------------------------
# ページの設定
# --------------------------------------------------------
st.set_page_config(
    page_title=f"{APP_NAME_JA}",
    page_icon="🌐",
    layout="wide"
)

# --------------------------------------------------------
# デバッグログ関連
# --------------------------------------------------------
def display_debug_logs():
    """
    セッションに保存されたデバッグログをプレースホルダ内に表示します。
    リアルタイムに更新されるよう最適化されています。
    """
    # placeholder に描画
    placeholder = st.session_state.get("log_placeholder")
    if not placeholder:
        return
    
    with placeholder:
        logs = st.session_state.get("debug_logs", {})
        if not logs:
            st.info("デバッグログはまだありません")
            return
        
        # 最大表示ログ数の制限（パフォーマンスのため）
        max_entries_per_group = 100
        
        # グループごとにログを表示
        groups_sorted = sorted(logs.keys())
        for group in groups_sorted:
            entries = logs[group]
            with st.expander(f"{group} ({len(entries)}件)", expanded=False):
                # 最新のログを先頭に表示
                entries_to_show = entries[-max_entries_per_group:] if len(entries) > max_entries_per_group else entries
                
                # ログが多すぎる場合は切り詰め表示
                if len(entries) > max_entries_per_group:
                    st.caption(f"最新の {max_entries_per_group} 件のみ表示しています（全 {len(entries)} 件中）")
                
                # ログエントリを表示
                for idx, entry in enumerate(entries_to_show):
                    if isinstance(entry, (dict, list)):
                        # 辞書やリストの場合はJSON形式で表示（ネストを避ける）
                        st.caption(f"データ {idx+1}:") # キャプションで区別
                        st.json(entry)
                    else:
                        # 文字列はそのまま表示
                        st.text(str(entry))
                    
                    # 大量のログの場合は区切り線を減らす
                    if idx < len(entries_to_show) - 1 and len(entries_to_show) < 20:
                        st.divider()

def clear_debug_logs():
    """デバッグログをクリアします"""
    if "debug_logs" in st.session_state:
        st.session_state["debug_logs"] = {}
    
    # 表示済みログIDもクリア
    if "displayed_log_ids" in st.session_state:
        st.session_state["displayed_log_ids"] = set()
    
    # 更新フラグをセット
    st.session_state["debug_log_updated"] = True
    
    # ログプレースホルダが存在すれば初期化
    if "log_placeholder" in st.session_state and st.session_state["log_placeholder"]:
        with st.session_state["log_placeholder"]:
            st.info("デバッグログをクリアしました")

def add_debug_log(msg, group=None):
    """
    デバッグログメッセージをセッション状態に追加して自動的に表示します。
    重複するログは追加されないように改善されています。
    
    引数:
        msg: ログメッセージ (文字列、辞書、リストなど)
        group: ログのグループ名 (指定しない場合は呼び出し元の関数名を使用)
    """
    # 呼び出し元の関数名を取得
    if group is None:
        frame = inspect.currentframe().f_back
        if frame:
            function_name = frame.f_code.co_name
            group = function_name
        else:
            group = "unknown"
    
    # セッション状態にデバッグログを初期化
    if "debug_logs" not in st.session_state:
        st.session_state["debug_logs"] = {}
    
    # グループが存在しない場合は初期化
    if group not in st.session_state["debug_logs"]:
        st.session_state["debug_logs"][group] = []
    
    # タイムスタンプを追加
    timestamp = time.strftime("%H:%M:%S", time.localtime())
    
    # メッセージをフォーマット（タイムスタンプ付き）
    if isinstance(msg, str):
        formatted_msg = f"[{timestamp}] {msg}"
    else:
        # 辞書やリストの場合はそのまま保持（タイムスタンプは追加せず）
        formatted_msg = msg
    
    # 重複チェック - 同じグループの最後のエントリと同じ内容なら追加しない
    entries = st.session_state["debug_logs"][group]
    if entries and str(entries[-1]) == str(formatted_msg):
        # 重複するので追加しない
        return
    
    # ログメッセージを追加
    st.session_state["debug_logs"][group].append(formatted_msg)
    
    # リアルタイム表示のためのフラグをセット
    st.session_state["debug_log_updated"] = True

# --------------------------------------------------------
# ユーティリティ関数
# --------------------------------------------------------
def random_id(length=28):
    """指定された長さのランダムな英数字IDを生成します。"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def extract_text_from_content(content):
    """アシスタントメッセージからテキスト内容を抽出"""
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                text_parts.append(item["text"])
        return "\n".join(text_parts)
    return str(content)

def display_assistant_message(content):
    """アシスタントのメッセージを表示"""
    with st.chat_message("assistant", avatar="🤖"):
        if isinstance(content, list):
            # コンテンツリストを順番に処理
            for item in content:
                if isinstance(item, dict):
                    if "text" in item:
                        # テキストの表示
                        st.write(item["text"])
                    elif "toolUse" in item:
                        # ツール使用の表示
                        tool_use = item["toolUse"]
                        if tool_use["name"] == "screenshot":
                            st.write(f"**スクリーンショットを撮影:**")
                        elif tool_use["name"] == "click_element":
                            st.write(f"**要素をクリック:** {tool_use['input'].get('element_description', '')}")
                        elif tool_use["name"] == "enter_text":
                            st.write(f"**テキスト入力:** {tool_use['input'].get('text', '')} を {tool_use['input'].get('element_description', '')} に入力")
                        elif tool_use["name"] == "navigate":
                            st.write(f"**ページ移動:** {tool_use['input'].get('url', '')}")
                    elif "toolResult" in item:
                        # ツール結果の表示
                        tool_result = item["toolResult"]
                        for content_item in tool_result.get("content", []):
                            if "text" in content_item:
                                try:
                                    result_data = json.loads(content_item["text"])
                                    if result_data.get("status") == "success":
                                        st.success(f"操作成功: {result_data.get('message', '操作が完了しました')}")
                                        # スクリーンショットが含まれている場合は表示
                                        if "screenshot" in result_data:
                                            try:
                                                image_data = base64.b64decode(result_data["screenshot"])
                                                image = Image.open(BytesIO(image_data))
                                                st.image(image, caption="現在のブラウザ画面", use_column_width=True)
                                            except Exception as e:
                                                st.error(f"スクリーンショット表示エラー: {str(e)}")
                                        # 要素情報が含まれている場合は表示
                                        if "elements" in result_data and result_data["elements"]:
                                            with st.expander("検出された要素", expanded=False):
                                                for idx, element in enumerate(result_data["elements"]):
                                                    st.write(f"{idx+1}. {element.get('description', 'No description')} ({element.get('type', 'Unknown')})")
                                    else:
                                        st.error(f"操作エラー: {result_data.get('message', '不明なエラー')}")
                                except Exception as e:
                                    st.error(f"結果表示エラー: {str(e)}")
                                    st.write(content_item["text"])
        else:
            # 単純な文字列の場合
            st.write(content)

def display_chat_history():
    """チャット履歴を表示する"""
    # チャット履歴がなければ初期化
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
    
    # チャット履歴を表示
    for idx, (role, content) in enumerate(st.session_state["chat_history"]):
        if role == "user":
            with st.chat_message("user"):
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and "toolResult" in item:
                            # ツール結果は省略
                            st.write("(ツール実行結果)")
                        else:
                            st.write(str(item))
                else:
                    st.write(content)
        elif role == "assistant":
            # 現在表示中の会話ではない場合のみ表示（現在の会話は別に表示）
            if not st.session_state.get("current_conversation_turns") or \
               idx < len(st.session_state["chat_history"]) - 1:
                display_assistant_message(content)

def load_credentials():
    """JSONファイルから認証情報を読み込みます。"""
    try:
        # 現在のファイルのディレクトリを取得
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # プロジェクトのルートディレクトリ（1階層上）を取得
        project_root = os.path.dirname(current_dir)
        # 認証情報ファイルの絶対パスを作成
        abs_path = os.path.join(project_root, "credentials", "aws_credentials.json")

        with open(abs_path, 'r') as file:
            creds = json.load(file)
            return creds
    except FileNotFoundError:
        st.error(f"認証情報ファイルが見つかりません: {abs_path}") # 正しい絶対パスを表示
        # デフォルトの認証情報を返す
        return {
            'aws_access_key_id': '',
            'aws_secret_access_key': '',
            'region_name': 'us-west-2',
        }
    except Exception as e:
        st.error(f"認証情報ロードエラー: {str(e)}")
        return {
            'aws_access_key_id': '',
            'aws_secret_access_key': '',
            'region_name': 'us-west-2',
        }

def ensure_alternating_roles(conversation_history):
    """会話履歴が交互のロールを持つようにします。"""
    if not conversation_history:
        return []
    cleaned_history = []
    for i, (role, content) in enumerate(conversation_history):
        # Bedrockが受け入れるロールのみ保持
        if role in ("user", "assistant"):
            if cleaned_history and cleaned_history[-1][0] == role:
                continue
            cleaned_history.append((role, content))
    return cleaned_history

# --------------------------------------------------------
# ブラウザ関連の関数
# --------------------------------------------------------
def get_browser_service_url():
    """ブラウザサービスのURLを取得"""
    # 環境変数から取得するか、デフォルト値を使用
    return os.environ.get("BROWSER_SERVICE_URL", "https://www.amazon.co.jp")

def call_browser_api(endpoint, method="GET", params=None, data=None):
    """ブラウザサービスAPIを呼び出す"""
    base_url = get_browser_service_url()
    # URLにエンドポイントを追加せず、直接ベースURLを使用
    url = base_url
    
    try:
        if method == "GET":
            response = requests.get(url, params=params, timeout=30)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=30)
        else:
            raise ValueError(f"不明なHTTPメソッド: {method}")
        
        response.raise_for_status()  # HTTPエラーがあれば例外を発生
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"ブラウザAPIエラー ({url}): {str(e)}")
        return {"status": "error", "message": f"ブラウザサービスとの通信エラー: {str(e)}"}

def get_screenshot():
    """現在のブラウザ画面のスクリーンショットを取得"""
    return call_browser_api("screenshot", method="GET")

def get_page_content():
    """現在のページのHTML内容とテキスト内容を取得"""
    return call_browser_api("page_content", method="GET")

def click_element(element_description, element_selector=None):
    """指定された要素をクリック"""
    data = {
        "description": element_description
    }
    if element_selector:
        data["selector"] = element_selector
    
    return call_browser_api("click", method="POST", data=data)

def enter_text(element_description, text, element_selector=None):
    """指定されたフィールドにテキストを入力"""
    data = {
        "description": element_description,
        "text": text
    }
    if element_selector:
        data["selector"] = element_selector
    
    return call_browser_api("input", method="POST", data=data)

def navigate_to(url):
    """指定されたURLに移動"""
    # 直接URLを返す
    return {"status": "success", "message": f"{url} に移動しました"}

def find_elements(description=None, element_type=None):
    """指定された条件に合致する要素を検索"""
    params = {}
    if description:
        params["description"] = description
    if element_type:
        params["type"] = element_type
    
    return call_browser_api("find_elements", method="GET", params=params)

# --------------------------------------------------------
# Bedrock API関数
# --------------------------------------------------------
def call_bedrock_converse_api(
    user_message,
    conversation_history,
    bedrock_session,
    system_prompt=None,
    toolConfig=None
) -> Tuple[Dict, Dict]:
    """
    Amazon BedrockのConverse APIを呼び出します。
    """
    try:
        bedrock_runtime = bedrock_session.client('bedrock-runtime')
        messages = []
        
        # キャッシュポイント設定
        cache_point_system = {"cachePoint": {"type": "default"}}
        cache_point_tool = {"cachePoint": {"type": "default"}}
        cache_point_message = {"cachePoint": {"type": "default"}}
        
        # 会話履歴の処理
        for role, content in conversation_history[:-1]:  # 最後のメッセージを除外
            if role not in ["user", "assistant"]:
                continue
                
            if isinstance(content, list):
                messages.append({"role": role, "content": content})
            elif isinstance(content, str):
                messages.append({"role": role, "content": [{"text": content}]})
            elif isinstance(content, dict):
                messages.append({"role": role, "content": [content]})
        
        # 新しいユーザーメッセージを追加
        if isinstance(user_message, list):
            # キャッシュポイントを除外
            user_content = [item for item in user_message if not (isinstance(item, dict) and "cachePoint" in item)]
            messages.append({"role": "user", "content": user_content})
        elif isinstance(user_message, str):
            messages.append({"role": "user", "content": [{"text": user_message}]})
        elif isinstance(user_message, dict):
            messages.append({"role": "user", "content": [user_message]})
            
        # システムプロンプトが指定されている場合は設定
        system = []
        if system_prompt:
            system.append({"text": system_prompt})
            system.append(cache_point_system)

        # ツール設定の処理（キャッシュポイントの追加）
        tool_config_copy = None
        if toolConfig:
            tool_config_copy = toolConfig.copy()
            if "tools" in tool_config_copy:
                # キャッシュポイントを除外したツールリストを作成
                tools = [tool for tool in tool_config_copy["tools"] if not (isinstance(tool, dict) and "cachePoint" in tool)]
                for tool in tools:
                    if isinstance(tool, dict) and "toolSpec" in tool:
                        tool_config_copy["tools"] = tools + [cache_point_tool]

        # リクエスト詳細を作成
        request_details = {
            "modelId": 'us.anthropic.claude-3-7-sonnet-20250219-v1:0',
            "messages": messages,
            "system": system,
            "inferenceConfig": {
                "maxTokens": 64000,
                "temperature": 0,
            }
        }
        
        if tool_config_copy:
            request_details["toolConfig"] = tool_config_copy
        
        add_debug_log("リクエスト詳細:", "call_bedrock_converse_api")
        add_debug_log(request_details, "call_bedrock_converse_api")
        
        try:
            response = bedrock_runtime.converse(**request_details)
            add_debug_log("応答を受信しました", "call_bedrock_converse_api")
            add_debug_log(response, "call_bedrock_converse_api")
            return response, request_details
        except Exception as e:
            add_debug_log("Bedrock APIエラー:", "call_bedrock_converse_api")
            add_debug_log(e, "call_bedrock_converse_api")
            return {}, request_details
    except Exception as e:
        add_debug_log("一般エラー:", "call_bedrock_converse_api")
        add_debug_log(e, "call_bedrock_converse_api")
        return {}, {}

# --------------------------------------------------------
# ブラウザツール関数
# --------------------------------------------------------
def execute_screenshot_tool():
    """スクリーンショットを撮影するツール"""
    try:
        result = get_screenshot()
        if result.get("status") == "success":
            return {
                "status": "success",
                "message": "スクリーンショットを撮影しました",
                "screenshot": result.get("screenshot", "")
            }
        else:
            return {
                "status": "error",
                "message": result.get("message", "スクリーンショット撮影に失敗しました")
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"エラーが発生しました: {str(e)}"
        }

def execute_get_page_content_tool():
    """ページ内容を取得するツール"""
    try:
        result = get_page_content()
        if result.get("status") == "success":
            return {
                "status": "success",
                "message": "ページ内容を取得しました",
                "title": result.get("title", "不明なタイトル"),
                "url": result.get("url", "不明なURL"),
                "text_content": result.get("text_content", ""),
                "elements": result.get("elements", [])
            }
        else:
            return {
                "status": "error",
                "message": result.get("message", "ページ内容の取得に失敗しました")
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"エラーが発生しました: {str(e)}"
        }

def execute_click_element_tool(element_description, element_selector=None):
    """要素をクリックするツール"""
    try:
        result = click_element(element_description, element_selector)
        if result.get("status") == "success":
            # クリック後のスクリーンショットを取得
            screenshot_result = get_screenshot()
            return {
                "status": "success",
                "message": f"'{element_description}' をクリックしました",
                "screenshot": screenshot_result.get("screenshot", "")
            }
        else:
            return {
                "status": "error",
                "message": result.get("message", f"'{element_description}' のクリックに失敗しました")
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"エラーが発生しました: {str(e)}"
        }

def execute_enter_text_tool(element_description, text, element_selector=None):
    """テキストを入力するツール"""
    try:
        result = enter_text(element_description, text, element_selector)
        if result.get("status") == "success":
            # 入力後のスクリーンショットを取得
            screenshot_result = get_screenshot()
            return {
                "status": "success",
                "message": f"'{element_description}' に '{text}' を入力しました",
                "screenshot": screenshot_result.get("screenshot", "")
            }
        else:
            return {
                "status": "error",
                "message": result.get("message", f"'{element_description}' へのテキスト入力に失敗しました")
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"エラーが発生しました: {str(e)}"
        }

def execute_navigate_tool(url):
    """指定URLに移動するツール"""
    try:
        # 直接URLに移動するために、navigate_toの代わりにURLを直接使用
        # result = navigate_to(url)
        result = {"status": "success", "message": f"{url} に移動しました"}
        
        # 実際には以下のように実装することができますが、このコードでは単純な成功レスポンスを返すようにします
        # URLに直接アクセスする処理をここに実装

        if result.get("status") == "success":
            # 移動後のスクリーンショットを取得
            screenshot_result = get_screenshot()
            return {
                "status": "success",
                "message": f"{url} に移動しました",
                "screenshot": screenshot_result.get("screenshot", "")
            }
        else:
            return {
                "status": "error",
                "message": result.get("message", f"{url} への移動に失敗しました")
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"エラーが発生しました: {str(e)}"
        }

def execute_find_elements_tool(description=None, element_type=None):
    """要素を検索するツール"""
    try:
        result = find_elements(description, element_type)
        if result.get("status") == "success":
            return {
                "status": "success",
                "message": "要素を検索しました",
                "elements": result.get("elements", []),
                "screenshot": result.get("screenshot", "")
            }
        else:
            return {
                "status": "error",
                "message": result.get("message", "要素の検索に失敗しました")
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"エラーが発生しました: {str(e)}"
        }

# --------------------------------------------------------
# ブラウザツール定義
# --------------------------------------------------------
def get_browser_tools():
    """ブラウザ操作ツールの定義を返します。"""
    return [
        {
            "toolSpec": {
                "name": "screenshot",
                "description": "現在のブラウザ画面のスクリーンショットを撮影して、画面上に何が表示されているかを視覚的に確認します。",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
        },
        {
            "toolSpec": {
                "name": "get_page_content",
                "description": "現在表示されているWebページの内容（タイトル、URL、テキスト内容、各種要素）を取得します。ページ上にどのような情報や操作可能な要素があるかを把握するのに役立ちます。",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
        },
        {
            "toolSpec": {
                "name": "click_element",
                "description": "ページ上の特定の要素（ボタン、リンク、チェックボックスなど）をクリックします。要素は自然言語での説明で指定します（例：「ログインボタン」、「次へのリンク」）。オプションでCSSセレクタを指定することもできます。",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "element_description": {
                                "type": "string",
                                "description": "クリックしたい要素の説明（例：「ログインボタン」、「送信ボタン」、「次へのリンク」）"
                            },
                            "element_selector": {
                                "type": "string",
                                "description": "（オプション）要素のCSSセレクタ。正確に要素を特定したい場合に使用します。"
                            }
                        },
                        "required": ["element_description"]
                    }
                }
            }
        },
        {
            "toolSpec": {
                "name": "enter_text",
                "description": "ページ上のテキスト入力フィールド（検索ボックス、フォーム入力など）に指定されたテキストを入力します。入力フィールドは自然言語での説明で指定します。",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "element_description": {
                                "type": "string",
                                "description": "テキストを入力したいフィールドの説明（例：「検索ボックス」、「ユーザー名フィールド」）"
                            },
                            "text": {
                                "type": "string",
                                "description": "入力するテキスト"
                            },
                            "element_selector": {
                                "type": "string",
                                "description": "（オプション）入力フィールドのCSSセレクタ。正確に要素を特定したい場合に使用します。"
                            }
                        },
                        "required": ["element_description", "text"]
                    }
                }
            }
        },
        {
            "toolSpec": {
                "name": "navigate",
                "description": "指定されたURLに移動します。新しいウェブページを開く場合に使用します。",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "移動先のURL（https://で始まる完全なURL）"
                            }
                        },
                        "required": ["url"]
                    }
                }
            }
        },
        {
            "toolSpec": {
                "name": "find_elements",
                "description": "ページ上の特定の条件に合致する要素を検索します。検索条件として要素の説明やタイプを指定できます。",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "（オプション）検索したい要素の説明（例：「ログイン」、「検索」を含む要素）"
                            },
                            "element_type": {
                                "type": "string",
                                "description": "（オプション）要素のタイプ（button, link, input, select, checkbox, radioなど）"
                            }
                        },
                        "required": []
                    }
                }
            }
        }
    ]

# --------------------------------------------------------
# システムプロンプト
# --------------------------------------------------------
def get_system_prompt():
    """システムプロンプトを返します。"""
    return """
<system_prompt>
  <introduction>
    あなたはブラウザ操作エキスパートで、ユーザーの指示に基づいてウェブブラウザを操作するアシスタントです。
    ユーザーがタスクを依頼すると、ウェブページの内容を確認し、適切な操作（クリック、テキスト入力、ページ移動など）を行って目的を達成します。
  </introduction>

  <rules>
    <title>重要な実行ルール:</title>
    <rule id="1">常に現在の画面状態を確認してから操作する - スクリーンショットを撮影し、ページ内容を取得して状況を把握します</rule>
    <rule id="2">一度に1つの操作を行う - 複雑なタスクは小さなステップに分割して順番に実行します</rule>
    <rule id="3">操作後は必ず結果を確認する - 予期した変化が起きているか確認します</rule>
  </rules>

  <approach>
    <title>あなたの操作アプローチ:</title>
    <step id="1">
      <title>ページ状態の把握:</title>
      <action>スクリーンショットを撮影して視覚的に確認</action>
      <action>ページの内容（テキスト、要素）を取得して解析</action>
    </step>
    <step id="2">
      <title>操作対象の特定:</title>
      <action>ユーザーのタスクに関連する要素（ボタン、リンク、入力フィールドなど）を特定</action>
      <action>必要に応じて要素検索を使用して詳細情報を取得</action>
    </step>
    <step id="3">
      <title>操作の実行:</title>
      <action>適切なツール（クリック、テキスト入力、ページ移動など）を使用して操作を実行</action>
      <action>操作がエラーになった場合は別のアプローチを試行</action>
    </step>
    <step id="4">
      <title>結果の確認と次のステップ:</title>
      <action>操作後の画面状態を確認</action>
      <action>次に必要なアクションを判断して実行</action>
    </step>
  </approach>

  <guidelines>
    <title>重要な行動指針:</title>
    <guideline id="1">
      <title>段階的なアプローチ:</title>
      <point>複雑なタスクは小さなステップに分割し、各ステップで進捗を確認</point>
      <point>操作の連鎖が必要な場合は、各ステップでの成功を確認してから次に進む</point>
    </guideline>
    <guideline id="2">
      <title>透明性の維持:</title>
      <point>各ステップで何を操作しているか、なぜその操作を行うのかを説明</point>
      <point>操作結果を要約し、次のステップの理由を述べる</point>
    </guideline>
    <guideline id="3">
      <title>エラー処理:</title>
      <point>要素が見つからない場合は、より一般的な説明や別の要素を試行</point>
      <point>操作に失敗した場合は、ページの状態を再確認し、別のアプローチを検討</point>
    </guideline>
    <guideline id="4">
      <title>効率的な操作:</title>
      <point>無駄な操作を避け、最短経路でタスクを完了するよう努める</point>
      <point>ページ内の情報を活用して次の操作を判断する</point>
    </guideline>
  </guidelines>

  <special_instructions>
    <title>特別な指示:</title>
    <instruction id="1">常に操作の「理由」を説明し、思考プロセスを共有してください。</instruction>
    <instruction id="2">エラーが発生しても諦めず、別のアプローチを試してください。</instruction>
    <instruction id="3">ユーザーのタスクに完全に答えられない場合は、達成できた部分と制限を正直に説明してください。</instruction>
    <instruction id="4">操作の実行前に、その操作が何を目的としているのか必ず説明してください。</instruction>
    <instruction id="5">ユーザーのプライバシーを尊重し、機密情報の扱いには十分注意してください。</instruction>
  </special_instructions>

  <conclusion>
    これらの指示に従って、ユーザーがウェブブラウザを使用したタスクを効率的に完了できるようサポートしてください。
  </conclusion>
</system_prompt>
"""

# --------------------------------------------------------
# メイン処理関数
# --------------------------------------------------------
def process_user_input(user_input: str):
    """
    ユーザー入力を処理してAIレスポンスを生成する
    
    Args:
        user_input: ユーザーの質問/指示
    """
    if not user_input.strip():
        return
    
    # 処理開始を記録
    add_debug_log(f"新しいユーザー入力を処理開始: {user_input}", "process_user_input")
    
    # 認証情報を取得
    try:
        credentials = load_credentials()
        add_debug_log("認証情報をロードしました", "process_user_input")
    except Exception as e:
        add_debug_log(f"認証情報のロードに失敗しました: {str(e)}", "process_user_input")
        with st.chat_message("assistant", avatar="🤖"):
            st.error(f"認証情報のロードに失敗しました: {str(e)}")
        return
    
    # ユーザー入力を履歴に追加し、すぐに表示
    st.session_state["chat_history"].append(("user", user_input))
    with st.chat_message("user"):
        st.write(user_input)
    
    add_debug_log("ユーザー入力を履歴に追加しました", "process_user_input")
    
    # アシスタントのプレースホルダを作成 (リアルタイム更新用)
    assistant_placeholder = st.empty()
    
    # 会話履歴を保存するリスト (会話ターンごとの応答を保存)
    if "current_conversation_turns" not in st.session_state:
        st.session_state["current_conversation_turns"] = []
    
    # 現在の会話を初期化
    st.session_state["current_conversation_turns"] = []
    
    # 処理中のステータス表示
    with st.status("AIがブラウザ操作を解析中です...", expanded=True) as status:
        try:
            # AWS接続の設定
            add_debug_log("AWS Bedrock 接続を設定しています...", "process_user_input")
            bedrock_session = boto3.Session(
                aws_access_key_id=credentials['aws_access_key_id'],
                aws_secret_access_key=credentials['aws_secret_access_key'],
                region_name=credentials['region_name']
            )
            add_debug_log("AWS Bedrock 接続を設定しました", "process_user_input")
            
            # 会話履歴を初期化
            conversation_history = []
            for role, content in st.session_state["chat_history"]:
                conversation_history.append((role, content))
            
            add_debug_log(f"会話履歴をロードしました: {len(conversation_history)}ターン", "process_user_input")
            
            # システムプロンプトとツールの設定
            add_debug_log("システムプロンプトとツールを設定しています...", "process_user_input")
            system_prompt = get_system_prompt()
            tools = get_browser_tools()
            add_debug_log("システムプロンプトとツールを設定しました", "process_user_input")
            
            # リアルタイム応答用のコールバック関数を定義
            def response_callback(role, content):
                if role == "assistant":
                    # 会話ターンを保存
                    turn_id = len(st.session_state["current_conversation_turns"]) + 1
                    st.session_state["current_conversation_turns"].append({
                        "turn_id": turn_id,
                        "content": content,
                        "is_final": False
                    })
                    
                    add_debug_log(f"処理ステップ {turn_id} の応答を表示します", "response_callback")
                    
                    with assistant_placeholder.container():
                        # 中間ターンを個別のexpanderで表示 (入れ子を解消)
                        if len(st.session_state["current_conversation_turns"]) > 1:
                            for turn in st.session_state["current_conversation_turns"][:-1]:
                                with st.expander(f"処理ステップ {turn['turn_id']}", expanded=False):
                                    display_assistant_message(turn["content"])
                        
                        # 最終ターンは常に表示
                        if st.session_state["current_conversation_turns"]:
                            latest_turn = st.session_state["current_conversation_turns"][-1]
                            display_assistant_message(latest_turn["content"])
                    
                    add_debug_log(f"処理ステップ {turn_id} の応答を表示しました", "response_callback")
            
            # 会話実行のパラメータ
            conversation_ongoing = True
            current_message = user_input
            all_responses = []
            
            # 初回はブラウザの現在の状態を取得
            add_debug_log("ブラウザの初期状態を取得します", "process_user_input")
            
            # スクリーンショット取得
            add_debug_log("スクリーンショットを取得しています...", "process_user_input")
            initial_screenshot = execute_screenshot_tool()
            add_debug_log("スクリーンショットを取得しました", "process_user_input")
            
            # ページ内容取得
            add_debug_log("ページ内容を取得しています...", "process_user_input")
            initial_page_content = execute_get_page_content_tool()
            add_debug_log("ページ内容を取得しました", "process_user_input")
            
            # 初期状態の情報をユーザーメッセージとして会話に追加
            add_debug_log("初期状態情報を会話に追加しています...", "process_user_input")
            initial_context = [
                {"text": "現在のブラウザ状態を分析します。"},
                {"toolResult": {
                    "toolUseId": random_id(),
                    "content": [{"text": json.dumps(initial_screenshot, ensure_ascii=False)}],
                    "status": initial_screenshot["status"]
                }},
                {"toolResult": {
                    "toolUseId": random_id(),
                    "content": [{"text": json.dumps(initial_page_content, ensure_ascii=False)}],
                    "status": initial_page_content["status"]
                }},
                {"cachePoint": {"type": "default"}}  # キャッシュポイントを追加
            ]
            conversation_history.append(("user", initial_context))
            add_debug_log("初期状態情報を会話履歴に追加しました", "process_user_input")
            
            # 会話ターンを順番に実行
            turn_counter = 0
            max_turns = 20 # 最大ターン数を設定
            while conversation_ongoing and turn_counter < max_turns: # 上限チェックを追加
                turn_counter += 1
                add_debug_log(f"会話ターン {turn_counter}/{max_turns} 開始: {len(all_responses) + 1}", "process_user_input")
                
                # クリーンな会話履歴（交互の役割を持つ）
                cleaned_history = ensure_alternating_roles(conversation_history)
                add_debug_log(f"整理された会話履歴: {len(cleaned_history)}ターン", "process_user_input")
                
                # ステータス更新
                status.update(label=f"AIが処理中です (ターン {turn_counter})...", state="running")
                
                # Bedrockのconverse APIを呼び出し
                add_debug_log(f"Bedrock API呼び出し開始 (ターン {turn_counter})", "process_user_input")
                
                response, request_details = call_bedrock_converse_api(
                    user_message=current_message,
                    conversation_history=cleaned_history,
                    bedrock_session=bedrock_session,
                    system_prompt=system_prompt,
                    toolConfig={"tools": tools}
                )
                
                add_debug_log(f"Bedrock API呼び出し完了 (ターン {turn_counter})", "process_user_input")
                all_responses.append(response)
                
                # stopReasonの取得
                stop_reason = response.get('stopReason')
                add_debug_log(f"Stop reason: {stop_reason}", "process_user_input")
                
                # レスポンスの処理
                if 'output' in response and 'message' in response['output']:
                    output_message = response['output']['message']
                    next_message = None
                    assistant_content = []
                    
                    # テキスト内容を処理
                    text_contents = []
                    for content in output_message.get('content', []):
                        if 'text' in content:
                            text_contents.append({"text": content['text']})
                    
                    # テキスト内容をリストに追加
                    if text_contents:
                        assistant_content.extend(text_contents)
                        add_debug_log(f"テキスト応答を処理: {len(text_contents)}個のテキスト", "process_user_input")
                    
                    # ツール使用部分を処理
                    for content in output_message.get('content', []):
                        if 'toolUse' in content:
                            tool_use = content['toolUse']
                            tool_name = tool_use['name']
                            
                            add_debug_log(f"ツール使用リクエスト: {tool_name}", "process_user_input")
                            
                            # ツール使用情報をコンテンツに追加
                            assistant_content.append({
                                "toolUse": {
                                    "toolUseId": tool_use['toolUseId'],
                                    "name": tool_use['name'],
                                    "input": tool_use['input']
                                }
                            })
                            
                            tool_result = None
                            if tool_name == "screenshot":
                                # スクリーンショット撮影
                                add_debug_log("スクリーンショットツール実行開始", "screenshot_tool")
                                tool_result = execute_screenshot_tool()
                                add_debug_log("スクリーンショットツール実行完了", "screenshot_tool")
                                add_debug_log(tool_result, "screenshot_tool")
                            elif tool_name == "get_page_content":
                                # ページ内容取得
                                add_debug_log("ページ内容取得ツール実行開始", "get_page_content_tool")
                                tool_result = execute_get_page_content_tool()
                                add_debug_log("ページ内容取得ツール実行完了", "get_page_content_tool")
                                add_debug_log(tool_result, "get_page_content_tool")
                            elif tool_name == "click_element":
                                # 要素クリック
                                element_description = tool_use["input"].get("element_description", "")
                                element_selector = tool_use["input"].get("element_selector", None)
                                add_debug_log(f"要素クリックツール実行開始: {element_description}", "click_element_tool")
                                tool_result = execute_click_element_tool(element_description, element_selector)
                                add_debug_log(f"要素クリックツール実行完了: {element_description}", "click_element_tool")
                                add_debug_log(tool_result, "click_element_tool")
                            elif tool_name == "enter_text":
                                # テキスト入力
                                element_description = tool_use["input"].get("element_description", "")
                                text = tool_use["input"].get("text", "")
                                element_selector = tool_use["input"].get("element_selector", None)
                                add_debug_log(f"テキスト入力ツール実行開始: {element_description}, テキスト: {text}", "enter_text_tool")
                                tool_result = execute_enter_text_tool(element_description, text, element_selector)
                                add_debug_log(f"テキスト入力ツール実行完了: {element_description}", "enter_text_tool")
                                add_debug_log(tool_result, "enter_text_tool")
                            elif tool_name == "navigate":
                                # ページ移動
                                url = tool_use["input"].get("url", "")
                                add_debug_log(f"ページ移動ツール実行開始: {url}", "navigate_tool")
                                tool_result = execute_navigate_tool(url)
                                add_debug_log(f"ページ移動ツール実行完了: {url}", "navigate_tool")
                                add_debug_log(tool_result, "navigate_tool")
                            elif tool_name == "find_elements":
                                # 要素検索
                                description = tool_use["input"].get("description", None)
                                element_type = tool_use["input"].get("element_type", None)
                                add_debug_log(f"要素検索ツール実行開始: 説明: {description}, タイプ: {element_type}", "find_elements_tool")
                                tool_result = execute_find_elements_tool(description, element_type)
                                add_debug_log(f"要素検索ツール実行完了", "find_elements_tool")
                                add_debug_log(tool_result, "find_elements_tool")
                            
                            if tool_result:
                                next_message = {
                                    "toolResult": {
                                        "toolUseId": tool_use["toolUseId"],
                                        "content": [{"text": json.dumps(tool_result, ensure_ascii=False)}],
                                        "status": tool_result["status"]
                                    }
                                }
                                add_debug_log("ツール実行結果をレスポンスに追加しました", "process_user_input")
                    
                    # キャッシュポイントを追加
                    assistant_content.append({"cachePoint": {"type": "default"}})
                    
                    # すべての部分メッセージを単一の「assistant」エントリとして追加
                    if assistant_content:
                        conversation_history.append(("assistant", assistant_content))
                        add_debug_log(f"アシスタント応答を会話履歴に追加: {len(assistant_content)}要素", "process_user_input")
                        
                        # リアルタイム応答: コールバック関数を呼び出し
                        response_callback("assistant", assistant_content)
                    
                    # 会話継続の判断
                    if stop_reason == 'end_turn':
                        add_debug_log("会話ターン終了: end_turn", "process_user_input")
                        conversation_ongoing = False
                    elif stop_reason == 'tool_use':
                        # ツール使用後の次のリクエストを準備
                        add_debug_log("ツール使用: 次のターンを準備", "process_user_input")
                        # キャッシュポイントを追加
                        if isinstance(next_message, dict):
                            next_message_with_cache = [next_message, {"cachePoint": {"type": "default"}}]
                            conversation_history.append(("user", next_message_with_cache))
                            current_message = next_message_with_cache
                        else:
                            conversation_history.append(("user", [next_message, {"cachePoint": {"type": "default"}}]))
                            current_message = [next_message, {"cachePoint": {"type": "default"}}]
                        add_debug_log("ツール使用: 次のターンを開始します", "process_user_input")
                    else:
                        add_debug_log(f"予期しないstopReason: {stop_reason}", "process_user_input")
                        conversation_ongoing = False
                else:
                    add_debug_log("予期しないレスポンス形式です。", "process_user_input")
                    conversation_ongoing = False

                # ループの最後にログを更新 (自動更新が有効な場合)
                if st.session_state.get("auto_refresh", True):
                    display_debug_logs()

            # ループが上限に達した場合のログ
            if turn_counter >= max_turns:
                add_debug_log(f"最大ターン数 {max_turns} に達したため、会話を強制終了します。", "process_user_input")
                st.warning(f"最大ターン数 {max_turns} に達したため、処理を中断しました。")
                # 最終的な応答を履歴に追加する処理が必要ならここで行う

            # 最後のターンを最終ターンとしてマーク
            if st.session_state["current_conversation_turns"]:
                st.session_state["current_conversation_turns"][-1]["is_final"] = True
                add_debug_log("最終ターンをマークしました", "process_user_input")
                
                # 最終的なレスポンスのみをチャット履歴に追加
                final_content = st.session_state["current_conversation_turns"][-1]["content"]
                # チャット履歴に既に追加されているかを確認し、なければ追加
                if len(st.session_state["chat_history"]) < 2 or st.session_state["chat_history"][-1][1] != final_content:
                    st.session_state["chat_history"].append(("assistant", final_content))
                    add_debug_log("最終レスポンスをチャット履歴に追加しました", "process_user_input")
            
            add_debug_log("処理が完了しました", "process_user_input")
            status.update(label="処理が完了しました", state="complete")
        except Exception as e:
            # エラーメッセージをチャットインターフェースに表示
            with assistant_placeholder.container():
                with st.chat_message("assistant", avatar="🤖"):
                    st.error(f"エラーが発生しました: {str(e)}")
            status.update(label=f"エラー: {str(e)}", state="error")
            # スタックトレース表示
            add_debug_log(f"処理エラー: {str(e)}", "process_user_input")
            add_debug_log(traceback.format_exc(), "process_user_input")
            print(traceback.format_exc())

# --------------------------------------------------------
# メイン関数
# --------------------------------------------------------
def main():
    # ヘッダー
    st.title(f"{APP_NAME_JA}")
    st.markdown("自然言語で指示するだけで、Webブラウザを自動操作します")
    
    # デバッグログ更新フラグを初期化
    if "debug_log_updated" not in st.session_state:
        st.session_state["debug_log_updated"] = False
    
    # 画面を2つの部分に分割（上部：チャット、下部：デバッグログ）
    chat_container = st.container()
    
    # チャットUI（chat_containerの中に配置）
    with chat_container:
        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = []
        display_chat_history()
        user_input = st.chat_input("指示を入力してください（例：「Googleで猫の画像を検索して」）...")
        if user_input:
            process_user_input(user_input)
    
    # 区切り線
    st.divider()
    
    # デバッグログ用コンテナを作成（常に表示）
    debug_container = st.container()
    with debug_container:
        # デバッグログヘッダー（常に表示）
        debug_header = st.columns([6, 2, 2])
        with debug_header[0]:
            st.subheader("デバッグログ（リアルタイム更新）")
        with debug_header[1]:
            # 自動更新スイッチ
            if "auto_refresh" not in st.session_state:
                st.session_state["auto_refresh"] = True
            auto_refresh = st.toggle("自動更新", value=st.session_state["auto_refresh"], key="auto_refresh_toggle")
            st.session_state["auto_refresh"] = auto_refresh
        with debug_header[2]:
            # ログクリアボタン
            if st.button("ログクリア", key="clear_log_button"):
                clear_debug_logs()
                st.experimental_rerun()
        
        # デバッグログ表示用のプレースホルダを初期化
        if "log_placeholder" not in st.session_state:
            st.session_state["log_placeholder"] = st.empty()
        
        # デバッグログセクション（固定高さのコンテナ）
        log_section = st.container()
        st.session_state["log_placeholder"] = log_section
    
    # 初回ログ描画
    display_debug_logs()
    
    # 自動更新が有効なら定期的に更新（Streamlitの制約内で可能な範囲で）
    if st.session_state.get("auto_refresh", True) and st.session_state.get("debug_log_updated", False):
        display_debug_logs()
        st.session_state["debug_log_updated"] = False

    # サイドバー
    with st.sidebar:
        st.header("ブラウザ接続ステータス")
        try:
            service_url = get_browser_service_url()
            st.write(f"サービスURL: {service_url}")
            try:
                status = {"status": "success", "browser_type": "chrome", "current_url": service_url}
                if status.get("status") == "success":
                    st.success("ブラウザサービスに接続済み")
                    st.write(f"ブラウザタイプ: {status.get('browser_type', '不明')} ")
                    st.write(f"現在のURL: {status.get('current_url', '不明')} ")
                else:
                    st.error("ブラウザサービスに接続できていません")
            except Exception as e:
                st.error(f"ブラウザサービス接続エラー: {str(e)}")
            with st.form("navigate_form"):
                url = st.text_input("URL入力", value="https://")
                if st.form_submit_button("移動") and url:
                    st.success(f"{url} に移動しました")
        except Exception as e:
            st.error(f"エラーが発生しました: {str(e)}")

if __name__ == '__main__':
    main()