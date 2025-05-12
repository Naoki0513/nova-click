"""
main.py E2E Test Script

Tests the main.py process end-to-end, verifying that the conversation API ends normally
with a stopReason of "endTurn" even when errors occur.

Environment variables:
    HEADLESS - If 'true', runs the browser in headless mode
    CI - If 'true', uses CI environment log settings
"""

import logging
import os
import sys
import time
import traceback
from typing import Any, Dict
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.bedrock import (
    analyze_stop_reason, call_bedrock_api)
from src.browser import (
    cleanup_browser, get_aria_snapshot, goto_url, initialize_browser)
from src.utils import \
    setup_logging

# Test parameters (modify these to change test conditions)
TEST_URL = "https://www.google.co.jp/"
TEST_MODEL_ID = "test-model"
TEST_SYSTEM_PROMPT = "Test system prompt"
TEST_USER_QUERY = "Test query"
TEST_MAX_TURNS = 3
# Operation timeout (seconds)
TEST_TIMEOUT = 60

MOCK_BEDROCK_RESPONSE = {
    "output": {
        "message": {
            "role": "assistant",
            "content": [{"text": "Test response. Browser operation completed."}],
        }
    },
    "stopReason": "end_turn",
    "usage": {"inputTokens": 100, "outputTokens": 50, "totalTokens": 150},
}

MOCK_ERROR_RESPONSE = {
    "output": {
        "message": {
            "role": "assistant",
            "content": [{"text": "An error occurred, but the conversation will end normally."}],
        }
    },
    "stopReason": "end_turn",
    "usage": {"inputTokens": 100, "outputTokens": 50, "totalTokens": 150},
}


def mock_bedrock_client(*args, **kwargs):  
    """Create a mock Bedrock client"""
    mock_client = MagicMock()
    mock_client.converse.return_value = MOCK_BEDROCK_RESPONSE
    return mock_client


def verify_api_response(response: Dict[str, Any]) -> bool:
    """Generic function to verify API response

    Args:
        response: Response from Bedrock API

    Returns:
        bool: Whether verification was successful
    """
    success = True

    # 1. Basic structure check
    if not isinstance(response, dict):
        logging.error("API response must be a dict type")
        return False

    # 2. Check for required fields
    required_fields = ["output", "stopReason", "usage"]
    for field in required_fields:
        if field not in response:
            logging.error("Required field '%s' is missing from response", field)
            success = False

    if not success:
        return False

    # 3. Check output message structure
    output = response.get("output", {})
    message = output.get("message", {})

    if not message.get("role"):
        logging.error("Message is missing role field")
        success = False

    content = message.get("content", [])
    if not content or not isinstance(content, list):
        logging.error("Message content field is invalid")
        success = False

    # 4. Check usage information
    usage = response.get("usage", {})
    usage_fields = ["inputTokens", "outputTokens", "totalTokens"]
    for field in usage_fields:
        if field not in usage:
            logging.warning("Usage information missing '%s' field", field)

    # 5. Analyze stopReason
    stop_reason = response.get("stopReason")
    if stop_reason != "end_turn":
        logging.error("stopReason is '%s' instead of expected 'end_turn'", stop_reason)
        success = False

    return success


def test_normal_case(url=TEST_URL):
    """Normal case test - Standard conversation API flow"""
    logging.info("=== Normal case test start ===")

    # Browser initialization and preparation
    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error("Browser initialization failed: %s", init_res.get("message"))
        assert False, "Browser initialization failed"

    goto_res = goto_url(url)
    if goto_res.get("status") != "success":
        logging.error("URL navigation failed: %s", goto_res.get("message"))
        assert False, "URL navigation failed"

    # Initial ARIA snapshot retrieval
    aria_res = get_aria_snapshot()
    if aria_res.get("status") != "success":
        logging.error("ARIA Snapshot retrieval failed: %s", aria_res.get("message"))
        assert False, "ARIA Snapshot retrieval failed"

    initial_elements = aria_res.get("aria_snapshot", [])
    logging.info("Initial element count: %d", len(initial_elements))

    # Bedrock API call test
    success = True
    with patch("src.bedrock.create_bedrock_client", side_effect=mock_bedrock_client):
        messages = [{"role": "user", "content": [{"text": TEST_USER_QUERY}]}]
        system_prompt = TEST_SYSTEM_PROMPT
        model_id = TEST_MODEL_ID
        tool_config = {"tools": [], "toolChoice": {"auto": {}}}

        mock_client = mock_bedrock_client()

        # Record state before API call
        pre_call_time = time.time()

        response = call_bedrock_api(
            mock_client, messages, system_prompt, model_id, tool_config
        )

        # Record elapsed time after API call
        call_duration = time.time() - pre_call_time
        logging.info("API call duration: %.2f seconds", call_duration)

        # Verify state after API call
        post_api_aria_res = get_aria_snapshot()
        if post_api_aria_res.get("status") == "success":
            post_elements = post_api_aria_res.get("aria_snapshot", [])
            logging.info("Element count after API call: %d", len(post_elements))

            # Confirm DOM state hasn't changed (API call doesn't perform DOM operations)
            if len(initial_elements) != len(post_elements):
                logging.warning(
                    "DOM element count changed before and after API call: %d → %d",
                    len(initial_elements),
                    len(post_elements),
                )

        # Detailed response verification
        if not verify_api_response(response):
            logging.error("API response verification failed")
            success = False

        # stopReason verification (basic check)
        if response.get("stopReason") != "end_turn":
            logging.error(
                "stopReason is not 'end_turn': %s", response.get("stopReason")
            )
            success = False
        else:
            stop_analysis = analyze_stop_reason(response.get("stopReason"))
            if stop_analysis.get("should_continue"):
                logging.error("stopReason analysis is incorrect")
                success = False
            elif stop_analysis.get("error"):
                logging.error("Error detected in normal case")
                success = False

    # Log response details
    if "response" in locals():
        try:
            output = response.get("output", {})
            message = output.get("message", {})
            content = message.get("content", [])
            response_text = content[0].get("text") if content else "(No text)"
            logging.info(
                "API response text: %s",
                (
                    response_text[:100] + "..."
                    if len(response_text) > 100
                    else response_text
                ),
            )
        except (KeyError, IndexError) as e:
            logging.warning("Error while extracting response text: %s", e)

    if success:
        logging.info("Normal case test successful")

    assert success, "Normal case test failed"


def test_error_case(url=TEST_URL):  
    """Error case test - Verify conversation API ends normally even when errors occur"""
    logging.info("=== Error case test start ===")

    # Browser initialization
    success = True
    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error("Browser initialization failed: %s", init_res.get("message"))
        assert False, "Browser initialization failed"

    goto_res = goto_url(url)
    if goto_res.get("status") != "success":
        logging.error("URL navigation failed: %s", goto_res.get("message"))
        assert False, "URL navigation failed"

    # Get initial ARIA snapshot
    initial_aria_res = get_aria_snapshot()
    if initial_aria_res.get("status") != "success":
        logging.error(
            "Initial ARIA Snapshot retrieval failed: %s", initial_aria_res.get("message")
        )
        assert False, "Initial ARIA Snapshot retrieval failed"

    initial_elements = initial_aria_res.get("aria_snapshot", [])
    logging.info("Initial element count: %d", len(initial_elements))

    def mock_error_client(*args, **kwargs):  
        mock_client = MagicMock()
        mock_client.converse.side_effect = [
            Exception("Test error"),
            MOCK_ERROR_RESPONSE,
        ]
        return mock_client

    # Error case API call test
    with patch("src.bedrock.create_bedrock_client", side_effect=mock_error_client):
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": [{"text": TEST_USER_QUERY}]}
        ]
        system_prompt = TEST_SYSTEM_PROMPT
        model_id = TEST_MODEL_ID
        tool_config = {"tools": [], "toolChoice": {"auto": {}}}

        mock_client = mock_error_client()

        # Confirm error occurs on first API call
        first_error_occurred = False
        try:
            call_bedrock_api(
                mock_client, messages, system_prompt, model_id, tool_config
            )
            logging.error("Error did not occur")
            success = False
        except Exception as e:  
            first_error_occurred = True
            logging.info("Error occurred as expected: %s", e)

            # Verify DOM state after error
            error_aria_res = get_aria_snapshot()
            if error_aria_res.get("status") == "success":
                error_elements = error_aria_res.get("aria_snapshot", [])
                logging.info("Element count after error: %d", len(error_elements))

                # Confirm DOM state hasn't changed due to error
                if len(initial_elements) != len(error_elements):
                    logging.warning(
                        "DOM element count changed before and after error: %d → %d",
                        len(initial_elements),
                        len(error_elements),
                    )

            # Confirm second API call ends normally
            try:
                response = call_bedrock_api(
                    mock_client, messages, system_prompt, model_id, tool_config
                )

                # Detailed response verification
                if not verify_api_response(response):
                    logging.error("Second API response verification failed")
                    success = False

                # Response verification
                if response.get("stopReason") != "end_turn":
                    logging.error(
                        "stopReason is not 'end_turn': %s",
                        response.get("stopReason"),
                    )
                    success = False
                else:
                    stop_analysis = analyze_stop_reason(response.get("stopReason"))
                    if stop_analysis.get("should_continue"):
                        logging.error("stopReason analysis is incorrect")
                        success = False
                    else:
                        # Confirm recovery after error
                        if "response" in locals():
                            try:
                                output = response.get("output", {})
                                message = output.get("message", {})
                                content = message.get("content", [])
                                response_text = (
                                    content[0].get("text")
                                    if content
                                    else "(No text)"
                                )
                                logging.info(
                                    "Recovery response text: %s",
                                    (
                                        response_text[:100] + "..."
                                        if len(response_text) > 100
                                        else response_text
                                    ),
                                )

                                # Verify recovery response is as expected
                                if "error" in response_text.lower():
                                    logging.info(
                                        "Recovery response mentions error"
                                    )
                            except (KeyError, IndexError) as e:
                                logging.warning(
                                    "Error while extracting recovery response text: %s", e
                                )

                        logging.info("Recovery after error successful")
            except Exception as e2:  
                logging.error("Recovery after error failed: %s", e2)
                success = False

    # Confirm error actually occurred
    if not first_error_occurred:
        logging.error("First API call did not generate an error")
        success = False

    if success:
        logging.info("Error case test successful")

    assert success, "Error case test failed"


def test_main_e2e(url=TEST_URL, max_turns=TEST_MAX_TURNS):
    """main.py E2E test - Emulates actual main.py processing for testing"""
    logging.info("=== main.py E2E test start ===")

    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error("Browser initialization failed: %s", init_res.get("message"))
        assert False, "Browser initialization failed"

    goto_res = goto_url(url)
    if goto_res.get("status") != "success":
        logging.error("URL navigation failed: %s", goto_res.get("message"))
        assert False, "URL navigation failed"

    # Get initial ARIA snapshot
    aria_res = get_aria_snapshot()
    if aria_res.get("status") != "success":
        logging.error("ARIA Snapshot retrieval failed: %s", aria_res.get("message"))
        assert False, "ARIA Snapshot retrieval failed"

    initial_elements = aria_res.get("aria_snapshot", [])
    logging.info("Initial element count: %d", len(initial_elements))

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
            logging.info("--- Turn %d start ---", turn_count)

            # Record DOM state at start of turn
            turn_start_aria_res = get_aria_snapshot()
            if turn_start_aria_res.get("status") == "success":
                turn_start_elements = turn_start_aria_res.get("aria_snapshot", [])
                logging.info(
                    "Element count at start of turn %d: %d", turn_count, len(turn_start_elements)
                )

            try:
                mock_client = mock_bedrock_client()

                # Record time before API call
                api_start_time = time.time()

                response = call_bedrock_api(
                    mock_client, messages, system_prompt, model_id, tool_config
                )

                # Record API call duration
                api_duration = time.time() - api_start_time
                logging.info(
                    "API call duration for turn %d: %.2f seconds", turn_count, api_duration
                )

                usage = response.get("usage", {})
                result["token_usage"]["inputTokens"] += usage.get("inputTokens", 0)
                result["token_usage"]["outputTokens"] += usage.get("outputTokens", 0)
                result["token_usage"]["totalTokens"] += usage.get(
                    "inputTokens", 0
                ) + usage.get("outputTokens", 0)

                # Detailed response verification
                if not verify_api_response(response):
                    logging.error(
                        "API response verification failed for turn %d", turn_count
                    )
                    success = False

            except Exception as e:  
                err_msg = str(e)
                logging.error("Bedrock API call error: %s", err_msg)
                result["status"] = "error"
                result["message"] = f"Bedrock API error: {err_msg}"
                success = False
                break

            output = response.get("output", {})
            message = output.get("message", {})
            stop_reason = response.get("stopReason")

            message_content = message.get("content", [])
            messages.append({"role": "assistant", "content": message_content})
            result["messages"].append({"role": "assistant", "content": message_content})

            # Verify response message content
            response_text = message_content[0].get("text") if message_content else ""
            logging.info(
                "Response text for turn %d: %s",
                turn_count,
                (
                    response_text[:100] + "..."
                    if len(response_text) > 100
                    else response_text
                ),
            )

            stop_analysis = analyze_stop_reason(stop_reason)

            # Record DOM state at end of turn and verify changes
            turn_end_aria_res = get_aria_snapshot()
            if turn_end_aria_res.get("status") == "success":
                turn_end_elements = turn_end_aria_res.get("aria_snapshot", [])
                logging.info(
                    "Element count at end of turn %d: %d", turn_count, len(turn_end_elements)
                )

                if len(turn_start_elements) != len(turn_end_elements):
                    logging.info(
                        "DOM element count changed during turn %d: %d → %d",
                        turn_count,
                        len(turn_start_elements),
                        len(turn_end_elements),
                    )

            if not stop_analysis["should_continue"]:
                if stop_analysis["error"]:
                    result["status"] = "error"
                    result["message"] = stop_analysis["message"]
                    success = False
                break

        if result["status"] != "success":
            logging.error(
                "E2E test failed: %s", result.get("message", "Unknown error")
            )
            success = False

        if turn_count >= max_turns:
            logging.error("Reached maximum turn count (%d)", max_turns)
            success = False

        # Verify final state
        final_aria_res = get_aria_snapshot()
        if final_aria_res.get("status") == "success":
            final_elements = final_aria_res.get("aria_snapshot", [])
            logging.info("Final element count: %d", len(final_elements))

            if len(initial_elements) != len(final_elements):
                logging.info(
                    "DOM element count changed over entire test: %d → %d",
                    len(initial_elements),
                    len(final_elements),
                )

        # Check token usage
        logging.info(
            "Token usage: input=%d, output=%d, total=%d",
            result["token_usage"]["inputTokens"],
            result["token_usage"]["outputTokens"],
            result["token_usage"]["totalTokens"],
        )

        if success:
            logging.info("E2E test successful: ended normally after %d turns", turn_count)

    cleanup_browser()

    assert success, "E2E test failed"


def main():
    """Main function - Controls test execution"""
    # Apply test settings
    url = TEST_URL
    timeout = TEST_TIMEOUT

    setup_logging()
    # Always set log level to DEBUG
    logging.getLogger().setLevel(logging.DEBUG)

    logging.info(
        "main.py E2E test start: headless=%s, CI=%s",
        os.environ.get("HEADLESS", "false"),
        os.environ.get("CI", "false"),
    )

    start_time = time.time()

    try:
        # Run test functions and evaluate assertions as needed
        try:
            test_normal_case()  # Don't use return value
            normal_success = True
        except AssertionError:
            normal_success = False

        try:
            test_error_case()  # Don't use return value
            error_success = True
        except AssertionError:
            error_success = False

        try:
            test_main_e2e()  # Don't use return value
            e2e_success = True
        except AssertionError:
            e2e_success = False

        elapsed_time = time.time() - start_time
        logging.info("Test execution time: %.2f seconds", elapsed_time)

        if normal_success and error_success and e2e_success:
            logging.info("All tests passed successfully")
            return 0

        logging.error("Some tests failed")
        return 1
    except Exception as e:  
        logging.error("Error during test execution: %s", e)
        traceback.print_exc()
        return 1
    finally:
        try:
            cleanup_browser()
            logging.info("Browser cleanup completed")
        except Exception as e:  
            logging.error("Error during browser cleanup: %s", e)
            traceback.print_exc()


if __name__ == "__main__":
    EXIT_CODE = main()
    logging.info("Ending test process: exit_code=%s", EXIT_CODE)
    sys.exit(EXIT_CODE)
