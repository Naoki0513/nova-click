"""
Tool definitions and dispatch module for Bedrock API

Provides tool definitions for LLM and dispatch logic to forward tool calls to browser operation functions.
"""

import logging
from typing import Any

from .browser import click_element as browser_click_element
from .browser import input_text as browser_input_text
from .utils import add_debug_log, log_operation_error

logger = logging.getLogger(__name__)


def get_browser_tools_config() -> list[dict[str, Any]]:
    """Get available browser operation tools configuration"""
    return [
        {
            "toolSpec": {
                "name": "click_element",
                "description": "First identify the element's ref_id (number) from the ARIA Snapshot, then use this tool. "
                "Clicks the element with the specified reference ID. "
                "The latest ARIA Snapshot is automatically included in the result (for both success and failure).",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "ref_id": {
                                "type": "integer",
                                "description": "Reference ID of the element to click (number, check in ARIA Snapshot)",
                            }
                        },
                        "required": ["ref_id"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "input_text",
                "description": "First identify the element's ref_id (number) from the ARIA Snapshot, then use this tool. "
                "Inputs text into the element with the specified reference ID and presses Enter. "
                "The latest ARIA Snapshot is automatically included in the result (for both success and failure).",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "Text to input",
                            },
                            "ref_id": {
                                "type": "integer",
                                "description": "Reference ID of the element to input text (number, check in ARIA Snapshot)",
                            },
                        },
                        "required": ["text", "ref_id"],
                    }
                },
            }
        },
    ]


def dispatch_browser_tool(tool_name: str, params: dict | None = None) -> dict[str, Any]:
    """Execute tool called by LLM

    Args:
        tool_name: Tool name ("click_element" or "input_text")
        params: Tool parameters (ref_id, text, etc.)

    Returns:
        Dictionary with tool execution result (status, message, aria_snapshot)
    """
    add_debug_log(f"tools.dispatch_browser_tool: tool={tool_name}, params={params}")
    result = None

    if tool_name == "click_element":
        if params is None or "ref_id" not in params:
            error_msg = "Parameter ref_id is not specified"
            log_operation_error(tool_name, error_msg, params)
            result = {
                "status": "error",
                "message": error_msg,
            }
        else:
            result = browser_click_element(params.get("ref_id"))
    elif tool_name == "input_text":
        if params is None or "ref_id" not in params or "text" not in params:
            error_msg = "Parameter text or ref_id is not specified"
            log_operation_error(tool_name, error_msg, params)
            result = {
                "status": "error",
                "message": error_msg,
            }
        else:
            result = browser_input_text(params.get("text"), params.get("ref_id"))
    else:
        error_msg = f"Unknown tool: {tool_name}"
        add_debug_log(f"tools.dispatch_browser_tool: {error_msg}")
        log_operation_error("unknown_tool", error_msg, params)
        result = {"status": "error", "message": error_msg}

    return result


__all__: list[str] = [
    "get_browser_tools_config",
    "dispatch_browser_tool",
]
