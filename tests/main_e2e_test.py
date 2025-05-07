"""
main.py のE2Eテストスクリプト

main.pyの処理をエンドツーエンドでテストし、エラーが発生しても会話APIが正常に終了し、
stopReasonが「endTurn」で終わることを検証します。

環境変数:
    HEADLESS - 'true'の場合、ブラウザをヘッドレスモードで実行します
    CI - 'true'の場合、CI環境向けのログ設定を使用します
"""
import sys
import os
import json
import logging
import argparse
import traceback
from unittest.mock import patch, MagicMock
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import setup_logging
from src.browser import initialize_browser, get_aria_snapshot, goto_url, cleanup_browser
from src.bedrock import call_bedrock_api, analyze_stop_reason

MOCK_BEDROCK_RESPONSE = {
    "output": {
        "message": {
            "role": "assistant",
            "content": [
                {
                    "text": "テスト応答です。ブラウザ操作を完了しました。"
                }
            ]
        }
    },
    "stopReason": "end_turn",
    "usage": {
        "inputTokens": 100,
        "outputTokens": 50,
        "totalTokens": 150
    }
}

MOCK_ERROR_RESPONSE = {
    "output": {
        "message": {
            "role": "assistant",
            "content": [
                {
                    "text": "エラーが発生しましたが、会話は正常に終了します。"
                }
            ]
        }
    },
    "stopReason": "end_turn",
    "usage": {
        "inputTokens": 100,
        "outputTokens": 50,
        "totalTokens": 150
    }
}

def mock_bedrock_client(*args, **kwargs):
    """モックのBedrockクライアントを作成"""
    mock_client = MagicMock()
    mock_client.converse.return_value = MOCK_BEDROCK_RESPONSE
    return mock_client

def test_normal_case():
    """正常系テスト - 通常の会話APIフロー"""
    logging.info("=== 正常系テスト開始 ===")
    
    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error(f"ブラウザ初期化に失敗: {init_res.get('message')}")
        return False
    
    goto_res = goto_url("https://www.google.co.jp/")
    if goto_res.get("status") != "success":
        logging.error(f"URL移動に失敗: {goto_res.get('message')}")
        return False
    
    aria_res = get_aria_snapshot()
    if aria_res.get("status") != "success":
        logging.error(f"ARIA Snapshot取得に失敗: {aria_res.get('message')}")
        return False
    
    with patch('src.bedrock.create_bedrock_client', side_effect=mock_bedrock_client):
        messages = [{"role": "user", "content": [{"text": "テストクエリ"}]}]
        system_prompt = "テスト用システムプロンプト"
        model_id = "test-model"
        tool_config = {"tools": [], "toolChoice": {"auto": {}}}
        
        mock_client = mock_bedrock_client()
        response = call_bedrock_api(mock_client, messages, system_prompt, model_id, tool_config)
        
        if response.get("stopReason") != "end_turn":
            logging.error(f"stopReasonが 'end_turn' ではありません: {response.get('stopReason')}")
            return False
        
        stop_analysis = analyze_stop_reason(response.get("stopReason"))
        if stop_analysis.get("should_continue"):
            logging.error("stopReasonの分析が正しくありません")
            return False
        
        if stop_analysis.get("error"):
            logging.error("正常系なのにエラーが検出されました")
            return False
    
    logging.info("正常系テスト成功")
    return True

def test_error_case():
    """異常系テスト - エラーが発生しても会話APIが正常に終了することを検証"""
    logging.info("=== 異常系テスト開始 ===")
    
    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error(f"ブラウザ初期化に失敗: {init_res.get('message')}")
        return False
    
    goto_res = goto_url("https://www.google.co.jp/")
    if goto_res.get("status") != "success":
        logging.error(f"URL移動に失敗: {goto_res.get('message')}")
        return False
    
    def mock_error_client(*args, **kwargs):
        mock_client = MagicMock()
        mock_client.converse.side_effect = [
            Exception("テスト用のエラー"),
            MOCK_ERROR_RESPONSE
        ]
        return mock_client
    
    with patch('src.bedrock.create_bedrock_client', side_effect=mock_error_client):
        messages = [{"role": "user", "content": [{"text": "テストクエリ"}]}]
        system_prompt = "テスト用システムプロンプト"
        model_id = "test-model"
        tool_config = {"tools": [], "toolChoice": {"auto": {}}}
        
        mock_client = mock_error_client()
        
        try:
            call_bedrock_api(mock_client, messages, system_prompt, model_id, tool_config)
            logging.error("エラーが発生しませんでした")
            return False
        except Exception as e:
            logging.info(f"想定通りエラーが発生しました: {e}")
            
            try:
                response = call_bedrock_api(mock_client, messages, system_prompt, model_id, tool_config)
                
                if response.get("stopReason") != "end_turn":
                    logging.error(f"stopReasonが 'end_turn' ではありません: {response.get('stopReason')}")
                    return False
                
                stop_analysis = analyze_stop_reason(response.get("stopReason"))
                if stop_analysis.get("should_continue"):
                    logging.error("stopReasonの分析が正しくありません")
                    return False
                
                logging.info("エラー後のリカバリーが成功しました")
            except Exception as e2:
                logging.error(f"エラー後のリカバリーに失敗しました: {e2}")
                return False
    
    logging.info("異常系テスト成功")
    return True

def test_main_e2e():
    """main.pyのE2Eテスト - 実際のmain.pyの処理を模倣してテスト"""
    logging.info("=== main.py E2Eテスト開始 ===")
    
    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error(f"ブラウザ初期化に失敗: {init_res.get('message')}")
        return False
    
    goto_res = goto_url("https://www.google.co.jp/")
    if goto_res.get("status") != "success":
        logging.error(f"URL移動に失敗: {goto_res.get('message')}")
        return False
    
    aria_res = get_aria_snapshot()
    if aria_res.get("status") != "success":
        logging.error(f"ARIA Snapshot取得に失敗: {aria_res.get('message')}")
        return False
    
    with patch('src.bedrock.create_bedrock_client', side_effect=mock_bedrock_client):
        messages = [{"role": "user", "content": [{"text": "テストクエリ"}]}]
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
            }
        }
        
        max_turns = 3
        turn_count = 0
        
        while turn_count < max_turns:
            turn_count += 1
            logging.info(f"--- ターン {turn_count} 開始 ---")
            
            try:
                mock_client = mock_bedrock_client()
                response = call_bedrock_api(mock_client, messages, system_prompt, model_id, tool_config)
                
                usage = response.get("usage", {})
                result["token_usage"]["inputTokens"] += usage.get("inputTokens", 0)
                result["token_usage"]["outputTokens"] += usage.get("outputTokens", 0)
                result["token_usage"]["totalTokens"] += usage.get("inputTokens", 0) + usage.get("outputTokens", 0)
                
            except Exception as e:
                err_msg = str(e)
                logging.error(f"Bedrock API呼び出しエラー: {err_msg}")
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
            logging.error(f"E2Eテストが失敗しました: {result.get('message', '不明なエラー')}")
            return False
        
        if turn_count >= max_turns:
            logging.error(f"最大ターン数 ({max_turns}) に達しました")
            return False
        
        logging.info(f"E2Eテスト成功: {turn_count}ターンで正常に終了")
    
    cleanup_browser()
    
    return True

def main():
    parser = argparse.ArgumentParser(description='main.pyのE2Eテスト')
    parser.add_argument('--debug', action='store_true', help='デバッグモードを有効にする')
    parser.add_argument('--timeout', type=int, default=60, help='テスト全体のタイムアウト（秒）')
    args = parser.parse_args()

    setup_logging(debug=args.debug or True)
    
    logging.info(f"main.py E2Eテスト開始: headless={os.environ.get('HEADLESS', 'false')}, CI={os.environ.get('CI', 'false')}")

    start_time = time.time()
    
    try:
        normal_success = test_normal_case()
        error_success = test_error_case()
        e2e_success = test_main_e2e()
        
        elapsed_time = time.time() - start_time
        logging.info(f"テスト実行時間: {elapsed_time:.2f}秒")
        
        if normal_success and error_success and e2e_success:
            logging.info("すべてのテストが成功しました")
            return 0
        else:
            logging.error("一部のテストが失敗しました")
            return 1
    except Exception as e:
        logging.error(f"テスト実行中にエラーが発生しました: {e}")
        traceback.print_exc()
        return 1
    finally:
        try:
            cleanup_browser()
            logging.info("ブラウザのクリーンアップが完了しました")
        except Exception as e:
            logging.error(f"ブラウザのクリーンアップ中にエラーが発生しました: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    import time
    exit_code = main()
    logging.info(f"テストプロセスを終了します: exit_code={exit_code}")
    sys.exit(exit_code)
