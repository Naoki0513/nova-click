import os
import json
import datetime
import inspect
import traceback
import sys
import logging
from typing import Dict, Any, Optional, Union, List

logger = logging.getLogger(__name__)

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
            project_root = os.path.dirname(current_dir)  # src ディレクトリの親 = プロジェクトルート
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
        return None

def add_debug_log(msg, group=None, level: str = "DEBUG"):
    """
    デバッグログメッセージを標準ロガーを使用して記録します。

    引数:
        msg: ログメッセージ (文字列、辞書、リスト、例外)
        group: ログのグループ名 (指定しない場合は呼び出し元の関数名を使用)
        level: ログレベル ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    """

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

def log_json_debug(name: str, data: Union[Dict[Any, Any], List[Any]], level: str = "DEBUG"):
    """
    Pretty-print JSON data to logs if the specified log level is enabled.

    Args:
        name: ロググループ名
        data: JSONシリアライズ可能なdictまたはlist
        level: ログレベル文字列 ("DEBUG", "INFO" など)
    """
    log_level = getattr(logger, level.upper(), logging.DEBUG) if False else getattr(logging, level.upper(), logging.DEBUG)
    # 指定レベルが有効であれば出力およびファイルに保存
    if logger.isEnabledFor(log_level):
        try:
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.log(log_level, f"[{name}] JSON serialization error: {e}")
            return
        # コンソール出力
        logger.log(log_level, f"[{name}] JSON Data:\n{json_str}")
        # ファイル出力: log/YYYY-MM-DD_HH-MM-SS.json に整形済みJSONを1ファイルとして出力
        try:
            # プロジェクトルートの log ディレクトリを作成
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            log_dir = os.path.join(project_root, 'log')
            os.makedirs(log_dir, exist_ok=True)
            # タイムスタンプ付きファイル名
            now = datetime.datetime.now()
            file_name = now.strftime('%Y-%m-%d_%H-%M-%S') + '.json'
            file_path = os.path.join(log_dir, file_name)
            # 整形済みJSONファイルとして書き出し
            record = {
                'timestamp': now.isoformat(),
                'group': name,
                'level': level.upper(),
                'data': data
            }
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[{name}] ログファイルの書き込みに失敗しました: {e}") 