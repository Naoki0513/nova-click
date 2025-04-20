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

def load_credentials(file_path):
    """JSONファイルから認証情報を読み込みます。"""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        abs_path = os.path.join(base_dir, file_path)
        with open(abs_path, 'r') as file:
            creds = json.load(file)
            return creds
    except FileNotFoundError:
        st.error(f"認証情報ファイルが見つかりません: {file_path}")
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
    return os.environ.get("BROWSER_SERVICE_URL", "http://localhost:5000")

def call_browser_api(endpoint, method="GET", params=None, data=None):
    """ブラウザサービスAPIを呼び出す"""
    base_url = get_browser_service_url()
    url = f"{base_url}/{endpoint}"
    
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
    return call_browser_api("navigate", method="POST", data={"url": url})

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
        bedrock_runtime = bedrock_session.client('bedrock-runtime', verify=False)
        messages = []
        
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
            messages.append({"role": "user", "content": user_message})
        elif isinstance(user_message, str):
            messages.append({"role": "user", "content": [{"text": user_message}]})
        elif isinstance(user_message, dict):
            messages.append({"role": "user", "content": [user_message]})
            
        # システムプロンプトが指定されている場合は設定
        system = []
        if system_prompt:
            system.append({"text": system_prompt})

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
        
        if toolConfig:
            request_details["toolConfig"] = toolConfig
        
        print("リクエスト詳細:")
        print(json.dumps(request_details, indent=2))
        
        try:
            response = bedrock_runtime.converse(**request_details)
            print("応答を受信しました")
            return response, request_details
        except Exception as e:
            print("Bedrock APIエラー:")
            print(str(e))
            return {}, request_details
    except Exception as e:
        print("一般エラー:")
        print(str(e))
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
        result = navigate_to(url)
        if result.get("status") == "success":
            # 移動後のスクリーンショットを取得
            screenshot_result = get_screenshot()
            return {
                "status": "success",
                "message": f"'{url}' に移動しました",
                "screenshot": screenshot_result.get("screenshot", "")
            }
        else:
            return {
                "status": "error",
                "message": result.get("message", f"'{url}' への移動に失敗しました")
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
    
    # 認証情報を取得
    credentials = load_credentials('credentials/aws_credentials.json')
    
    # ユーザー入力を履歴に追加し、すぐに表示
    st.session_state["chat_history"].append(("user", user_input))
    with st.chat_message("user"):
        st.write(user_input)
    
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
            bedrock_session = boto3.Session(
                aws_access_key_id=credentials['aws_access_key_id'],
                aws_secret_access_key=credentials['aws_secret_access_key'],
                region_name=credentials['region_name']
            )
            
            # 会話履歴を初期化
            conversation_history = []
            for role, content in st.session_state["chat_history"]:
                conversation_history.append((role, content))
            
            # システムプロンプトとツールの設定
            system_prompt = get_system_prompt()
            tools = get_browser_tools()
            
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
            
            # 会話実行のパラメータ
            conversation_ongoing = True
            current_message = user_input
            all_responses = []
            
            # 初回はブラウザの現在の状態を取得
            initial_screenshot = execute_screenshot_tool()
            initial_page_content = execute_get_page_content_tool()
            
            # 初期状態の情報をユーザーメッセージとして会話に追加
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
                }}
            ]
            conversation_history.append(("user", initial_context))
            
            # 会話ターンを順番に実行
            while conversation_ongoing:
                print(f"\n--- 会話ターン開始: {len(all_responses) + 1} ---")
                
                # クリーンな会話履歴（交互の役割を持つ）
                cleaned_history = ensure_alternating_roles(conversation_history)
                
                # Bedrockのconverse APIを呼び出し
                response, request_details = call_bedrock_converse_api(
                    user_message=current_message,
                    conversation_history=cleaned_history,
                    bedrock_session=bedrock_session,
                    system_prompt=system_prompt,
                    toolConfig={"tools": tools}
                )
                
                all_responses.append(response)
                
                # stopReasonの取得
                stop_reason = response.get('stopReason')
                print(f"Stop reason: {stop_reason}")
                
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
                    
                    # ツール使用部分を処理
                    for content in output_message.get('content', []):
                        if 'toolUse' in content:
                            tool_use = content['toolUse']
                            
                            # ツール使用情報をコンテンツに追加
                            assistant_content.append({
                                "toolUse": {
                                    "toolUseId": tool_use['toolUseId'],
                                    "name": tool_use['name'],
                                    "input": tool_use['input']
                                }
                            })
                            
                            tool_result = None
                            if tool_use["name"] == "screenshot":
                                # スクリーンショット撮影
                                tool_result = execute_screenshot_tool()
                            elif tool_use["name"] == "get_page_content":
                                # ページ内容取得
                                tool_result = execute_get_page_content_tool()
                            elif tool_use["name"] == "click_element":
                                # 要素クリック
                                element_description = tool_use["input"].get("element_description", "")
                                element_selector = tool_use["input"].get("element_selector", None)
                                tool_result = execute_click_element_tool(element_description, element_selector)
                            elif tool_use["name"] == "enter_text":
                                # テキスト入力
                                element_description = tool_use["input"].get("element_description", "")
                                text = tool_use["input"].get("text", "")
                                element_selector = tool_use["input"].get("element_selector", None)
                                tool_result = execute_enter_text_tool(element_description, text, element_selector)
                            elif tool_use["name"] == "navigate":
                                # ページ移動
                                url = tool_use["input"].get("url", "")
                                tool_result = execute_navigate_tool(url)
                            elif tool_use["name"] == "find_elements":
                                # 要素検索
                                description = tool_use["input"].get("description", None)
                                element_type = tool_use["input"].get("element_type", None)
                                tool_result = execute_find_elements_tool(description, element_type)
                            
                            if tool_result:
                                next_message = {
                                    "toolResult": {
                                        "toolUseId": tool_use["toolUseId"],
                                        "content": [{"text": json.dumps(tool_result, ensure_ascii=False)}],
                                        "status": tool_result["status"]
                                    }
                                }
                    
                    # すべての部分メッセージを単一の「assistant」エントリとして追加
                    if assistant_content:
                        conversation_history.append(("assistant", assistant_content))
                        
                        # リアルタイム応答: コールバック関数を呼び出し
                        response_callback("assistant", assistant_content)
                    
                    # 会話継続の判断
                    if stop_reason == 'end_turn':
                        print("会話ターン終了")
                        conversation_ongoing = False
                    elif stop_reason == 'tool_use':
                        # ツール使用後の次のリクエストを準備
                        conversation_history.append(("user", [next_message]))
                        current_message = next_message
                        print("ツール使用: 次のターンを開始します")
                    else:
                        # 予期しないstopReasonの場合
                        print(f"予期しないstopReason: {stop_reason}")
                        conversation_ongoing = False
                else:
                    print("予期しないレスポンス形式です。")
                    conversation_ongoing = False
            
            # 最後のターンを最終ターンとしてマーク
            if st.session_state["current_conversation_turns"]:
                st.session_state["current_conversation_turns"][-1]["is_final"] = True
                
                # 最終的なレスポンスのみをチャット履歴に追加
                final_content = st.session_state["current_conversation_turns"][-1]["content"]
                # チャット履歴に既に追加されているかを確認し、なければ追加
                if len(st.session_state["chat_history"]) < 2 or st.session_state["chat_history"][-1][1] != final_content:
                    st.session_state["chat_history"].append(("assistant", final_content))
            
            status.update(label="処理が完了しました", state="complete")
        except Exception as e:
            # エラーメッセージをチャットインターフェースに表示
            with assistant_placeholder.container():
                with st.chat_message("assistant", avatar="🤖"):
                    st.error(f"エラーが発生しました: {str(e)}")
            status.update(label=f"エラー: {str(e)}", state="error")
            # スタックトレース表示
            print(traceback.format_exc())

# --------------------------------------------------------
# メイン関数
# --------------------------------------------------------
def main():
    # ヘッダー
    st.title(f"{APP_NAME_JA}")
    st.markdown("自然言語で指示するだけで、Webブラウザを自動操作します")
    
    # サイドバー
    with st.sidebar:
        st.header("ブラウザ接続ステータス")
        
        try:
            # ブラウザサービスの状態確認
            service_url = get_browser_service_url()
            st.write(f"サービスURL: {service_url}")
            
            # ステータスチェック（簡易的なもの）
            try:
                status = call_browser_api("status", method="GET")
                if status.get("status") == "success":
                    st.success("ブラウザサービスに接続済み")
                    st.write(f"ブラウザタイプ: {status.get('browser_type', '不明')}")
                    st.write(f"現在のURL: {status.get('current_url', '不明')}")
                else:
                    st.error("ブラウザサービスに接続できていません")
            except Exception as e:
                st.error(f"ブラウザサービス接続エラー: {str(e)}")
            
            # 新しいURLに移動するフォーム
            with st.form("navigate_form"):
                url = st.text_input("URL入力", value="https://")
                navigate_submitted = st.form_submit_button("移動")
                
                if navigate_submitted and url:
                    result = navigate_to(url)
                    if result.get("status") == "success":
                        st.success(f"{url} に移動しました")
                    else:
                        st.error(f"移動エラー: {result.get('message', '不明なエラー')}")
        
        except Exception as e:
            st.error(f"エラーが発生しました: {str(e)}")
    
    # チャット履歴がなければ初期化
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
    
    # チャット履歴表示
    display_chat_history()
    
    # ユーザー入力
    user_input = st.chat_input("指示を入力してください（例：「Googleで猫の画像を検索して」）...")
    if user_input:
        process_user_input(user_input)

if __name__ == '__main__':
    main()