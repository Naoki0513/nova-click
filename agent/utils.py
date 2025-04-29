import os
import json
import datetime
import inspect
import traceback
import sys
import logging
from typing import Dict, Any, Optional, Union, List

logger = logging.getLogger(__name__)

# Streamlit のインポートと関連変数を削除
# try:
#     import streamlit as st
#     STREAMLIT_AVAILABLE = True
# except ImportError:
#     STREAMLIT_AVAILABLE = False

def setup_logging(debug: bool = False) -> None:
    """
    アプリケーション全体のロギング設定を行います。

    引数:
        debug: デバッグモードを有効にするかどうか。Trueの場合、ログレベルはDEBUGに設定されます。
    """
    root_logger = logging.getLogger()

    # 既存のハンドラをすべて削除（設定の重複を防ぐため）
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    log_level = logging.DEBUG if debug else logging.INFO
    root_logger.setLevel(log_level)

    # コンソールハンドラを作成・設定
    console_handler = logging.StreamHandler(sys.stdout) # 標準出力へ
    console_handler.setLevel(log_level)

    # フォーマッタを設定
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    console_handler.setFormatter(formatter)

    # ハンドラをルートロガーに追加
    root_logger.addHandler(console_handler)

    # 設定完了をINFOレベルでログ出力（ただしハンドラ追加後）
    root_logger.info(f"ログレベルを{logging.getLevelName(log_level)}に設定しました")

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

        # INFOレベルでログ出力 (add_debug_log を使わないように変更)
        logger.info(f"認証情報を読み込み中: {full_path}")
        with open(full_path, 'r') as f:
            credentials = json.load(f)
            logger.info("認証情報を読み込みました")
            return credentials
    except Exception as e:
        error_msg = f"認証情報の読み込みに失敗しました: {e}"
        # ERRORレベルでログ出力 (add_debug_log を使わないように変更)
        logger.error(error_msg)
        # Streamlit のエラー表示を削除
        # if STREAMLIT_AVAILABLE and hasattr(st, 'session_state') and "log_placeholder" in st.session_state:
        #     st.error(error_msg)
        return None

# Streamlit UI 専用の display_debug_logs 関数を削除
# def display_debug_logs():
#     ... (関数全体を削除) ...

def add_debug_log(msg, group=None, level: str = "DEBUG"):
    """
    デバッグログメッセージを標準ロガーを使用して記録します。

    引数:
        msg: ログメッセージ (文字列、辞書、リスト、例外)
        group: ログのグループ名 (指定しない場合は呼び出し元の関数名を使用)
        level: ログレベル ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    """
    # Streamlit 関連のチェックと処理を削除
    # streamlit_active = False
    # ... (streamlit_active のチェックと関連処理を削除) ...

    # 呼び出し元の関数名を取得
    if group is None:
        try:
            frame = inspect.currentframe()
            if frame and frame.f_back:
                function_name = frame.f_back.f_code.co_name
                group = function_name
            else:
                group = "Unknown"
        except (AttributeError, ValueError):
            group = "Unknown"
        finally:
            del frame # 重要: フレームオブジェクトの参照を削除

    # --- メッセージのフォーマット ---
    log_entry_message_for_logger = None

    if isinstance(msg, (dict, list)):
        try:
            log_entry_message_for_logger = json.dumps(msg, ensure_ascii=False, indent=2)
        except TypeError:
            log_entry_message_for_logger = str(msg)
    elif isinstance(msg, Exception):
        log_entry_message_for_logger = f"Error: {str(msg)}\n{traceback.format_exc()}"
    else:
        log_entry_message_for_logger = str(msg)

    # --- 標準ロガーへの出力 ---
    log_output = f"[{group}] {log_entry_message_for_logger}"

    log_level_int = getattr(logging, level.upper(), logging.DEBUG) # 文字列から数値レベルに変換

    if log_level_int == logging.DEBUG:
        logger.debug(log_output)
    elif log_level_int == logging.INFO:
        logger.info(log_output)
    elif log_level_int == logging.WARNING:
        logger.warning(log_output)
    elif log_level_int == logging.ERROR:
        logger.error(log_output)
    elif log_level_int == logging.CRITICAL:
        logger.critical(log_output)
    else:
        logger.log(log_level_int, log_output) # 未知のレベルはlogメソッドで処理

    # Streamlit へのログエントリ返却を削除
    # return log_entry


def extract_text_from_assistant_message(message):
    """アシスタントメッセージからテキスト部分を抽出します。"""
    if not message:
        return ""

    text_parts = []

    # contentがリストの場合
    if isinstance(message.get("content"), list):
        for content in message.get("content", []):
            # "type" キーが存在しない、または "text" の場合
            if content.get("type", "text") == "text":
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
    """会話履歴をクリアします (CLI モードでは何もしません)。"""
    # Streamlit 関連の処理を削除
    # try:
    #     if STREAMLIT_AVAILABLE and hasattr(st, 'session_state') and "log_placeholder" in st.session_state:
    #         st.session_state["conversation_history"] = []
    #         add_debug_log("会話履歴をクリアしました", level="INFO") # Streamlit依存
    #     else:
    #         logger.info("Streamlit環境ではないため、会話履歴のクリアをスキップします")
    # except Exception as e:
    #     logger.error(f"会話履歴のクリア中にエラーが発生しました: {e}\n{traceback.format_exc()}")
    logger.info("CLIモードでは会話履歴のクリアはサポートされていません (何もしません)") # ログだけ残す
