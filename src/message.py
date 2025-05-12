"""
Message Management Module

Manages conversation history passed to Bedrock API and formats messages displayed to users.
"""

import json
import logging
from typing import Any

import main as constants  # Reference to constants from entry point
from src.bedrock import (BedrockAPIError, analyze_stop_reason,
                         call_bedrock_api, create_bedrock_client,
                         extract_tool_calls, update_token_usage)
from src.browser import cleanup_browser, get_aria_snapshot, initialize_browser
from src.prompts import get_system_prompt
from src.tools import dispatch_browser_tool, get_browser_tools_config
from src.utils import load_credentials, setup_logging

logger = logging.getLogger(__name__)


def format_user_query_with_aria_snapshot(
    user_input: str, aria_snapshot: dict | None
) -> str:
    """Returns formatted text combining user input and ARIA Snapshot"""
    aria_snapshot_str = "Could not retrieve ARIA Snapshot."
    if aria_snapshot is not None:
        try:
            aria_snapshot_json = json.dumps(aria_snapshot, ensure_ascii=False, indent=2)
            # Apply length limit
            max_aria_snapshot_length = 100000
            if len(aria_snapshot_json) > max_aria_snapshot_length:
                truncated_part = "\n... (truncated)"
                aria_snapshot_json = (
                    aria_snapshot_json[:max_aria_snapshot_length] + truncated_part
                )
            aria_snapshot_str = (
                f"Current page ARIA Snapshot:\n" f"```json\n{aria_snapshot_json}\n```"
            )
        except ValueError as e:
            aria_snapshot_str = f"ARIA Snapshot conversion error: {e}"

    formatted_text = f"""User instruction: {user_input}

"
                      f"{aria_snapshot_str}

"
                      f"Based on the user instruction and current page state (ARIA Snapshot) above,"
                      f"please respond or execute a tool."""

    return formatted_text


def create_initial_messages(
    user_input: str, aria_snapshot: dict | None
) -> list[dict[str, Any]]:
    """Create initial message list

    Args:
        user_input: User's input text
        aria_snapshot: Current ARIA Snapshot

    Returns:
        Message list for Bedrock API
    """
    # Create text combining user input and ARIA Snapshot
    formatted_user_input = format_user_query_with_aria_snapshot(
        user_input, aria_snapshot
    )

    # Create initial user message
    initial_user_message = {"role": "user", "content": [{"text": formatted_user_input}]}

    return [initial_user_message]


def create_user_facing_messages(user_input: str) -> list[dict[str, Any]]:
    """Create message list to display to the user

    Args:
        user_input: User's input text

    Returns:
        Message list to display to the user
    """
    # Create message showing only the original question to the user
    user_facing_message = {"role": "user", "content": [{"text": user_input}]}

    return [user_facing_message]


def add_assistant_message(
    messages: list[dict[str, Any]], assistant_content: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Add assistant message to the list

    Args:
        messages: Existing message list
        assistant_content: Assistant's response content

    Returns:
        Updated message list
    """
    assistant_message = {"role": "assistant", "content": assistant_content}
    messages.append(assistant_message)
    return messages


def create_tool_result_message(tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Create user message containing tool execution results

    Args:
        tool_results: List of tool execution results

    Returns:
        User message containing tool results
    """
    merged_content = []

    for result in tool_results:
        tool_use_id = result.get("toolUseId")
        tool_result_data = result.get("result", {})
        tool_status = (
            "success" if tool_result_data.get("status") == "success" else "error"
        )

        # Tool result JSON includes both tool execution result and ARIA Snapshot information
        tool_result_json = {
            "operation_status": tool_result_data.get("status"),
            "message": tool_result_data.get("message", ""),
        }

        # Include ARIA Snapshot retrieved after tool execution if available
        if "aria_snapshot" in tool_result_data:
            tool_result_json["aria_snapshot"] = tool_result_data.get("aria_snapshot")
            if "aria_snapshot_message" in tool_result_data:
                tool_result_json["aria_snapshot_message"] = tool_result_data.get(
                    "aria_snapshot_message"
                )

        # Create toolResult block
        tool_result_block = {
            "toolResult": {
                "toolUseId": tool_use_id,
                "content": [{"json": tool_result_json}],
                "status": tool_status,
            }
        }

        merged_content.append(tool_result_block)

    # Create user message with merged content
    user_message = {"role": "user", "content": merged_content}
    return user_message


# ---------------------------------------------------------------------------
# Conversation loop (moved from main.py)
# ---------------------------------------------------------------------------


def run_cli_mode() -> int:  # noqa: D401
    """Execute the browser automation agent. Main logic."""

    # Set execution parameters
    query = constants.DEFAULT_QUERY
    model_id = constants.DEFAULT_MODEL_ID
    credentials_path = constants.DEFAULT_CREDENTIALS_PATH
    max_turns = constants.DEFAULT_MAX_TURNS

    setup_logging()
    logger.info("Executing - Model: %s", model_id)

    # Initialize browser
    init_result = initialize_browser()
    if init_result.get("status") != "success":
        logger.error("Browser initialization failed: %s", init_result.get("message"))
        return 1

    # Load AWS credentials
    credentials = load_credentials(credentials_path)
    if not credentials:
        logger.error("Failed to load credentials: %s", credentials_path)
        return 1

    # Create Bedrock client
    bedrock_runtime = create_bedrock_client(credentials)

    # Initialize result data structure
    result = {
        "status": "success",
        "messages": [],  # Message history to show to user
        "token_usage": {
            "inputTokens": 0,
            "outputTokens": 0,
            "totalTokens": 0,
        },
    }

    # Process user query
    logger.info("Processing query: %s", query)

    # Get tool configuration
    tool_config = {"tools": get_browser_tools_config(), "toolChoice": {"auto": {}}}

    # Get current ARIA Snapshot for initial request
    aria_snapshot_result = get_aria_snapshot()
    current_aria_snapshot: list[dict[str, Any]] | None = (
        aria_snapshot_result.get("aria_snapshot")
        if aria_snapshot_result.get("status") == "success"
        else None
    )
    if not current_aria_snapshot:
        logger.error(
            "Failed to get ARIA Snapshot: %s",
            aria_snapshot_result.get("message", "Unknown error"),
        )

    # Message history for Bedrock API (internal use)
    messages_for_api = create_initial_messages(query, current_aria_snapshot)

    # Message history to display to user
    result["messages"] = create_user_facing_messages(query)

    # Start conversation loop
    turn_count = 0

    while turn_count < max_turns:
        turn_count += 1
        logger.info("--- Turn %s start ---", turn_count)

        try:
            # Call Bedrock API
            response = call_bedrock_api(
                bedrock_runtime,
                messages_for_api,
                get_system_prompt(),
                model_id,
                tool_config,
            )

            # Update token usage
            result["token_usage"] = update_token_usage(response, result["token_usage"])

        except BedrockAPIError as e:
            err_msg = str(e)
            logger.error("Bedrock API call error: %s", err_msg)
            result["status"] = "error"
            result["message"] = f"Bedrock API error: {err_msg}"
            break

        # Analyze response
        output = response.get("output", {})
        message = output.get("message", {})
        stop_reason = response.get("stopReason")

        # Add assistant response to history
        message_content = message.get("content", [])
        messages_for_api = add_assistant_message(messages_for_api, message_content)
        result["messages"] = add_assistant_message(result["messages"], message_content)

        # Display assistant's text messages in real-time
        for content in message_content:
            if "text" in content:
                print(f"\n{content['text']}\n")

        # Extract tool calls
        tool_calls = extract_tool_calls(message_content)

        if tool_calls:
            tool_results: list[dict[str, Any]] = []
            for tool_call in tool_calls:
                tool_name = tool_call.get("name")
                tool_input = tool_call.get("input", {})
                tool_use_id = tool_call.get("toolUseId")

                logger.info("Tool execution: %s", tool_name)

                # Execute tool
                tool_result_data = dispatch_browser_tool(tool_name, tool_input)

                tool_results.append(
                    {"toolUseId": tool_use_id, "result": tool_result_data}
                )

            # Create tool result message
            tool_result_message = create_tool_result_message(tool_results)

            # Add to history
            messages_for_api.append(tool_result_message)
            result["messages"].append(tool_result_message)

            continue  # Next loop iteration

        # Analyze stop reason
        stop_analysis = analyze_stop_reason(stop_reason)
        if not stop_analysis["should_continue"]:
            if stop_analysis["error"]:
                result["status"] = "error"
                result["message"] = stop_analysis["message"]
            break

    # Check for max turns exceeded
    if turn_count >= max_turns:
        logger.warning("Maximum number of turns (%s) reached, ending process.", max_turns)
        if result["status"] == "success":
            result["status"] = "error"
            result["message"] = f"Maximum number of turns ({max_turns}) reached."

    # Wait 5 seconds after processing
    import time
    logger.info("Processing complete. Waiting for 5 seconds...")
    time.sleep(5)

    # Close browser
    cleanup_browser()

    # Display result
    logger.info("Processing complete")

    # Display token usage
    token_usage = result.get("token_usage", {})
    logger.info(
        "Token usage: input=%s output=%s total=%s",
        f"{token_usage.get('inputTokens', 0):,}",
        f"{token_usage.get('outputTokens', 0):,}",
        f"{token_usage.get('totalTokens', 0):,}",
    )

    return 0
