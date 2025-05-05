"""
ブラウザ操作エージェントのメインエントリーポイント
"""
import logging
import sys
from typing import Dict, Any, Optional

from src.utils import setup_logging, debug_pause, is_debug_mode, load_credentials
from src.browser import initialize_browser, get_aria_snapshot, cleanup_browser
from src.tools import get_browser_tools_config, dispatch_browser_tool
from src.prompts import get_system_prompt
from src.message import create_initial_messages, create_user_facing_messages, add_assistant_message, create_tool_result_message
from src.bedrock import create_bedrock_client, call_bedrock_api, analyze_stop_reason, extract_tool_calls, update_token_usage

# ロガーの設定
logger = logging.getLogger(__name__)

# CLIモードの実行関数 (引数なし)
def run_cli_mode() -> int:

    # --- ここで実行パラメータを設定 --- +
    query = "Amazonでイヤホンを調べてカートに入れてください" # 固定のクエリ
    model_id = "us.amazon.nova-pro-v1:0"
    credentials_path = "credentials/aws_credentials.json"
    debug = False # デバッグモードを無効にする場合は False
    max_turns = 20  # 最大対話ターン数
    # ------------------------------------ +

    setup_logging(debug) # ログを設定
    logger.info(f"CLIモードで実行します - モデル: {model_id}") # 実行情報ログ
    
    # ブラウザを初期化
    init_result = initialize_browser()
    if init_result.get("status") != "success":
        logger.error(f"ブラウザ初期化に失敗しました: {init_result.get('message')}")
        return 1
    
    # AWS認証情報を読み込み
    credentials = load_credentials(credentials_path)
    if not credentials:
        logger.error(f"認証情報の読み込みに失敗しました: {credentials_path}")
        return 1
    
    # Bedrock クライアントを作成
    bedrock_runtime = create_bedrock_client(credentials)
    
    # 結果用データ構造を初期化
    result = {
        "status": "success",
        "messages": [], # 最終的にユーザーに見せるためのメッセージ履歴
        "token_usage": {
            "inputTokens": 0,
            "outputTokens": 0,
            "totalTokens": 0,
        }
    }
    
    # ユーザークエリを処理
    logger.info(f"クエリを処理します: {query}")
    
    # ツール設定を取得
    tool_config = {
        "tools": get_browser_tools_config(),
        "toolChoice": {"auto": {}}
    }
    
    # 初回リクエスト時、現在のARIA Snapshotを取得
    aria_snapshot_result = get_aria_snapshot()
    current_aria_snapshot = aria_snapshot_result.get('aria_snapshot') if aria_snapshot_result.get('status') == 'success' else None
    if not current_aria_snapshot:
        logger.error(f"ARIA Snapshotの取得に失敗しました: {aria_snapshot_result.get('message', '不明なエラー')}")
    
    # Bedrock APIに渡すためのメッセージ履歴（内部管理用）
    messages_for_api = create_initial_messages(query, current_aria_snapshot)
    
    # ユーザーに表示するためのメッセージ履歴
    result["messages"] = create_user_facing_messages(query)
    
    # 対話ループを開始
    turn_count = 0
    
    while turn_count < max_turns:
        turn_count += 1
        logger.info(f"--- ターン {turn_count} 開始 ---")
        
        try:
            # Bedrock API呼び出し
            response = call_bedrock_api(
                bedrock_runtime, 
                messages_for_api, 
                get_system_prompt(), 
                model_id, 
                tool_config
            )
            
            # トークン使用量を更新
            result["token_usage"] = update_token_usage(response, result["token_usage"])
            
        except Exception as e:
            err_msg = str(e)
            logger.error(f"Bedrock API呼び出しエラー: {err_msg}")
            result["status"] = "error"
            result["message"] = f"Bedrock APIエラー: {err_msg}"
            break
        
        # レスポンス解析
        output = response.get("output", {})
        message = output.get("message", {})
        stop_reason = response.get("stopReason")
        
        # アシスタント応答をAPI用履歴と結果用履歴に追加
        message_content = message.get("content", [])
        messages_for_api = add_assistant_message(messages_for_api, message_content)
        result["messages"] = add_assistant_message(result["messages"], message_content)
        
        # ツール呼び出しの抽出と実行
        tool_calls = extract_tool_calls(message_content)
        
        if tool_calls:
            tool_results = []
            
            for tool_call in tool_calls:
                tool_name = tool_call.get("name")
                tool_input = tool_call.get("input", {})
                tool_use_id = tool_call.get("toolUseId")
                
                logger.info(f"ツール実行: {tool_name}")
                
                # ツール実行
                tool_result_data = dispatch_browser_tool(tool_name, tool_input)
                
                # 結果を記録
                tool_results.append({
                    "toolUseId": tool_use_id,
                    "result": tool_result_data
                })
            
            # ツール結果を含むメッセージを作成
            tool_result_message = create_tool_result_message(tool_results)
            
            # API用履歴と結果用履歴の両方に追加
            messages_for_api.append(tool_result_message)
            result["messages"].append(tool_result_message)
            
            continue # 次のループへ
        
        # 停止理由を分析
        stop_analysis = analyze_stop_reason(stop_reason)
        if not stop_analysis["should_continue"]:
            if stop_analysis["error"]:
                result["status"] = "error"
                result["message"] = stop_analysis["message"]
            break
    
    # 最大ターン数超過チェック
    if turn_count >= max_turns:
        logger.warning(f"最大ターン数 ({max_turns}) に達したため、処理を終了します。")
        if result["status"] == "success": # 他のエラーが発生していなければ
            result["status"] = "error" # 最大ターン到達もエラー扱いにする場合
            result["message"] = f"最大ターン数 ({max_turns}) に達しました。"
    
    # ブラウザを終了
    cleanup_browser()
    
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
