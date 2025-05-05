import json
import logging
from typing import Dict, Any, List, Optional, Union, Tuple
from .utils import add_debug_log, load_credentials, log_json_debug
from .browser.worker import initialize_browser
from .browser import dispatch_browser_tool, get_aria_snapshot
from .prompts import get_system_prompt

logger = logging.getLogger(__name__)

def initialize_agent(credentials_path: str) -> Dict[str, Any]:
    """エージェントを初期化し、必要なリソースをセットアップします"""
    credentials = load_credentials(credentials_path)
    if not credentials:
        return {"status": "error", "message": f"認証情報の読み込みに失敗しました: {credentials_path}"}
    
    browser_status = initialize_browser()
    if browser_status.get("status") != "success":
        return {"status": "error", "message": f"ブラウザの初期化に失敗しました: {browser_status.get('message')}"}
    
    return {"status": "success", "credentials": credentials, "browser_status": browser_status}

def get_inference_config(model_id: str) -> Dict[str, Any]:
    """モデルごとに最適な推論パラメータを返す"""
    cfg = {"maxTokens": 3000}

    if "amazon.nova" in model_id:          # Nova 系
        cfg.update({"topP": 1, "temperature": 1})
    elif "anthropic.claude" in model_id:   # Claude 系（必要なら）
        cfg.update({"temperature": 0})   # 例
    return cfg

def get_browser_tools_config() -> List[Dict[str, Any]]:
    """利用可能なブラウザ操作ツールの設定を取得します"""
    return [
        {
            "toolSpec": {
                "name": "click_element",
                "description": "ARIA Snapshotから要素の ref_id (数値) を特定してから使用してください。指定された参照IDを持つ要素をクリックします。実行後の最新のARIA Snapshotが自動的に結果に含まれます（成功時も失敗時も）。",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "ref_id": {
                                "type": "integer",
                                "description": "クリックする要素の参照ID（数値、ARIA Snapshotで確認）"
                            }
                        },
                        "required": ["ref_id"]
                    }
                }
            }
        },
        {
            "toolSpec": {
                "name": "input_text",
                "description": "ARIA Snapshotから要素の ref_id (数値) を特定してから使用してください。指定された参照IDを持つ要素にテキストを入力し、Enterキーを押します。実行後の最新のARIA Snapshotが自動的に結果に含まれます（成功時も失敗時も）。",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "入力するテキスト"
                            },
                            "ref_id": {
                                "type": "integer",
                                "description": "テキストを入力する要素の参照ID（数値、ARIA Snapshotで確認）"
                            }
                        },
                        "required": ["text", "ref_id"]
                    }
                }
            }
        }
    ]

def update_token_usage(response: Dict[str, Any], token_usage: Dict[str, int]) -> Dict[str, int]:
    """トークン使用量を更新する"""
    usage = response.get("usage", {})
    token_usage["inputTokens"] += usage.get("inputTokens", 0)
    token_usage["outputTokens"] += usage.get("outputTokens", 0)
    token_usage["totalTokens"] += usage.get("inputTokens", 0) + usage.get("outputTokens", 0)
    return token_usage

def _get_current_aria_snapshot() -> Tuple[Optional[Dict], Optional[str]]:
    """現在のARIA Snapshotを取得するヘルパー関数"""
    aria_snapshot_result = get_aria_snapshot()
    if aria_snapshot_result.get('status') == 'success':
        return aria_snapshot_result.get('aria_snapshot'), None
    else:
        error_message = f"ARIA Snapshotの取得に失敗しました: {aria_snapshot_result.get('message', '不明なエラー')}"
        logger.error(error_message)
        return None, error_message

def format_user_query_with_aria_snapshot(user_input: str, aria_snapshot: Optional[Dict]) -> str:
    """ユーザー入力とARIA Snapshotを組み合わせたフォーマット済みテキストを返します"""
    aria_snapshot_str = "ARIA Snapshotを取得できませんでした。"
    if aria_snapshot is not None:
        try:
            aria_snapshot_json = json.dumps(aria_snapshot, ensure_ascii=False, indent=2)
            # 長さ制限を適用
            MAX_ARIA_SNAPSHOT_LENGTH = 100000
            if len(aria_snapshot_json) > MAX_ARIA_SNAPSHOT_LENGTH:
                aria_snapshot_json = aria_snapshot_json[:MAX_ARIA_SNAPSHOT_LENGTH] + "\n... (truncated)"
            aria_snapshot_str = f"現在のページのARIA Snapshot:\n```json\n{aria_snapshot_json}\n```"
        except Exception as e:
            aria_snapshot_str = f"ARIA Snapshotの変換エラー: {e}"
    
    formatted_text = f"""ユーザーからの指示: {user_input}

{aria_snapshot_str}

上記のユーザー指示と現在のページ状態（ARIA Snapshot）を基に応答またはツールを実行してください。"""
    
    return formatted_text

def handle_user_query(
    user_input: str,
    bedrock_session,
    system_prompt: str,
    model_id: str,
    session_state: Optional[Dict] = None
) -> Dict[str, Any]:
    """ユーザー入力を処理して応答を返す"""
    result = {
        "status": "success",
        "messages": [], # 最終的にユーザーに見せるためのメッセージ履歴
        "token_usage": {
            "inputTokens": 0,
            "outputTokens": 0,
            "totalTokens": 0,
        }
    }

    add_debug_log(f"ユーザー入力: {user_input}")

    tool_specs = get_browser_tools_config()
    tool_config = {
        "tools": tool_specs,
        "toolChoice": {"auto": {}}
    }

    # Bedrock APIに渡すためのメッセージ履歴（内部管理用）
    messages_for_api = []
    
    # 初回リクエスト時、現在のARIA Snapshotを取得して組み込み
    current_aria_snapshot, aria_snapshot_error = _get_current_aria_snapshot()
    
    # ユーザー入力とARIA Snapshotを組み合わせたテキストを作成
    formatted_user_input = format_user_query_with_aria_snapshot(user_input, current_aria_snapshot)
    
    # 初回のユーザーメッセージを作成
    initial_user_message = {"role": "user", "content": [{"text": formatted_user_input}]}
    messages_for_api.append(initial_user_message)
    
    # ユーザーには元の質問のみを表示する形式でメッセージ履歴に追加
    user_facing_message = {"role": "user", "content": [{"text": user_input}]}
    result["messages"].append(user_facing_message)

    max_turns = 20
    turn_count = 0

    while turn_count < max_turns:
        turn_count += 1
        add_debug_log(f"--- ターン {turn_count} 開始 ---")

        # 4. Bedrock API呼び出し
        try:
            inference_config = get_inference_config(model_id)
            request_params = {
                "modelId": model_id,
                "messages": messages_for_api, # フォーマット済みメッセージを使用
                "system": [{"text": system_prompt}],
                "inferenceConfig": inference_config,
                "toolConfig": tool_config
            }
            log_json_debug("Bedrock Request", request_params, level="DEBUG")
            response = bedrock_session.converse(**request_params)
            log_json_debug("Bedrock Response", response, level="DEBUG")

            result["token_usage"] = update_token_usage(response, result["token_usage"])

        except Exception as e:
            err_msg = str(e)
            add_debug_log(f"Bedrock API呼び出しエラー: {err_msg}")
            result["status"] = "error"
            result["message"] = f"Bedrock APIエラー: {err_msg}"
            break

        output = response.get("output", {})
        message = output.get("message", {})
        stop_reason = response.get("stopReason")

        # 5. アシスタント応答をAPI用履歴と結果用履歴に追加
        assistant_message = {"role": "assistant", "content": message.get("content", [])}
        messages_for_api.append(assistant_message)
        result["messages"].append(assistant_message) # ユーザーに見せる結果にも追加

        tool_calls = [c["toolUse"] for c in message.get("content", []) if "toolUse" in c]

        # 6. ツール実行と結果の作成
        if tool_calls:
            merged_user_content = [] # このターンのツール結果を入れるリスト
            tool_execution_failed = False # ツール実行失敗フラグ
            
            for tool_call in tool_calls:
                tool_name = tool_call.get("name")
                tool_input = tool_call.get("input", {})
                tool_use_id = tool_call.get("toolUseId")

                logger.info(f"ツール実行: {tool_name}")
                if tool_input:
                    logger.debug(f"パラメータ: {json.dumps(tool_input, ensure_ascii=False)}")

                # ツール実行（ツール側でARIA Snapshot取得処理が追加されている）
                tool_result_data = dispatch_browser_tool(tool_name, tool_input)
                logger.info(f"ツール実行結果: {json.dumps(tool_result_data, ensure_ascii=False)}")

                # ツール実行ステータスを確認
                tool_status = "success" if tool_result_data.get('status') == 'success' else "error"
                
                # ツール結果JSONにはツール実行結果とARIA Snapshot情報を含める
                tool_result_json = {
                    "operation_status": tool_result_data.get('status'),
                    "message": tool_result_data.get('message', '')
                }
                
                # ツール実行後に取得したARIA Snapshotがあれば含める
                if 'aria_snapshot' in tool_result_data:
                    tool_result_json["aria_snapshot"] = tool_result_data.get('aria_snapshot')
                    if 'aria_snapshot_message' in tool_result_data:
                        tool_result_json["aria_snapshot_message"] = tool_result_data.get('aria_snapshot_message')
                
                # toolResultブロックを作成
                tool_result_block = {
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"json": tool_result_json}],
                        "status": tool_status
                    }
                }
                
                merged_user_content.append(tool_result_block)
                
                if tool_status == "error":
                    logger.error(f"ツール '{tool_name}' の実行に失敗しました: {tool_result_data.get('message')}")
                    tool_execution_failed = True

            # マージした内容でuserメッセージを作成
            merged_user_message = {"role": "user", "content": merged_user_content}
            
            # API用履歴と結果用履歴の両方に、このマージされたuserメッセージを追加
            messages_for_api.append(merged_user_message)
            result["messages"].append(merged_user_message)

            continue # 次のループへ

        # 7. ループ終了判定 (stop_reason)
        if stop_reason == "end_turn":
            add_debug_log("Stop reasonが 'end_turn' のため終了します。")
            break
        elif stop_reason == "tool_use":
            add_debug_log("Stop reasonが 'tool_use' ですが、ツールが見つかりませんでした。予期せぬ状態のため終了します。")
            result["status"] = "error"
            result["message"] = "LLMがtool_useで停止しましたが、toolUseブロックがありませんでした。"
            break
        elif stop_reason: # 他のstop_reason (max_tokensなど)
            add_debug_log(f"Stop reason '{stop_reason}' のため終了します。")
            if stop_reason == "max_tokens":
                 logger.warning("最大トークン数に達したため、応答が途中で打ち切られている可能性があります。")
            break
        else: # stop_reason が null や空文字の場合 (通常は発生しないはず)
            add_debug_log("Stop reasonが不明です。予期せぬ状態のためループを終了します。")
            result["status"] = "error"
            result["message"] = "LLMが予期せぬ状態で停止しました（Stop reason不明）。"
            break

    if turn_count >= max_turns:
        logger.warning(f"最大ターン数 ({max_turns}) に達したため、処理を終了します。")
        if result["status"] == "success": # 他のエラーが発生していなければ
             result["status"] = "error" # 最大ターン到達もエラー扱いにする場合
             result["message"] = f"最大ターン数 ({max_turns}) に達しました。"

    add_debug_log(f"--- 処理終了: Status={result['status']} ---")
    return result
