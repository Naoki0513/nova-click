"""
main.py のE2Eテストスクリプト

main.pyの処理をエンドツーエンドでテストし、エラーが発生しても会話APIが正常に終了し、
stopReasonが「endTurn」で終わることを検証します。

環境変数:
    HEADLESS - 'true'の場合、ブラウザをヘッドレスモードで実行します
    CI - 'true'の場合、CI環境向けのログ設定を使用します
"""

import argparse
# import json # 未使用のためコメントアウト
import logging
import os
import sys
import time
import traceback
from typing import Any
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.bedrock import (  # pylint: disable=wrong-import-position,import-error
    analyze_stop_reason, call_bedrock_api)
from src.browser import (  # pylint: disable=wrong-import-position,import-error
    cleanup_browser, get_aria_snapshot, goto_url, initialize_browser)
# 以下のインポートはsys.pathを設定した後に行う必要があるため、ここに配置
from src.utils import \
    setup_logging  # pylint: disable=wrong-import-position,import-error

MOCK_BEDROCK_RESPONSE = {
    "output": {
        "message": {
            "role": "assistant",
            "content": [{"text": "テスト応答です。ブラウザ操作を完了しました。"}],
        }
    },
    "stopReason": "end_turn",
    "usage": {"inputTokens": 100, "outputTokens": 50, "totalTokens": 150},
}

MOCK_ERROR_RESPONSE = {
    "output": {
        "message": {
            "role": "assistant",
            "content": [{"text": "エラーが発生しましたが、会話は正常に終了します。"}],
        }
    },
    "stopReason": "end_turn",
    "usage": {"inputTokens": 100, "outputTokens": 50, "totalTokens": 150},
}


def mock_bedrock_client(*args, **kwargs):  # pylint: disable=unused-argument
    """モックのBedrockクライアントを作成"""
    mock_client = MagicMock()
    mock_client.converse.return_value = MOCK_BEDROCK_RESPONSE
    return mock_client


def test_normal_case():
    """正常系テスト - 通常の会話APIフロー"""
    logging.info("=== 正常系テスト開始 ===")

    # ブラウザ初期化と準備
    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error("ブラウザ初期化に失敗: %s", init_res.get("message"))
        return False

    goto_res = goto_url("https://www.google.co.jp/")
    if goto_res.get("status") != "success":
        logging.error("URL移動に失敗: %s", goto_res.get("message"))
        return False

    aria_res = get_aria_snapshot()
    if aria_res.get("status") != "success":
        logging.error("ARIA Snapshot取得に失敗: %s", aria_res.get("message"))
        return False

    # Bedrock API呼び出しテスト
    success = True
    with patch("src.bedrock.create_bedrock_client", side_effect=mock_bedrock_client):
        messages = [{"role": "user", "content": [{"text": "テストクエリ"}]}]
        system_prompt = "テスト用システムプロンプト"
        model_id = "test-model"
        tool_config = {"tools": [], "toolChoice": {"auto": {}}}

        mock_client = mock_bedrock_client()
        response = call_bedrock_api(
            mock_client, messages, system_prompt, model_id, tool_config
        )

        if response.get("stopReason") != "end_turn":
            logging.error(
                "stopReasonが 'end_turn' ではありません: %s", response.get("stopReason")
            )
            success = False
        else:
            stop_analysis = analyze_stop_reason(response.get("stopReason"))
            if stop_analysis.get("should_continue"):
                logging.error("stopReasonの分析が正しくありません")
                success = False
            elif stop_analysis.get("error"):
                logging.error("正常系なのにエラーが検出されました")
                success = False

    if success:
        logging.info("正常系テスト成功")

    return success


def test_error_case():  # pylint: disable=too-many-return-statements
    """異常系テスト - エラーが発生しても会話APIが正常に終了することを検証"""
    logging.info("=== 異常系テスト開始 ===")

    # ブラウザの初期化
    success = True
    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error("ブラウザ初期化に失敗: %s", init_res.get("message"))
        return False

    goto_res = goto_url("https://www.google.co.jp/")
    if goto_res.get("status") != "success":
        logging.error("URL移動に失敗: %s", goto_res.get("message"))
        return False

    def mock_error_client(*args, **kwargs):  # pylint: disable=unused-argument
        mock_client = MagicMock()
        mock_client.converse.side_effect = [
            Exception("テスト用のエラー"),
            MOCK_ERROR_RESPONSE,
        ]
        return mock_client

    # API呼び出しの異常系テスト
    with patch("src.bedrock.create_bedrock_client", side_effect=mock_error_client):
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": [{"text": "テストクエリ"}]}
        ]
        system_prompt = "テスト用システムプロンプト"
        model_id = "test-model"
        tool_config = {"tools": [], "toolChoice": {"auto": {}}}

        mock_client = mock_error_client()

        # 最初のAPI呼び出しでエラーが発生することを確認
        try:
            call_bedrock_api(
                mock_client, messages, system_prompt, model_id, tool_config
            )
            logging.error("エラーが発生しませんでした")
            success = False
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.info("想定通りエラーが発生しました: %s", e)

            # 2回目のAPI呼び出しで正常に終了することを確認
            try:
                response = call_bedrock_api(
                    mock_client, messages, system_prompt, model_id, tool_config
                )

                # レスポンスの検証
                if response.get("stopReason") != "end_turn":
                    logging.error(
                        "stopReasonが 'end_turn' ではありません: %s",
                        response.get("stopReason"),
                    )
                    success = False
                else:
                    stop_analysis = analyze_stop_reason(response.get("stopReason"))
                    if stop_analysis.get("should_continue"):
                        logging.error("stopReasonの分析が正しくありません")
                        success = False
                    else:
                        logging.info("エラー後のリカバリーが成功しました")
            except Exception as e2:  # pylint: disable=broad-exception-caught
                logging.error("エラー後のリカバリーに失敗しました: %s", e2)
                success = False

    if success:
        logging.info("異常系テスト成功")

    return success


# pylint: disable=too-many-locals,too-many-statements
def test_main_e2e():
    """main.pyのE2Eテスト - 実際のmain.pyの処理を模倣してテスト"""
    logging.info("=== main.py E2Eテスト開始 ===")

    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error("ブラウザ初期化に失敗: %s", init_res.get("message"))
        return False

    goto_res = goto_url("https://www.google.co.jp/")
    if goto_res.get("status") != "success":
        logging.error("URL移動に失敗: %s", goto_res.get("message"))
        return False

    aria_res = get_aria_snapshot()
    if aria_res.get("status") != "success":
        logging.error("ARIA Snapshot取得に失敗: %s", aria_res.get("message"))
        return False

    with patch("src.bedrock.create_bedrock_client", side_effect=mock_bedrock_client):
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": [{"text": "テストクエリ"}]}
        ]
        system_prompt = "テスト用システムプロンプト"
        model_id = "test-model"
        tool_config = {"tools": [], "toolChoice": {"auto": {}}}

        result = {
            "status": "success",
            "messages": messages.copy(),
            "token_usage": {
                "inputTokens": 0,
                "outputTokens": 0,
                "totalTokens": 0,
            },
        }

        max_turns = 3
        turn_count = 0

        while turn_count < max_turns:
            turn_count += 1
            logging.info("--- ターン %d 開始 ---", turn_count)

            try:
                mock_client = mock_bedrock_client()
                response = call_bedrock_api(
                    mock_client, messages, system_prompt, model_id, tool_config
                )

                usage = response.get("usage", {})
                result["token_usage"]["inputTokens"] += usage.get("inputTokens", 0)
                result["token_usage"]["outputTokens"] += usage.get("outputTokens", 0)
                result["token_usage"]["totalTokens"] += usage.get(
                    "inputTokens", 0
                ) + usage.get("outputTokens", 0)

            except Exception as e:  # pylint: disable=broad-exception-caught
                err_msg = str(e)
                logging.error("Bedrock API呼び出しエラー: %s", err_msg)
                result["status"] = "error"
                result["message"] = f"Bedrock APIエラー: {err_msg}"
                break

            output = response.get("output", {})
            message = output.get("message", {})
            stop_reason = response.get("stopReason")

            message_content = message.get("content", [])
            messages.append({"role": "assistant", "content": message_content})
            result["messages"].append({"role": "assistant", "content": message_content})

            stop_analysis = analyze_stop_reason(stop_reason)
            if not stop_analysis["should_continue"]:
                if stop_analysis["error"]:
                    result["status"] = "error"
                    result["message"] = stop_analysis["message"]
                break

        if result["status"] != "success":
            logging.error(
                "E2Eテストが失敗しました: %s", result.get("message", "不明なエラー")
            )
            return False

        if turn_count >= max_turns:
            logging.error("最大ターン数 (%d) に達しました", max_turns)
            return False

        logging.info("E2Eテスト成功: %dターンで正常に終了", turn_count)

    cleanup_browser()

    return True


def main():
    """メイン関数 - テストの実行を制御"""
    parser = argparse.ArgumentParser(description="main.pyのE2Eテスト")
    parser.add_argument(
        "--debug", action="store_true", help="デバッグモードを有効にする"
    )
    parser.add_argument(
        "--timeout", type=int, default=60, help="テスト全体のタイムアウト（秒）"
    )
    args = parser.parse_args()

    setup_logging(debug=args.debug or True)

    logging.info(
        "main.py E2Eテスト開始: headless=%s, CI=%s",
        os.environ.get("HEADLESS", "false"),
        os.environ.get("CI", "false"),
    )

    start_time = time.time()

    try:
        normal_success = test_normal_case()
        error_success = test_error_case()
        e2e_success = test_main_e2e()

        elapsed_time = time.time() - start_time
        logging.info("テスト実行時間: %.2f秒", elapsed_time)

        if normal_success and error_success and e2e_success:
            logging.info("すべてのテストが成功しました")
            return 0

        logging.error("一部のテストが失敗しました")
        return 1
    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.error("テスト実行中にエラーが発生しました: %s", e)
        traceback.print_exc()
        return 1
    finally:
        try:
            cleanup_browser()
            logging.info("ブラウザのクリーンアップが完了しました")
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.error("ブラウザのクリーンアップ中にエラーが発生しました: %s", e)
            traceback.print_exc()


if __name__ == "__main__":
    EXIT_CODE = main()
    logging.info("テストプロセスを終了します: exit_code=%s", EXIT_CODE)
    sys.exit(EXIT_CODE)
