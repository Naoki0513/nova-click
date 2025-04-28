"""
ブラウザ操作エージェントのメインエントリーポイント
"""
import argparse
import logging
import sys
import webbrowser
import boto3
import time
import threading
from typing import Dict, Any, Optional

from agent.core import initialize_agent, get_system_prompt, handle_user_query
from streamlit.app import run_streamlit_app

# ロガーの設定
logger = logging.getLogger(__name__)

def setup_logging(debug: bool = False) -> None:
    """ロギングの設定"""
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler()]
    )
    logger.setLevel(log_level)
    logger.info(f"ログレベルを{logging.getLevelName(log_level)}に設定しました")

def launch_browser_in_background(url: str, delay: int = 2) -> None:
    """バックグラウンドでブラウザを起動する"""
    def _launch():
        time.sleep(delay)  # 少し待ってからブラウザを起動
        webbrowser.open(url)
        logger.info(f"ブラウザを起動しました: {url}")
    
    thread = threading.Thread(target=_launch)
    thread.daemon = True
    thread.start()

def run_cli_mode(query: str, model_id: str, credentials_path: str, debug: bool) -> int:
    """CLIモードで実行"""
    setup_logging(debug)
    logger.info(f"CLIモードで実行します - モデル: {model_id}")
    
    # エージェントを初期化
    init_result = initialize_agent(credentials_path)
    if init_result.get("status") != "success":
        logger.error(f"初期化に失敗しました: {init_result.get('message')}")
        return 1
    
    credentials = init_result.get("credentials")
    
    # Bedrock クライアントを作成
    bedrock_runtime = boto3.client(
        service_name="bedrock-runtime",
        region_name="us-west-2",
        aws_access_key_id=credentials.get("aws_access_key_id"),
        aws_secret_access_key=credentials.get("aws_secret_access_key")
    )
    
    # ユーザークエリを処理
    logger.info(f"クエリを処理します: {query}")
    result = handle_user_query(
        query,
        bedrock_runtime,
        get_system_prompt(),
        model_id
    )
    
    if result.get("status") == "error":
        logger.error(f"クエリ処理中にエラーが発生しました: {result.get('message')}")
        return 1
    
    # 結果を表示
    logger.info("処理が完了しました")
    for msg in result.get("messages", []):
        if msg.get("role") == "assistant":
            for content in msg.get("content", []):
                if "text" in content:
                    print(f"\n{content['text']}\n")
    
    # トークン使用量を表示
    token_usage = result.get("token_usage", {})
    logger.info(f"トークン使用量: 入力={token_usage.get('inputTokens', 0):,} 出力={token_usage.get('outputTokens', 0):,} 合計={token_usage.get('totalTokens', 0):,}")
    
    return 0

def run_ui_mode(debug: bool) -> int:
    """UIモードで実行"""
    setup_logging(debug)
    logger.info("UIモードで実行します")
    
    # ブラウザを自動起動
    launch_browser_in_background("http://localhost:8501")
    
    # Streamlitアプリを実行
    try:
        run_streamlit_app()
        return 0
    except Exception as e:
        logger.error(f"UIモード実行中にエラーが発生しました: {e}")
        return 1

def main() -> int:
    """メインエントリーポイント"""
    parser = argparse.ArgumentParser(description="ブラウザ操作エージェント")
    
    # サブコマンドの設定
    subparsers = parser.add_subparsers(dest="command", help="実行モード")
    
    # CLIモード用のパーサー
    cli_parser = subparsers.add_parser("cli", help="CLIモードで実行")
    cli_parser.add_argument("query", help="実行するクエリ/質問")
    cli_parser.add_argument("--model", "-m", default="us.anthropic.claude-3-7-sonnet-20250219-v1:0", 
                          help="使用するモデルID")
    cli_parser.add_argument("--credentials", "-c", default="credentials/aws_credentials.json",
                          help="AWS認証情報のパス")
    cli_parser.add_argument("--debug", "-d", action="store_true", help="デバッグモードを有効化")
    
    # UIモード用のパーサー
    ui_parser = subparsers.add_parser("ui", help="UIモード（Streamlit）で実行")
    ui_parser.add_argument("--debug", "-d", action="store_true", help="デバッグモードを有効化")
    
    # 引数をパース
    args = parser.parse_args()
    
    # コマンドに応じて処理を分岐
    if args.command == "cli":
        return run_cli_mode(args.query, args.model, args.credentials, args.debug)
    elif args.command == "ui":
        return run_ui_mode(args.debug)
    else:
        # デフォルトはUIモード
        parser.print_help()
        print("\nコマンドが指定されていません。デフォルトでUIモードを実行します。")
        return run_ui_mode(False)

if __name__ == "__main__":
    sys.exit(main())
