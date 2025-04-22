import streamlit as st
import streamlit.components.v1 as components
import json
import random
import string
import os
import time
import datetime
import re
from typing import List, Dict, Any, Tuple, Union
import uuid
import boto3
import base64
from collections import defaultdict
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# セッション状態の初期化
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

# ページレイアウト
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

# メインエリアの設定
main_container = st.container()

# トークン使用量の表示コンテナ
token_usage_container = st.container()

# 会話表示エリア
conversation_container = st.container()

# ユーザー入力エリア
user_input_container = st.container()

# ブラウザ表示エリア
browser_container = st.container()

# デバッグログ用のプレースホルダー
if "log_placeholder" not in st.session_state:
    st.session_state["log_placeholder"] = st.empty()

# デバッグログエリア (コンテナに変更)
debug_container = st.container()

# トークン使用量とコストを表示
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

# --------------------------------------------------------
# ユーティリティ関数
# --------------------------------------------------------
def random_id(length=28):
    """指定された長さのランダムな英数字IDを生成します。"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def load_credentials(file_path):
    """認証情報をJSONファイルから読み込みます。"""
    try:
        # 絶対パスで指定されている場合はそのまま使用
        if os.path.isabs(file_path):
            full_path = file_path
        else:
            # 相対パスの場合はプロジェクトルートからの相対パスとして扱う
            # 現在のファイルの場所を基準にプロジェクトルートへ
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)  # agent ディレクトリの親 = プロジェクトルート
            full_path = os.path.join(project_root, file_path)
            
        add_debug_log(f"認証情報を読み込み中: {full_path}", "認証")
        with open(full_path, 'r') as f:
            credentials = json.load(f)
            add_debug_log(f"認証情報を読み込みました", "認証")
            return credentials
    except Exception as e:
        error_msg = f"認証情報の読み込みに失敗しました: {e}"
        add_debug_log(error_msg, "エラー")
        st.error(error_msg)
        return None

def ensure_alternating_roles(conversation_history):
    """会話履歴が正しく交互のロールになっていることを確認します"""
    if not conversation_history:
        return conversation_history
    
    # 最後のメッセージのロールを確認
    last_role = conversation_history[-1]["role"]
    
    # もし最後のメッセージがアシスタントのものなら、ユーザーのメッセージが必要
    if last_role == "assistant":
        return conversation_history
    
    # もし最後のメッセージがユーザーのものなら、アシスタントのメッセージが必要
    if last_role == "user":
        conversation_history.append({
            "role": "assistant", 
            "content": [{"text": ""}]
        })
    
    return conversation_history

def display_debug_logs():
    """デバッグログをグループ化してJSON形式で表示します。"""
    if "log_placeholder" in st.session_state:
        # プレースホルダを使って表示
        with st.session_state["log_placeholder"].container():
            st.header("デバッグログ")
            if "debug_logs" in st.session_state:
                logs = st.session_state["debug_logs"]
                
                # グループごとにログを表示
                for group, entries in logs.items():
                    # 各グループのエントリ数を見出しで表示
                    st.subheader(f"🔍 {group} ({len(entries)}件)")
                    # ログエントリをJSON形式で表示
                    st.json(entries, expanded=False)

def add_debug_log(msg, group=None):
    """
    デバッグログメッセージをセッション状態に追加して自動的に表示します。
    
    引数:
        msg: ログメッセージ (文字列、辞書、リスト、例外)
        group: ログのグループ名 (指定しない場合は呼び出し元の関数名を使用)
    """
    import inspect
    import traceback
    
    # デバッグログが初期化されていない場合は初期化
    if "debug_logs" not in st.session_state:
        st.session_state["debug_logs"] = {}
    
    # 呼び出し元の関数名を取得
    if group is None:
        frame = inspect.currentframe().f_back
        function_name = frame.f_code.co_name
        group = function_name
    
    # グループが存在しない場合は初期化
    if group not in st.session_state["debug_logs"]:
        st.session_state["debug_logs"][group] = []
    
    # タイムスタンプを取得
    now = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    # メッセージをフォーマット
    if isinstance(msg, (dict, list)):
        formatted_msg = msg  # JSONとして直接保存
    elif isinstance(msg, Exception):
        formatted_msg = {
            "error": str(msg),
            "traceback": traceback.format_exc()
        }
    else:
        formatted_msg = str(msg)
    
    # ログエントリの作成
    log_entry = {
        "timestamp": now,
        "message": formatted_msg
    }
    
    # ログを追加
    st.session_state["debug_logs"][group].append(log_entry)
    
    return log_entry

# --------------------------------------------------------
# ブラウザ関連機能
# --------------------------------------------------------
def initialize_browser():
    """Playwrightブラウザを初期化します"""
    if st.session_state.get("browser") is None:
        try:
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(headless=False)
            page = browser.new_page()
            
            st.session_state["playwright"] = playwright
            st.session_state["browser"] = browser
            st.session_state["page"] = page
            
            add_debug_log("ブラウザを初期化しました", "ブラウザ")
            return True
        except Exception as e:
            add_debug_log(f"ブラウザ初期化エラー: {str(e)}", "エラー")
            return False
    return True

def close_browser():
    """ブラウザを閉じます"""
    if st.session_state.get("browser") is not None:
        try:
            st.session_state["browser"].close()
            st.session_state["playwright"].stop()
            
            st.session_state["browser"] = None
            st.session_state["page"] = None
            st.session_state["playwright"] = None
            
            add_debug_log("ブラウザを閉じました", "ブラウザ")
        except Exception as e:
            add_debug_log(f"ブラウザ終了エラー: {str(e)}", "エラー")

def navigate_to_url_tool(url=None):
    """指定されたURLに移動するツール"""
    if url is None:
        return {"error": "URLが指定されていません"}
    
    try:
        if not initialize_browser():
            return {"error": "ブラウザの初期化に失敗しました"}
        
        page = st.session_state["page"]
        page.goto(url)
        add_debug_log(f"URL {url} に移動しました", "ブラウザ")
        
        # 少し待ってからDOM取得
        time.sleep(1)
        content = get_page_content()
        
        return {
            "status": "success",
            "message": f"URL {url} に移動しました",
            "current_url": page.url,
            "page_title": page.title(),
            "content_preview": content[:200] + "..." if len(content) > 200 else content
        }
    except Exception as e:
        add_debug_log(f"URL移動エラー: {str(e)}", "エラー")
        return {"error": f"URL移動エラー: {str(e)}"}

def get_page_content():
    """現在のページのHTML内容を取得します"""
    if st.session_state.get("page") is None:
        return "ブラウザが初期化されていません"
    
    try:
        content = st.session_state["page"].content()
        return content
    except Exception as e:
        add_debug_log(f"ページ内容取得エラー: {str(e)}", "エラー")
        return f"ページ内容取得エラー: {str(e)}"

def get_dom_tool(selector=None, extract_text_only=False):
    """指定されたセレクタのDOM要素または全体のDOMを取得するツール"""
    if st.session_state.get("page") is None:
        return {"error": "ブラウザが初期化されていません"}
    
    try:
        page = st.session_state["page"]
        
        if selector:
            try:
                if extract_text_only:
                    # テキストのみを抽出
                    text_content = page.text_content(selector)
                    return {
                        "status": "success",
                        "text_content": text_content
                    }
                else:
                    # HTML要素を取得
                    html = page.inner_html(selector)
                    return {
                        "status": "success",
                        "html": html,
                        "element_exists": True
                    }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"セレクタ '{selector}' の要素が見つかりませんでした",
                    "element_exists": False
                }
        else:
            # 全体のDOMを取得
            full_html = page.content()
            # サイズ削減のためにBeautifulSoupで整形
            soup = BeautifulSoup(full_html, 'html.parser')
            return {
                "status": "success",
                "url": page.url,
                "title": page.title(),
                "html": str(soup)
            }
    except Exception as e:
        add_debug_log(f"DOM取得エラー: {str(e)}", "エラー")
        return {"error": f"DOM取得エラー: {str(e)}"}

def click_element_tool(selector=None):
    """指定されたセレクタの要素をクリックするツール"""
    if selector is None:
        return {"error": "セレクタが指定されていません"}
    
    if st.session_state.get("page") is None:
        return {"error": "ブラウザが初期化されていません"}
    
    try:
        page = st.session_state["page"]
        
        # 要素が表示されるまで少し待つ
        try:
            page.wait_for_selector(selector, timeout=5000)
        except:
            return {
                "status": "error",
                "message": f"セレクタ '{selector}' の要素が見つかりませんでした"
            }
        
        # クリック
        page.click(selector)
        add_debug_log(f"要素 '{selector}' をクリックしました", "ブラウザ")
        
        # 少し待ってからDOM取得
        time.sleep(1)
        
        return {
            "status": "success",
            "message": f"要素 '{selector}' をクリックしました",
            "current_url": page.url,
            "page_title": page.title()
        }
    except Exception as e:
        add_debug_log(f"クリックエラー: {str(e)}", "エラー")
        return {"error": f"クリックエラー: {str(e)}"}

def input_text_tool(selector=None, text=None):
    """指定されたセレクタの入力フィールドにテキストを入力するツール"""
    if selector is None or text is None:
        return {"error": "セレクタまたはテキストが指定されていません"}
    
    if st.session_state.get("page") is None:
        return {"error": "ブラウザが初期化されていません"}
    
    try:
        page = st.session_state["page"]
        
        # 要素が表示されるまで少し待つ
        try:
            page.wait_for_selector(selector, timeout=5000)
        except:
            return {
                "status": "error",
                "message": f"セレクタ '{selector}' の入力フィールドが見つかりませんでした"
            }
        
        # テキスト入力前にフィールドをクリア
        page.fill(selector, "")
        
        # テキスト入力
        page.fill(selector, text)
        add_debug_log(f"要素 '{selector}' にテキスト '{text}' を入力しました", "ブラウザ")
        
        return {
            "status": "success",
            "message": f"要素 '{selector}' にテキスト '{text}' を入力しました"
        }
    except Exception as e:
        add_debug_log(f"テキスト入力エラー: {str(e)}", "エラー")
        return {"error": f"テキスト入力エラー: {str(e)}"}

def take_screenshot_tool():
    """現在のページのスクリーンショットを取得するツール"""
    if st.session_state.get("page") is None:
        return {"error": "ブラウザが初期化されていません"}
    
    try:
        page = st.session_state["page"]
        screenshot_path = f"screenshot_{int(time.time())}.png"
        
        # スクリーンショット撮影
        page.screenshot(path=screenshot_path)
        add_debug_log(f"スクリーンショットを保存しました: {screenshot_path}", "ブラウザ")
        
        # 画像をbase64エンコード
        with open(screenshot_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        
        return {
            "status": "success",
            "message": f"スクリーンショットを取得しました",
            "file_path": screenshot_path,
            "base64_image": encoded_string
        }
    except Exception as e:
        add_debug_log(f"スクリーンショットエラー: {str(e)}", "エラー")
        return {"error": f"スクリーンショットエラー: {str(e)}"}

def extract_links_tool():
    """現在のページからすべてのリンクを抽出するツール"""
    if st.session_state.get("page") is None:
        return {"error": "ブラウザが初期化されていません"}
    
    try:
        page = st.session_state["page"]
        
        # ページ上のすべてのaタグを抽出
        links = page.evaluate("""
            () => {
                const anchors = Array.from(document.querySelectorAll('a'));
                return anchors.map(anchor => {
                    return {
                        text: anchor.textContent.trim(),
                        href: anchor.href,
                        id: anchor.id || null,
                        class: anchor.className || null,
                        selector: 'a[href="' + anchor.getAttribute('href') + '"]'
                    };
                });
            }
        """)
        
        add_debug_log(f"{len(links)}個のリンクを抽出しました", "ブラウザ")
        
        return {
            "status": "success",
            "links_count": len(links),
            "links": links
        }
    except Exception as e:
        add_debug_log(f"リンク抽出エラー: {str(e)}", "エラー")
        return {"error": f"リンク抽出エラー: {str(e)}"}

def unicode_escape_str(s):
    """文字列内のUnicodeエスケープシーケンスを変換します。"""
    return s.encode('unicode-escape').decode('utf-8')

# --------------------------------------------------------
# Bedrock Converse API関連
# --------------------------------------------------------
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

def extract_text_from_assistant_message(message):
    """アシスタントメッセージからテキスト部分を抽出します。"""
    if not message:
        return ""
    
    text_parts = []
    
    # contentがリストの場合
    if isinstance(message.get("content"), list):
        for content in message.get("content", []):
            if content.get("type") == "text":
                text = content.get("text", "")
                if text.strip():  # 空でない場合のみ追加
                    text_parts.append(text)
    # contentが辞書の場合（古い形式）
    elif isinstance(message.get("content"), dict):
        if "text" in message.get("content", {}):
            text = message.get("content", {}).get("text", "")
            if text.strip():
                text_parts.append(text)
    # contentが文字列の場合（最も古い形式）
    elif isinstance(message.get("content"), str):
        if message.get("content").strip():
            text_parts.append(message.get("content"))
    
    return "\n".join(text_parts)

def clear_conversation_history():
    """会話履歴をクリアします。"""
    st.session_state["conversation_history"] = []
    add_debug_log("会話履歴をクリアしました", "会話")

def update_readme():
    """README.mdファイルを更新します"""
    try:
        # プロジェクトルートディレクトリのパスを取得
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        readme_path = os.path.join(project_root, "README.md")
        
        # 現在のREADMEの内容を読み込む
        try:
            with open(readme_path, 'r', encoding='utf-8') as f:
                current_content = f.read()
        except:
            current_content = "# ブラウザ操作エージェント\n\n"
        
        # 現在時刻
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 新しい更新情報
        update_info = f"""
## 最終更新: {now}

### 機能
- Webブラウザの自動操作
- チャットベースのインターフェース
- 検索、クリック、フォーム入力などの操作
- スクリーンショット撮影機能
- リンク抽出機能

### 使用方法
1. サイドバーからモデルを選択
2. チャット入力欄にブラウザ操作の指示を入力
3. 結果を確認

### 技術仕様
- Streamlit: UIフレームワーク
- Playwright: ブラウザ自動化
- Amazon Bedrock: AI応答生成
- Claude 3 Sonnet: メインモデル
"""
        
        # 既存の内容を維持しつつ、更新情報を追加
        if "## 最終更新:" in current_content:
            # 更新情報のセクションを置き換え
            lines = current_content.split("\n")
            update_start = -1
            
            for i, line in enumerate(lines):
                if line.startswith("## 最終更新:"):
                    update_start = i
                    break
            
            if update_start >= 0:
                # タイトル部分を保持し、それ以降を更新
                new_content = "\n".join(lines[:update_start]) + update_info
            else:
                new_content = current_content + update_info
        else:
            # 更新情報がなければ追加
            new_content = current_content + update_info
        
        # ファイルに書き込み
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        add_debug_log(f"README.mdを更新しました: {readme_path}", "ファイル")
        return True
    except Exception as e:
        add_debug_log(f"README.md更新エラー: {str(e)}", "エラー")
        return False

# --------------------------------------------------------
# メイン関数
# --------------------------------------------------------
def handle_user_input(user_input, bedrock_session, bedrock_credentials, system_prompt, tools):
    """ユーザー入力を処理します。"""
    if not user_input:
        return
    
    add_debug_log(f"ユーザー入力: {user_input}", "会話")
    
    # 会話履歴を確保
    ensure_alternating_roles(st.session_state["conversation_history"])
    
    # ユーザーのメッセージを会話履歴に追加
    st.session_state["conversation_history"].append({
        "role": "user",
        "content": [{"type": "text", "text": user_input}]
    })
    
    # システムプロンプトの設定
    if not system_prompt:
        system_prompt = """
        あなたはウェブブラウザを操作するAIアシスタントです。
        ユーザーの指示に従って、ブラウザで様々な操作を行います。
        操作の結果を日本語で簡潔に説明してください。
        実行した操作の結果や、見つけた情報について詳細に報告してください。
        ウェブページの内容を理解し、適切なナビゲーションや操作を提案することができます。
        """
    
    # ツール設定
    toolConfig = {
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
                
            # ツールに応じた処理
            tool_result = None
            if tool_name == "initialize_browser":
                tool_result = {"status": "success", "message": "ブラウザを初期化しました"} if initialize_browser() else {"error": "ブラウザの初期化に失敗しました"}
            elif tool_name == "close_browser":
                close_browser()
                tool_result = {"status": "success", "message": "ブラウザを閉じました"}
            elif tool_name == "navigate_to_url":
                tool_result = navigate_to_url_tool(params.get("url"))
            elif tool_name == "get_dom":
                tool_result = get_dom_tool(
                    params.get("selector"), 
                    params.get("extract_text_only", False)
                )
            elif tool_name == "click_element":
                tool_result = click_element_tool(params.get("selector"))
            elif tool_name == "input_text":
                tool_result = input_text_tool(
                    params.get("selector"),
                    params.get("text")
                )
            elif tool_name == "take_screenshot":
                tool_result = take_screenshot_tool()
                
                # スクリーンショットをセッションに保存
                if "status" in tool_result and tool_result["status"] == "success":
                    # base64エンコードされた画像データをデコード
                    image_data = base64.b64decode(tool_result["base64_image"])
                    st.session_state["screenshot_data"] = image_data
                    
            elif tool_name == "extract_links":
                tool_result = extract_links_tool()
            
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
                # 再帰的にツール呼び出しを処理
                for tool_call in new_tool_calls:
                    # ... (同様の処理)
                    pass

def main():
    # README.mdを更新
    update_readme()
    
    # 認証情報を自動読み込み
    try:
        credentials_path = "credentials/aws_credentials.json"
        credentials = load_credentials(credentials_path)
        if credentials:
            st.session_state["credentials"] = credentials
            add_debug_log("認証情報を自動読み込みしました", "認証")
        else:
            st.error("認証情報の読み込みに失敗しました。credentials/aws_credentials.json を確認してください。")
    except Exception as e:
        st.error(f"認証情報読み込みエラー: {str(e)}")
    
    # システムプロンプト (非表示)
    system_prompt = """あなたはウェブブラウザを操作するAIアシスタントです。
ユーザーの指示に従って、ブラウザで様々な操作を行います。
操作の結果を日本語で簡潔に説明してください。
実行した操作の結果や、見つけた情報について詳細に報告してください。
ウェブページの内容を理解し、適切なナビゲーションや操作を提案することができます。
必要に応じてブラウザを初期化したり、閉じたりしてください。"""
    
    # リージョン (非表示)
    region = "us-west-2"
    
    # メインコンテナにタイトルを表示
    with main_container:
        st.header("ブラウザを通じてWebを操作できます")
        st.markdown("指示を入力してください。例: 「Amazonで商品を検索して」「Googleマップで最寄りの駅を表示して」")
    
    # 会話履歴の表示（質問と回答）
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
    
    # スクリーンショットがあれば表示
    with browser_container:
        if "screenshot_data" in st.session_state:
            st.image(st.session_state["screenshot_data"])
    
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
                                st.session_state["credentials"],
                                system_prompt,
                                None  # toolsは内部で設定
                            )
                except Exception as e:
                    st.error(f"エラーが発生しました: {str(e)}")
            else:
                st.error("認証情報を読み込めませんでした。credentials/aws_credentials.json を確認してください。")

    # デバッグログを表示
    with debug_container:
        # プレースホルダをコンテナに更新
        st.session_state["log_placeholder"] = debug_container
        display_debug_logs()

if __name__ == "__main__":
    main() 