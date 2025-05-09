"""
ブラウザ操作エージェントのメインエントリーポイント
"""

import logging
import sys
from typing import Any

from src import constants  # constants をインポート
from src.bedrock import (analyze_stop_reason, call_bedrock_api,
                         create_bedrock_client, extract_tool_calls,
                         update_token_usage)
from src.browser import cleanup_browser, get_aria_snapshot, initialize_browser
from src.message import (add_assistant_message, create_initial_messages,
                         create_tool_result_message,
                         create_user_facing_messages)
from src.prompts import get_system_prompt
from src.tools import dispatch_browser_tool, get_browser_tools_config
from src.utils import load_credentials, setup_logging

# ロガーの設定
logger = logging.getLogger(__name__)


# CLIモードの実行関数 (引数なし)
def run_cli_mode() -> int:
    """CLIモードでブラウザ操作エージェントを実行します。"""
    # --- ここで実行パラメータを設定 --- +
    query = constants.DEFAULT_QUERY  # 固定のクエリ
    model_id = constants.DEFAULT_MODEL_ID
    credentials_path = constants.DEFAULT_CREDENTIALS_PATH
    max_turns = constants.DEFAULT_MAX_TURNS  # 最大対話ターン数
    # ------------------------------------ +

    setup_logging()  # ログを設定 (常にINFO）
    logger.info("CLIモードで実行します - モデル: %s", model_id)  # 実行情報ログ

    # ブラウザを初期化
    init_result = initialize_browser()
    if init_result.get("status") != "success":
        logger.error("ブラウザ初期化に失敗しました: %s", init_result.get("message"))
        return 1

    # AWS認証情報を読み込み
    credentials = load_credentials(credentials_path)
    if not credentials:
        logger.error("認証情報の読み込みに失敗しました: %s", credentials_path)
        return 1

    # Bedrock クライアントを作成
    bedrock_runtime = create_bedrock_client(credentials)

    # 結果用データ構造を初期化
    result = {
        "status": "success",
        "messages": [],  # 最終的にユーザーに見せるためのメッセージ履歴
        "token_usage": {
            "inputTokens": 0,
            "outputTokens": 0,
            "totalTokens": 0,
        },
    }

    # ユーザークエリを処理
    logger.info("クエリを処理します: %s", query)

    # ツール設定を取得
    tool_config = {"tools": get_browser_tools_config(), "toolChoice": {"auto": {}}}

    # 初回リクエスト時、現在のARIA Snapshotを取得
    aria_snapshot_result = get_aria_snapshot()
    current_aria_snapshot: list[dict[str, Any]] | None = (
        aria_snapshot_result.get("aria_snapshot")
        if aria_snapshot_result.get("status") == "success"
        else None
    )
    if not current_aria_snapshot:
        logger.error(
            "ARIA Snapshotの取得に失敗しました: %s",
            aria_snapshot_result.get("message", "不明なエラー"),
        )

    # Bedrock APIに渡すためのメッセージ履歴（内部管理用）
    messages_for_api = create_initial_messages(query, current_aria_snapshot)

    # ユーザーに表示するためのメッセージ履歴
    result["messages"] = create_user_facing_messages(query)

    # 対話ループを開始
    turn_count = 0

    while turn_count < max_turns:
        turn_count += 1
        logger.info("--- ターン %s 開始 ---", turn_count)

        try:
            # Bedrock API呼び出し
            response = call_bedrock_api(
                bedrock_runtime,
                messages_for_api,
                get_system_prompt(),
                model_id,
                tool_config,
            )

            # トークン使用量を更新
            result["token_usage"] = update_token_usage(response, result["token_usage"])

        except RuntimeError as e:
            err_msg = str(e)
            logger.error("Bedrock API呼び出しエラー: %s", err_msg)
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

                logger.info("ツール実行: %s", tool_name)

                # ツール実行
                tool_result_data = dispatch_browser_tool(tool_name, tool_input)

                # 結果を記録
                tool_results.append(
                    {"toolUseId": tool_use_id, "result": tool_result_data}
                )

            # ツール結果を含むメッセージを作成
            tool_result_message = create_tool_result_message(tool_results)

            # API用履歴と結果用履歴の両方に追加
            messages_for_api.append(tool_result_message)
            result["messages"].append(tool_result_message)

            continue  # 次のループへ

        # 停止理由を分析
        stop_analysis = analyze_stop_reason(stop_reason)
        if not stop_analysis["should_continue"]:
            if stop_analysis["error"]:
                result["status"] = "error"
                result["message"] = stop_analysis["message"]
            break

    # 最大ターン数超過チェック
    if turn_count >= max_turns:
        logger.warning("最大ターン数 (%s) に達したため、処理を終了します。", max_turns)
        if result["status"] == "success":  # 他のエラーが発生していなければ
            result["status"] = "error"  # 最大ターン到達もエラー扱いにする場合
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
    logger.info(
        "トークン使用量: 入力=%s 出力=%s 合計=%s",
        f"{token_usage.get('inputTokens', 0):,}",
        f"{token_usage.get('outputTokens', 0):,}",
        f"{token_usage.get('totalTokens', 0):,}",
    )

    return 0


def main() -> int:
    """メインエントリーポイント"""

    # 引数なしでCLIモードを実行
    return run_cli_mode()


if __name__ == "__main__":
    sys.exit(main())
