"""
ブラウザ操作エージェントのメインエントリーポイント
"""
import logging
import sys
import boto3
from typing import Dict, Any, Optional

from agent.core import initialize_agent, get_system_prompt, handle_user_query
from agent.utils import setup_logging, debug_pause, is_debug_mode

# ロガーの設定
logger = logging.getLogger(__name__)

# CLIモードの実行関数 (引数なし)
def run_cli_mode() -> int:

    # --- ここで実行パラメータを設定 --- +
    query = "amazonで佐藤のごはんをカートに入れて購入までして" # 固定のクエリ
    model_id = "us.amazon.nova-premier-v1:0"
    credentials_path = "credentials/aws_credentials.json"
    debug = True # デバッグモードを無効にする場合は False
    # ------------------------------------ +

    setup_logging(debug) # agent.utils からインポートした関数を呼び出す
    logger.info(f"CLIモードで実行します - モデル: {model_id}") # 実行情報ログ
    
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
        # デバッグモードの場合、ブラウザを開いたままにして一時停止
        if is_debug_mode():
            debug_pause("クエリ処理エラーによりデバッグ停止します")
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

def main() -> int:
    """メインエントリーポイント"""

    # 引数なしでCLIモードを実行
    return run_cli_mode()

if __name__ == "__main__":
    sys.exit(main())
