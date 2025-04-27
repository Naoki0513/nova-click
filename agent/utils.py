import streamlit as st
import os
import json
import random
import string
import datetime
import inspect
import traceback
import sys # 標準エラー出力用にインポート

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
            
        add_debug_log(f"認証情報を読み込み中: {full_path}")
        with open(full_path, 'r') as f:
            credentials = json.load(f)
            add_debug_log("認証情報を読み込みました")
            return credentials
    except Exception as e:
        error_msg = f"認証情報の読み込みに失敗しました: {e}"
        add_debug_log(error_msg)
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
    デバッグログメッセージを処理します。
    Streamlit 環境ではセッション状態に追加し、それ以外では標準出力に出力します。

    引数:
        msg: ログメッセージ (文字列、辞書、リスト、例外)
        group: ログのグループ名 (指定しない場合は呼び出し元の関数名を使用)
    """
    # Streamlit セッション状態が利用可能かチェック
    # セッション状態自体が存在し、かつメインアプリで設定されるであろう
    # "log_placeholder" キーが存在するかで判断
    streamlit_active = False
    try:
        # st.session_state 自体が存在しない場合 AttributeError が発生する可能性
        if hasattr(st, 'session_state') and "log_placeholder" in st.session_state:
             streamlit_active = True
    except Exception:
         # st.session_state へのアクセスで予期せぬエラーが発生した場合も非アクティブ扱い
         streamlit_active = False

    # 呼び出し元の関数名を取得
    if group is None:
        try:
            frame = inspect.currentframe().f_back
            function_name = frame.f_code.co_name
            group = function_name
        except AttributeError:
            group = "Unknown"

    # タイムスタンプを取得
    now = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]

    # --- メッセージのフォーマット (共通処理) ---
    log_entry_message_for_streamlit = None # Streamlit用
    log_entry_message_for_print = None    # 標準出力用

    if isinstance(msg, (dict, list)):
        log_entry_message_for_streamlit = msg # Streamlitは元の形式を保持
        try:
            # 標準出力用はJSON文字列化を試みる
            log_entry_message_for_print = json.dumps(msg, ensure_ascii=False, indent=2)
        except TypeError:
            log_entry_message_for_print = str(msg)
    elif isinstance(msg, Exception):
        traceback_str = f"Error: {str(msg)}\\n{traceback.format_exc()}"
        log_entry_message_for_print = traceback_str
        log_entry_message_for_streamlit = { # Streamlit用は構造化
            "error": str(msg),
            "traceback": traceback.format_exc()
        }
    else:
        # 文字列の場合は両方同じ
        log_entry_message_for_print = str(msg)
        log_entry_message_for_streamlit = str(msg)

    # 返却用のログエントリ (Streamlit形式を基本とする)
    log_entry = {
        "timestamp": now,
        "message": log_entry_message_for_streamlit
    }

    if streamlit_active:
        # --- Streamlit 環境での処理 (従来通り) ---
        try:
            # デバッグログ辞書がなければ初期化
            if "debug_logs" not in st.session_state:
                st.session_state["debug_logs"] = {}

            # グループリストがなければ初期化
            if group not in st.session_state["debug_logs"]:
                st.session_state["debug_logs"][group] = []

            # ログを追加
            st.session_state["debug_logs"][group].append(log_entry)

            # 画面上のプレースホルダにリアルタイム表示
            placeholder = st.session_state.get("log_placeholder")
            if placeholder:
                 # 表示用のメッセージ整形
                 display_msg = ""
                 if isinstance(log_entry["message"], (dict, list)):
                     try:
                         # 辞書/リストはJSON文字列として表示
                         display_msg = json.dumps(log_entry["message"], ensure_ascii=False)
                     except TypeError:
                         display_msg = str(log_entry["message"]) # JSON化できなければ文字列
                 else:
                     display_msg = str(log_entry["message"])

                 # プレースホルダーに追記
                 with placeholder.container(): # container() を使って追記エリアを確保
                      st.text(f"{now} [{group}] {display_msg}")

        except Exception as e:
             # Streamlit 関連のエラーが発生した場合、標準エラーに出力
             print(f"ERROR in add_debug_log (Streamlit Active): {e}\\n{traceback.format_exc()}", file=sys.stderr, flush=True)

    else:
        # --- Streamlit 環境以外での処理 (標準出力) ---
        log_output = f"{now} [{group}] {log_entry_message_for_print}"
        print(log_output, flush=True)

    return log_entry # どちらのケースでもログエントリを返す

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
    # Streamlit 環境でのみ st.session_state を操作
    try:
        if hasattr(st, 'session_state') and "log_placeholder" in st.session_state:
            st.session_state["conversation_history"] = []
            add_debug_log("会話履歴をクリアしました") # この呼び出しも環境に応じて処理される
        else:
            print("clear_conversation_history: Not in Streamlit environment, skipping session state clear.", flush=True)
    except Exception as e:
        print(f"ERROR in clear_conversation_history: {e}\\n{traceback.format_exc()}", file=sys.stderr, flush=True)

def unicode_escape_str(s):
    """文字列内のUnicodeエスケープシーケンスを変換します。"""
    return s.encode('unicode-escape').decode('utf-8') 