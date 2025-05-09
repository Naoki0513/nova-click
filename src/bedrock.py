"""
Amazon Bedrock API 連携モジュール

Bedrock API を使用して、LLMに基づくブラウザ操作エージェントを実現します。
以下の機能を提供します：
- API通信設定
- 推論パラメータの管理
- APIレスポンスの解析
"""

import logging
from typing import Any

import boto3

from .utils import add_debug_log, log_json_debug

logger = logging.getLogger(__name__)


def get_inference_config(model_id: str) -> dict[str, Any]:
    """モデルごとに最適な推論パラメータを返す"""
    cfg = {"maxTokens": 3000}

    if "amazon.nova" in model_id:
        cfg.update({"topP": 1, "temperature": 1})
    elif "anthropic.claude" in model_id:
        cfg.update({"temperature": 0})
    return cfg


def update_token_usage(
    response: dict[str, Any], token_usage: dict[str, int]
) -> dict[str, int]:
    """トークン使用量を更新する"""
    usage = response.get("usage", {})
    token_usage["inputTokens"] += usage.get("inputTokens", 0)
    token_usage["outputTokens"] += usage.get("outputTokens", 0)
    token_usage["totalTokens"] += usage.get("inputTokens", 0) + usage.get(
        "outputTokens", 0
    )
    return token_usage


def call_bedrock_api(
    bedrock_runtime,
    messages: list[dict[str, Any]],
    system_prompt: str,
    model_id: str,
    tool_config: dict[str, Any],
) -> dict[str, Any]:
    """Bedrock API を呼び出して、LLMの応答を取得します

    Args:
        bedrock_runtime: Bedrock ランタイムセッション
        messages: 会話履歴
        system_prompt: システムプロンプト
        model_id: 使用するモデルID
        tool_config: ツール設定

    Returns:
        APIレスポンス
    """
    try:
        inference_config = get_inference_config(model_id)
        request_params = {
            "modelId": model_id,
            "messages": messages,
            "system": [{"text": system_prompt}],
            "inferenceConfig": inference_config,
            "toolConfig": tool_config,
        }
        log_json_debug("Bedrock Request", request_params, level="DEBUG")
        response = bedrock_runtime.converse(**request_params)
        log_json_debug("Bedrock Response", response, level="DEBUG")

        return response
    except Exception as e:
        err_msg = str(e)
        add_debug_log(f"Bedrock API呼び出しエラー: {err_msg}")
        raise


def analyze_stop_reason(stop_reason: str) -> dict[str, Any]:
    """応答停止理由を分析し、適切な処理方法を返します

    Args:
        stop_reason: APIレスポンスのstopReason値

    Returns:
        分析結果と処理方法を含む辞書
    """
    if stop_reason == "end_turn":
        add_debug_log("Stop reasonが 'end_turn' のため終了します。")
        return {"should_continue": False, "error": False, "message": "正常終了"}

    if stop_reason == "tool_use":
        add_debug_log(
            "Stop reasonが 'tool_use' ですが、ツールが見つかりませんでした。予期せぬ状態のため終了します。"
        )
        return {
            "should_continue": False,
            "error": True,
            "message": "LLMがtool_useで停止しましたが、toolUseブロックがありませんでした。",
        }

    if stop_reason == "max_tokens":
        add_debug_log("Stop reasonが 'max_tokens' のため終了します。", level="WARNING")
        return {
            "should_continue": False,
            "error": False,
            "message": "最大トークン数に達したため、応答が途中で打ち切られている可能性があります。",
        }

    if stop_reason:  # 他のstop_reason
        add_debug_log(f"Stop reason '{stop_reason}' のため終了します。")
        return {
            "should_continue": False,
            "error": False,
            "message": f"停止理由: {stop_reason}",
        }

    # stop_reason が null や空文字の場合
    add_debug_log("Stop reasonが不明です。予期せぬ状態のためループを終了します。")
    return {
        "should_continue": False,
        "error": True,
        "message": "LLMが予期せぬ状態で停止しました（Stop reason不明）。",
    }


def extract_tool_calls(message_content: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """メッセージコンテンツからツール呼び出しを抽出します

    Args:
        message_content: アシスタントメッセージのコンテンツ

    Returns:
        ツール呼び出しのリスト
    """
    return [c["toolUse"] for c in message_content if "toolUse" in c]


def create_bedrock_client(credentials: dict[str, str]) -> Any:
    """Bedrock クライアントを作成します

    Args:
        credentials: AWS認証情報

    Returns:
        Bedrock ランタイムクライアント
    """
    bedrock_runtime = boto3.client(
        service_name="bedrock-runtime",
        region_name="us-west-2",
        aws_access_key_id=credentials.get("aws_access_key_id"),
        aws_secret_access_key=credentials.get("aws_secret_access_key"),
    )

    return bedrock_runtime
