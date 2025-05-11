"""
main.py のE2Eテストスクリプト

main.pyの処理をエンドツーエンドでテストし、エラーが発生しても会話APIが正常に終了し、
stopReasonが「endTurn」で終わることを検証します。

環境変数:
    HEADLESS - 'true'の場合、ブラウザをヘッドレスモードで実行します
    CI - 'true'の場合、CI環境向けのログ設定を使用します
"""

import argparse
import logging
import os
import sys
import time
import traceback
from typing import Any, Dict
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.bedrock import (  # pylint: disable=wrong-import-position,import-error
    analyze_stop_reason, call_bedrock_api)
from src.browser import (  # pylint: disable=wrong-import-position,import-error
    cleanup_browser, get_aria_snapshot, goto_url, initialize_browser)
from src.utils import \
    setup_logging  # pylint: disable=wrong-import-position,import-error

# テスト用パラメータ（自由に変更可能）
TEST_URL = "https://www.google.co.jp/"
TEST_MODEL_ID = "test-model"
TEST_SYSTEM_PROMPT = "テスト用システムプロンプト"
TEST_USER_QUERY = "テストクエリ"
TEST_MAX_TURNS = 3

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


def verify_api_response(response: Dict[str, Any]) -> bool:
    """API応答の検証を行う汎用関数

    Args:
        response: Bedrock APIからのレスポンス

    Returns:
        bool: 検証が成功したかどうか
    """
    success = True
    
    # 1. 基本的な構造チェック
    if not isinstance(response, dict):
        logging.error("APIレスポンスはdict型である必要があります")
        return False
    
    # 2. 必須フィールドの存在チェック
    required_fields = ["output", "stopReason", "usage"]
    for field in required_fields:
        if field not in response:
            logging.error("必須フィールド '%s' がレスポンスにありません", field)
            success = False
    
    if not success:
        return False
    
    # 3. 出力メッセージの構造チェック
    output = response.get("output", {})
    message = output.get("message", {})
    
    if not message.get("role"):
        logging.error("メッセージにroleフィールドがありません")
        success = False
    
    content = message.get("content", [])
    if not content or not isinstance(content, list):
        logging.error("メッセージのcontentフィールドが不正です")
        success = False
    
    # 4. 使用量情報のチェック
    usage = response.get("usage", {})
    usage_fields = ["inputTokens", "outputTokens", "totalTokens"]
    for field in usage_fields:
        if field not in usage:
            logging.warning("使用量情報に '%s' フィールドがありません", field)
    
    # 5. stopReasonの解析
    stop_reason = response.get("stopReason")
    if stop_reason != "end_turn":
        logging.error("stopReasonが期待値 'end_turn' ではなく '%s' です", stop_reason)
        success = False
    
    return success


def test_normal_case(url=TEST_URL):
    """正常系テスト - 通常の会話APIフロー"""
    logging.info("=== 正常系テスト開始 ===")

    # ブラウザ初期化と準備
    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error("ブラウザ初期化に失敗: %s", init_res.get("message"))
        assert False, "ブラウザ初期化に失敗"

    goto_res = goto_url(url)
    if goto_res.get("status") != "success":
        logging.error("URL移動に失敗: %s", goto_res.get("message"))
        assert False, "URL移動に失敗"

    # 初期ARIAスナップショット取得
    aria_res = get_aria_snapshot()
    if aria_res.get("status") != "success":
        logging.error("ARIA Snapshot取得に失敗: %s", aria_res.get("message"))
        assert False, "ARIA Snapshot取得に失敗"
    
    initial_elements = aria_res.get("aria_snapshot", [])
    logging.info("初期要素数: %d", len(initial_elements))

    # Bedrock API呼び出しテスト
    success = True
    with patch("src.bedrock.create_bedrock_client", side_effect=mock_bedrock_client):
        messages = [{"role": "user", "content": [{"text": TEST_USER_QUERY}]}]
        system_prompt = TEST_SYSTEM_PROMPT
        model_id = TEST_MODEL_ID
        tool_config = {"tools": [], "toolChoice": {"auto": {}}}

        mock_client = mock_bedrock_client()
        
        # API呼び出し前の状態を記録
        pre_call_time = time.time()
        
        response = call_bedrock_api(
            mock_client, messages, system_prompt, model_id, tool_config
        )
        
        # API呼び出し後の経過時間を記録
        call_duration = time.time() - pre_call_time
        logging.info("API呼び出し所要時間: %.2f秒", call_duration)
        
        # API呼び出し後の状態を検証
        post_api_aria_res = get_aria_snapshot()
        if post_api_aria_res.get("status") == "success":
            post_elements = post_api_aria_res.get("aria_snapshot", [])
            logging.info("API呼び出し後の要素数: %d", len(post_elements))
            
            # DOM状態が変わっていないことを確認（API呼び出しはDOM操作を行わない）
            if len(initial_elements) != len(post_elements):
                logging.warning("API呼び出し前後でDOM要素数が変化しています: %d → %d", 
                             len(initial_elements), len(post_elements))
        
        # レスポンスの詳細検証
        if not verify_api_response(response):
            logging.error("APIレスポンス検証に失敗しました")
            success = False
            
        # stopReasonの検証（基本チェック）
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

    # ログに応答内容の詳細を出力
    if 'response' in locals():
        try:
            output = response.get("output", {})
            message = output.get("message", {})
            content = message.get("content", [])
            response_text = content[0].get("text") if content else "(テキストなし)"
            logging.info("APIレスポンステキスト: %s", response_text[:100] + '...' if len(response_text) > 100 else response_text)
        except (KeyError, IndexError) as e:
            logging.warning("レスポンステキスト抽出中にエラー: %s", e)

    if success:
        logging.info("正常系テスト成功")

    assert success, "正常系テストが失敗しました"


def test_error_case(url=TEST_URL):  # pylint: disable=too-many-return-statements
    """異常系テスト - エラーが発生しても会話APIが正常に終了することを検証"""
    logging.info("=== 異常系テスト開始 ===")

    # ブラウザの初期化
    success = True
    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error("ブラウザ初期化に失敗: %s", init_res.get("message"))
        assert False, "ブラウザ初期化に失敗"

    goto_res = goto_url(url)
    if goto_res.get("status") != "success":
        logging.error("URL移動に失敗: %s", goto_res.get("message"))
        assert False, "URL移動に失敗"

    # 初期状態のARIAスナップショット取得
    initial_aria_res = get_aria_snapshot()
    if initial_aria_res.get("status") != "success":
        logging.error("初期ARIA Snapshot取得に失敗: %s", initial_aria_res.get("message"))
        assert False, "初期ARIA Snapshot取得に失敗"
    
    initial_elements = initial_aria_res.get("aria_snapshot", [])
    logging.info("初期要素数: %d", len(initial_elements))

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
            {"role": "user", "content": [{"text": TEST_USER_QUERY}]}
        ]
        system_prompt = TEST_SYSTEM_PROMPT
        model_id = TEST_MODEL_ID
        tool_config = {"tools": [], "toolChoice": {"auto": {}}}

        mock_client = mock_error_client()

        # 最初のAPI呼び出しでエラーが発生することを確認
        first_error_occurred = False
        try:
            call_bedrock_api(
                mock_client, messages, system_prompt, model_id, tool_config
            )
            logging.error("エラーが発生しませんでした")
            success = False
        except Exception as e:  # pylint: disable=broad-exception-caught
            first_error_occurred = True
            logging.info("想定通りエラーが発生しました: %s", e)
            
            # エラー発生後のDOM状態を検証
            error_aria_res = get_aria_snapshot()
            if error_aria_res.get("status") == "success":
                error_elements = error_aria_res.get("aria_snapshot", [])
                logging.info("エラー発生後の要素数: %d", len(error_elements))
                
                # エラーによってDOM状態が変わっていないことを確認
                if len(initial_elements) != len(error_elements):
                    logging.warning("エラー発生前後でDOM要素数が変化しています: %d → %d", 
                                 len(initial_elements), len(error_elements))

            # 2回目のAPI呼び出しで正常に終了することを確認
            try:
                response = call_bedrock_api(
                    mock_client, messages, system_prompt, model_id, tool_config
                )

                # 詳細な応答検証
                if not verify_api_response(response):
                    logging.error("2回目のAPIレスポンス検証に失敗しました")
                    success = False
                
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
                        # エラー後の回復であることを確認
                        if 'response' in locals():
                            try:
                                output = response.get("output", {})
                                message = output.get("message", {})
                                content = message.get("content", [])
                                response_text = content[0].get("text") if content else "(テキストなし)"
                                logging.info("回復後のAPIレスポンステキスト: %s", 
                                           response_text[:100] + '...' if len(response_text) > 100 else response_text)
                                
                                # 回復したレスポンスが期待するものか検証
                                if "エラー" in response_text:
                                    logging.info("回復レスポンスにエラーへの言及があります")
                            except (KeyError, IndexError) as e:
                                logging.warning("回復レスポンステキスト抽出中にエラー: %s", e)
                        
                        logging.info("エラー後のリカバリーが成功しました")
            except Exception as e2:  # pylint: disable=broad-exception-caught
                logging.error("エラー後のリカバリーに失敗しました: %s", e2)
                success = False

    # エラーが実際に発生したことを確認
    if not first_error_occurred:
        logging.error("最初のAPI呼び出しでエラーが発生しませんでした")
        success = False

    if success:
        logging.info("異常系テスト成功")

    assert success, "異常系テストが失敗しました"


# pylint: disable=too-many-locals,too-many-statements
def test_main_e2e(url=TEST_URL, max_turns=TEST_MAX_TURNS):
    """main.pyのE2Eテスト - 実際のmain.pyの処理を模倣してテスト"""
    logging.info("=== main.py E2Eテスト開始 ===")

    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error("ブラウザ初期化に失敗: %s", init_res.get("message"))
        assert False, "ブラウザ初期化に失敗"

    goto_res = goto_url(url)
    if goto_res.get("status") != "success":
        logging.error("URL移動に失敗: %s", goto_res.get("message"))
        assert False, "URL移動に失敗"

    # 初期のARIAスナップショット取得
    aria_res = get_aria_snapshot()
    if aria_res.get("status") != "success":
        logging.error("ARIA Snapshot取得に失敗: %s", aria_res.get("message"))
        assert False, "ARIA Snapshot取得に失敗"
    
    initial_elements = aria_res.get("aria_snapshot", [])
    logging.info("初期要素数: %d", len(initial_elements))

    success = True
    with patch("src.bedrock.create_bedrock_client", side_effect=mock_bedrock_client):
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": [{"text": TEST_USER_QUERY}]}
        ]
        system_prompt = TEST_SYSTEM_PROMPT
        model_id = TEST_MODEL_ID
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

        turn_count = 0

        while turn_count < max_turns:
            turn_count += 1
            logging.info("--- ターン %d 開始 ---", turn_count)

            # ターン開始時のDOM状態を記録
            turn_start_aria_res = get_aria_snapshot()
            if turn_start_aria_res.get("status") == "success":
                turn_start_elements = turn_start_aria_res.get("aria_snapshot", [])
                logging.info("ターン %d 開始時の要素数: %d", turn_count, len(turn_start_elements))

            try:
                mock_client = mock_bedrock_client()
                
                # API呼び出し前の時刻を記録
                api_start_time = time.time()
                
                response = call_bedrock_api(
                    mock_client, messages, system_prompt, model_id, tool_config
                )
                
                # API呼び出し所要時間を記録
                api_duration = time.time() - api_start_time
                logging.info("ターン %d のAPI呼び出し所要時間: %.2f秒", turn_count, api_duration)

                usage = response.get("usage", {})
                result["token_usage"]["inputTokens"] += usage.get("inputTokens", 0)
                result["token_usage"]["outputTokens"] += usage.get("outputTokens", 0)
                result["token_usage"]["totalTokens"] += usage.get(
                    "inputTokens", 0
                ) + usage.get("outputTokens", 0)
                
                # レスポンスの詳細検証
                if not verify_api_response(response):
                    logging.error("ターン %d のAPIレスポンス検証に失敗しました", turn_count)
                    success = False

            except Exception as e:  # pylint: disable=broad-exception-caught
                err_msg = str(e)
                logging.error("Bedrock API呼び出しエラー: %s", err_msg)
                result["status"] = "error"
                result["message"] = f"Bedrock APIエラー: {err_msg}"
                success = False
                break

            output = response.get("output", {})
            message = output.get("message", {})
            stop_reason = response.get("stopReason")

            message_content = message.get("content", [])
            messages.append({"role": "assistant", "content": message_content})
            result["messages"].append({"role": "assistant", "content": message_content})
            
            # レスポンスメッセージの内容を検証
            response_text = message_content[0].get("text") if message_content else ""
            logging.info("ターン %d のレスポンステキスト: %s", 
                       turn_count, response_text[:100] + '...' if len(response_text) > 100 else response_text)

            stop_analysis = analyze_stop_reason(stop_reason)
            
            # ターン終了時のDOM状態を記録して変化を検証
            turn_end_aria_res = get_aria_snapshot()
            if turn_end_aria_res.get("status") == "success":
                turn_end_elements = turn_end_aria_res.get("aria_snapshot", [])
                logging.info("ターン %d 終了時の要素数: %d", turn_count, len(turn_end_elements))
                
                if len(turn_start_elements) != len(turn_end_elements):
                    logging.info("ターン %d 内でDOM要素数が変化しました: %d → %d", 
                              turn_count, len(turn_start_elements), len(turn_end_elements))
            
            if not stop_analysis["should_continue"]:
                if stop_analysis["error"]:
                    result["status"] = "error"
                    result["message"] = stop_analysis["message"]
                    success = False
                break

        if result["status"] != "success":
            logging.error(
                "E2Eテストが失敗しました: %s", result.get("message", "不明なエラー")
            )
            success = False

        if turn_count >= max_turns:
            logging.error("最大ターン数 (%d) に達しました", max_turns)
            success = False

        # 最終的な状態を検証
        final_aria_res = get_aria_snapshot()
        if final_aria_res.get("status") == "success":
            final_elements = final_aria_res.get("aria_snapshot", [])
            logging.info("最終的な要素数: %d", len(final_elements))
            
            if len(initial_elements) != len(final_elements):
                logging.info("テスト全体でDOM要素数が変化しました: %d → %d", 
                          len(initial_elements), len(final_elements))
        
        # トークン使用量を確認
        logging.info("トークン使用量: 入力=%d, 出力=%d, 合計=%d",
                   result["token_usage"]["inputTokens"],
                   result["token_usage"]["outputTokens"],
                   result["token_usage"]["totalTokens"])

        if success:
            logging.info("E2Eテスト成功: %dターンで正常に終了", turn_count)

    cleanup_browser()

    assert success, "E2Eテストが失敗しました"


def main():
    """メイン関数 - テストの実行を制御"""
    # pytestから実行される場合は、sys.argvを変更して余計な引数を削除
    if len(sys.argv) > 1 and sys.argv[0].endswith('__main__.py'):
        # pytestから実行される場合、余計な引数をフィルタリング
        filtered_args = [sys.argv[0]]
        for arg in sys.argv[1:]:
            if arg in ['--debug', '--timeout'] or not arg.startswith('-'):
                filtered_args.append(arg)
        sys.argv = filtered_args

    parser = argparse.ArgumentParser(description="main.pyのE2Eテスト")
    parser.add_argument(
        "--debug", action="store_true", help="デバッグモードを有効にする"
    )
    parser.add_argument(
        "--timeout", type=int, default=60, help="テスト全体のタイムアウト（秒）"
    )
    args = parser.parse_args()

    # setup_loggingの呼び出しを修正
    setup_logging()
    if args.debug or True:
        logging.getLogger().setLevel(logging.DEBUG)

    logging.info(
        "main.py E2Eテスト開始: headless=%s, CI=%s",
        os.environ.get("HEADLESS", "false"),
        os.environ.get("CI", "false"),
    )

    start_time = time.time()

    try:
        # テスト関数を実行し、必要に応じてassert文を評価
        success = True
        
        try:
            test_normal_case()  # 戻り値を使用しない
            normal_success = True
        except AssertionError:
            normal_success = False
            success = False
            
        try:
            test_error_case()  # 戻り値を使用しない
            error_success = True
        except AssertionError:
            error_success = False
            success = False
            
        try:
            test_main_e2e()  # 戻り値を使用しない
            e2e_success = True
        except AssertionError:
            e2e_success = False
            success = False

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
