import streamlit as st
import os
import json
import random
import string
import datetime
import inspect
import traceback

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

def unicode_escape_str(s):
    """文字列内のUnicodeエスケープシーケンスを変換します。"""
    return s.encode('unicode-escape').decode('utf-8') 