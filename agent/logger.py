"""
ロギング設定モジュール
"""
import logging
import sys
from typing import Optional

def setup_logging(debug: bool = False) -> None:
    """
    アプリケーション全体のロギング設定を行います。
    
    引数:
        debug: デバッグモードを有効にするかどうか。Trueの場合、ログレベルはDEBUGに設定されます。
    """
    root_logger = logging.getLogger()
    
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    log_level = logging.DEBUG if debug else logging.INFO
    root_logger.setLevel(log_level)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    console_handler.setFormatter(formatter)
    
    root_logger.addHandler(console_handler)
    
    root_logger.info(f"ログレベルを{logging.getLevelName(log_level)}に設定しました")

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    指定された名前のロガーを取得します。
    
    引数:
        name: ロガー名。Noneの場合はルートロガーを返します。
        
    戻り値:
        指定された名前のロガーインスタンス
    """
    return logging.getLogger(name)
