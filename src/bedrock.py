"""
Amazon Bedrock API Integration Module

Implements browser automation agent using Bedrock API with LLM capabilities.
This module provides:
- API communication settings
- Inference parameter management
- API response analysis
"""

import logging
from typing import Any

import boto3

from .exceptions import BedrockAPIError
from .utils import add_debug_log, log_json_debug

logger = logging.getLogger(__name__)


def get_inference_config(model_id: str) -> dict[str, Any]:
    """Return optimal inference parameters for each model"""
    cfg = {"maxTokens": 3000}

    if "amazon.nova" in model_id:
        cfg.update({"topP": 1, "temperature": 1})
    elif "anthropic.claude" in model_id:
        cfg.update({"temperature": 0})
    return cfg


def update_token_usage(
    response: dict[str, Any], token_usage: dict[str, int]
) -> dict[str, int]:
    """Update token usage statistics"""
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
    """Call Bedrock API to get LLM response

    Args:
        bedrock_runtime: Bedrock runtime session
        messages: Conversation history
        system_prompt: System prompt
        model_id: Model ID to use
        tool_config: Tool configuration

    Returns:
        API response
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
    except Exception as exc:  # noqa: BLE001
        # Catch and wrap boto3 exceptions
        err_msg = str(exc)
        add_debug_log(f"Bedrock API call error: {err_msg}", level="ERROR")
        raise BedrockAPIError(err_msg) from exc


def analyze_stop_reason(stop_reason: str) -> dict[str, Any]:
    """Analyze response stop reason and return appropriate handling method

    Args:
        stop_reason: stopReason value from API response

    Returns:
        Dictionary with analysis results and handling instructions
    """
    if stop_reason == "end_turn":
        add_debug_log("Ending because stop reason is 'end_turn'.")
        return {"should_continue": False, "error": False, "message": "Completed normally"}

    if stop_reason == "tool_use":
        add_debug_log(
            "Stop reason is 'tool_use' but no tool was found. Ending due to unexpected state."
        )
        return {
            "should_continue": False,
            "error": True,
            "message": "LLM stopped with tool_use but no toolUse block was found.",
        }

    if stop_reason == "max_tokens":
        add_debug_log("Ending because stop reason is 'max_tokens'.", level="WARNING")
        return {
            "should_continue": False,
            "error": False,
            "message": "Maximum token count reached. Response may have been truncated.",
        }

    if stop_reason:  # Other stop_reason
        add_debug_log(f"Ending because stop reason is '{stop_reason}'.")
        return {
            "should_continue": False,
            "error": False,
            "message": f"Stop reason: {stop_reason}",
        }

    # For null or empty stop_reason
    add_debug_log("Stop reason is unknown. Ending loop due to unexpected state.")
    return {
        "should_continue": False,
        "error": True,
        "message": "LLM stopped in an unexpected state (unknown stop reason).",
    }


def extract_tool_calls(message_content: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract tool calls from message content

    Args:
        message_content: Assistant message content

    Returns:
        List of tool calls
    """
    return [c["toolUse"] for c in message_content if "toolUse" in c]


def create_bedrock_client(credentials: dict[str, str]) -> Any:
    """Create Bedrock client

    Args:
        credentials: AWS credentials

    Returns:
        Bedrock runtime client
    """
    bedrock_runtime = boto3.client(
        service_name="bedrock-runtime",
        region_name="us-west-2",
        aws_access_key_id=credentials.get("aws_access_key_id"),
        aws_secret_access_key=credentials.get("aws_secret_access_key"),
    )

    return bedrock_runtime


__all__: list[str] = [
    "get_inference_config",
    "update_token_usage",
    "call_bedrock_api",
    "analyze_stop_reason",
    "extract_tool_calls",
    "create_bedrock_client",
    "BedrockAPIError",
]
