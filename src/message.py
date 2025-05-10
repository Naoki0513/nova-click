"""
メッセージ管理モジュール

Bedrock API に渡す会話履歴の管理と、ユーザーに表示するメッセージの整形を行います。
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def format_user_query_with_aria_snapshot(
    user_input: str, aria_snapshot: dict | None
) -> str:
    """ユーザー入力とARIA Snapshotを組み合わせたフォーマット済みテキストを返します"""
    aria_snapshot_str = "ARIA Snapshotを取得できませんでした。"
    if aria_snapshot is not None:
        try:
            aria_snapshot_json = json.dumps(aria_snapshot, ensure_ascii=False, indent=2)
            # 長さ制限を適用
            max_aria_snapshot_length = 100000
            if len(aria_snapshot_json) > max_aria_snapshot_length:
                truncated_part = "\n... (truncated)"
                aria_snapshot_json = (
                    aria_snapshot_json[:max_aria_snapshot_length] + truncated_part
                )
            aria_snapshot_str = (
                f"現在のページのARIA Snapshot:\n" f"```json\n{aria_snapshot_json}\n```"
            )
        except ValueError as e:
            aria_snapshot_str = f"ARIA Snapshotの変換エラー: {e}"

    formatted_text = f"""ユーザーからの指示: {user_input}

"
                      f"{aria_snapshot_str}

"
                      f"上記のユーザー指示と現在のページ状態（ARIA Snapshot）を基に"
                      f"応答またはツールを実行してください。"""

    return formatted_text


def create_initial_messages(
    user_input: str, aria_snapshot: dict | None
) -> list[dict[str, Any]]:
    """初回のメッセージリストを作成します

    Args:
        user_input: ユーザーの入力テキスト
        aria_snapshot: 現在のARIA Snapshot

    Returns:
        Bedrock API用のメッセージリスト
    """
    # ユーザー入力とARIA Snapshotを組み合わせたテキストを作成
    formatted_user_input = format_user_query_with_aria_snapshot(
        user_input, aria_snapshot
    )

    # 初回のユーザーメッセージを作成
    initial_user_message = {"role": "user", "content": [{"text": formatted_user_input}]}

    return [initial_user_message]


def create_user_facing_messages(user_input: str) -> list[dict[str, Any]]:
    """ユーザーに表示するためのメッセージリストを作成します

    Args:
        user_input: ユーザーの入力テキスト

    Returns:
        ユーザーに表示するためのメッセージリスト
    """
    # ユーザーには元の質問のみを表示する形式でメッセージを作成
    user_facing_message = {"role": "user", "content": [{"text": user_input}]}

    return [user_facing_message]


def add_assistant_message(
    messages: list[dict[str, Any]], assistant_content: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """アシスタントのメッセージをリストに追加します

    Args:
        messages: 既存のメッセージリスト
        assistant_content: アシスタントの応答コンテンツ

    Returns:
        更新されたメッセージリスト
    """
    assistant_message = {"role": "assistant", "content": assistant_content}
    messages.append(assistant_message)
    return messages


def create_tool_result_message(tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    """ツール実行結果のユーザーメッセージを作成します

    Args:
        tool_results: ツール実行結果のリスト

    Returns:
        ツール結果を含むユーザーメッセージ
    """
    merged_content = []

    for result in tool_results:
        tool_use_id = result.get("toolUseId")
        tool_result_data = result.get("result", {})
        tool_status = (
            "success" if tool_result_data.get("status") == "success" else "error"
        )

        # ツール結果JSONにはツール実行結果とARIA Snapshot情報を含める
        tool_result_json = {
            "operation_status": tool_result_data.get("status"),
            "message": tool_result_data.get("message", ""),
        }

        # ツール実行後に取得したARIA Snapshotがあれば含める
        if "aria_snapshot" in tool_result_data:
            tool_result_json["aria_snapshot"] = tool_result_data.get("aria_snapshot")
            if "aria_snapshot_message" in tool_result_data:
                tool_result_json["aria_snapshot_message"] = tool_result_data.get(
                    "aria_snapshot_message"
                )

        # toolResultブロックを作成
        tool_result_block = {
            "toolResult": {
                "toolUseId": tool_use_id,
                "content": [{"json": tool_result_json}],
                "status": tool_status,
            }
        }

        merged_content.append(tool_result_block)

    # マージした内容でuserメッセージを作成
    user_message = {"role": "user", "content": merged_content}
    return user_message


# ---------------------------------------------------------------------------
# 会話ループ処理（main.py から移設）
# ---------------------------------------------------------------------------

import main as constants  # エントリポイントの定数を参照
from src.bedrock import (
    analyze_stop_reason,
    call_bedrock_api,
    create_bedrock_client,
    extract_tool_calls,
    update_token_usage,
    BedrockAPIError,
)
from src.browser import cleanup_browser, get_aria_snapshot, initialize_browser
from src.prompts import get_system_prompt
from src.tools import dispatch_browser_tool, get_browser_tools_config
from src.utils import load_credentials, setup_logging


def run_cli_mode() -> int:  # noqa: D401
    """ブラウザ操作エージェントを実行します。メインロジック。"""

    # 実行パラメータを設定
    query = constants.DEFAULT_QUERY
    model_id = constants.DEFAULT_MODEL_ID
    credentials_path = constants.DEFAULT_CREDENTIALS_PATH
    max_turns = constants.DEFAULT_MAX_TURNS

    setup_logging()
    logger.info("実行します - モデル: %s", model_id)

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
        "messages": [],  # ユーザーに見せるためのメッセージ履歴
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

    # 初回リクエスト時に現在のARIA Snapshotを取得
    aria_snapshot_result = get_aria_snapshot()
    current_aria_snapshot: list[dict[str, Any]] | None = (
        aria_snapshot_result.get("aria_snapshot")
        if aria_snapshot_result.get("status") == "success"
        else None
    )
    if not current_aria_snapshot:
        logger.error(
            "ARIA Snapshot取得に失敗しました: %s",
            aria_snapshot_result.get("message", "不明なエラー"),
        )

    # Bedrock APIに渡すためのメッセージ履歴（内部管理用）
    messages_for_api = create_initial_messages(query, current_aria_snapshot)

    # ユーザーに表示するためのメッセージ履歴
    result["messages"] = create_user_facing_messages(query)

    # 対話ループ開始
    turn_count = 0

    while turn_count < max_turns:
        turn_count += 1
        logger.info("--- ターン %s 開始 ---", turn_count)

        try:
            # Bedrock API 呼び出し
            response = call_bedrock_api(
                bedrock_runtime,
                messages_for_api,
                get_system_prompt(),
                model_id,
                tool_config,
            )

            # トークン使用量更新
            result["token_usage"] = update_token_usage(response, result["token_usage"])

        except BedrockAPIError as e:  # pylint: disable=broad-exception-caught
            err_msg = str(e)
            logger.error("Bedrock API呼び出しエラー: %s", err_msg)
            result["status"] = "error"
            result["message"] = f"Bedrock APIエラー: {err_msg}"
            break

        # レスポンス解析
        output = response.get("output", {})
        message = output.get("message", {})
        stop_reason = response.get("stopReason")

        # アシスタント応答を履歴に追加
        message_content = message.get("content", [])
        messages_for_api = add_assistant_message(messages_for_api, message_content)
        result["messages"] = add_assistant_message(result["messages"], message_content)

        # アシスタントのテキストメッセージをリアルタイムで表示
        for content in message_content:
            if "text" in content:
                print(f"\n{content['text']}\n")

        # ツール呼び出しの抽出
        tool_calls = extract_tool_calls(message_content)

        if tool_calls:
            tool_results: list[dict[str, Any]] = []
            for tool_call in tool_calls:
                tool_name = tool_call.get("name")
                tool_input = tool_call.get("input", {})
                tool_use_id = tool_call.get("toolUseId")

                logger.info("ツール実行: %s", tool_name)

                # ツール実行
                tool_result_data = dispatch_browser_tool(tool_name, tool_input)

                tool_results.append({"toolUseId": tool_use_id, "result": tool_result_data})

            # ツール結果メッセージを作成
            tool_result_message = create_tool_result_message(tool_results)

            # 履歴に追加
            messages_for_api.append(tool_result_message)
            result["messages"].append(tool_result_message)

            continue  # 次のループへ

        # 停止理由解析
        stop_analysis = analyze_stop_reason(stop_reason)
        if not stop_analysis["should_continue"]:
            if stop_analysis["error"]:
                result["status"] = "error"
                result["message"] = stop_analysis["message"]
            break

    # 最大ターン数超過チェック
    if turn_count >= max_turns:
        logger.warning("最大ターン数 (%s) に達したため、処理を終了します。", max_turns)
        if result["status"] == "success":
            result["status"] = "error"
            result["message"] = f"最大ターン数 ({max_turns}) に達しました。"

    # ブラウザ終了
    cleanup_browser()

    # 結果表示（削除）
    logger.info("処理が完了しました")

    # トークン使用量を表示
    token_usage = result.get("token_usage", {})
    logger.info(
        "トークン使用量: 入力=%s 出力=%s 合計=%s",
        f"{token_usage.get('inputTokens', 0):,}",
        f"{token_usage.get('outputTokens', 0):,}",
        f"{token_usage.get('totalTokens', 0):,}",
    )

    return 0
