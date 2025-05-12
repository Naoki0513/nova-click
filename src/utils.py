"""
Utility module.

This module provides logging configuration and utility functions for debugging.
Main features include application-wide logging configuration, credentials loading,
and debug log recording.
"""

import datetime
import inspect
import json
import logging
import os
import sys
import traceback
from typing import Any, Union

import main as constants

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """
    Configure application-wide logging.
    Sets the log level according to LOG_LEVEL in main.py.
    """
    root_logger = logging.getLogger()

    # Remove all existing handlers (to prevent duplicate configuration)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Configure log level
    is_ci = os.environ.get("CI", "false").lower() == "true"
    log_level_name = constants.LOG_LEVEL if hasattr(constants, "LOG_LEVEL") else "INFO"
    log_level = getattr(logging, log_level_name, logging.INFO)

    # Always use INFO level or higher in CI environment
    if is_ci and log_level > logging.INFO:
        log_level = logging.INFO

    root_logger.setLevel(log_level)

    # Create and configure console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Configure formatter
    if is_ci:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
    console_handler.setFormatter(formatter)

    # Add handler to root logger
    root_logger.addHandler(console_handler)

    # Log configuration completion
    root_logger.info("Log level set to %s", logging.getLevelName(log_level))


def load_credentials(file_path: str) -> dict[str, str] | None:
    """Load credentials from a JSON file."""
    try:
        # Use absolute path if provided
        if os.path.isabs(file_path):
            full_path = file_path
        else:
            # For relative paths, treat as relative to project root
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            full_path = os.path.join(project_root, file_path)

        logger.info("Loading credentials from: %s", full_path)
        with open(full_path, "r", encoding="utf-8") as f:
            credentials = json.load(f)
            logger.info("Credentials loaded successfully")
            return credentials
    except FileNotFoundError as e:
        error_msg = f"Credentials file not found: {e}"
        logger.error(error_msg)
        return None
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON format in credentials file: {e}"
        logger.error(error_msg)
        return None
    except IOError as e:
        error_msg = f"Error reading credentials file: {e}"
        logger.error(error_msg)
        return None


def add_debug_log(
    msg: Union[str, dict, list, Exception],
    group: str | None = None,
    level: str = "DEBUG",
) -> None:
    """
    Record a debug log message using the standard logger.

    Args:
        msg: Log message (string, dict, list, or exception)
        group: Log group name (uses caller function name if not specified)
        level: Log level ("DEBUG", "INFO", "WARNING", "ERROR")
    """

    # Get caller function name
    if group is None:
        try:
            frame = inspect.currentframe()
            if frame and frame.f_back:
                function_name = frame.f_back.f_code.co_name
                group = function_name
            else:
                group = "Unknown"
        except (AttributeError, ValueError):
            group = "Unknown"
        finally:
            del frame

    # Format message
    log_entry_message_for_logger = None

    if isinstance(msg, (dict, list)):
        try:
            log_entry_message_for_logger = json.dumps(msg, ensure_ascii=False, indent=2)
        except TypeError:
            log_entry_message_for_logger = str(msg)
    elif isinstance(msg, Exception):
        log_entry_message_for_logger = f"Error: {str(msg)}\n{traceback.format_exc()}"
    else:
        log_entry_message_for_logger = str(msg)

    # Output to standard logger
    log_output = f"[{group}] {log_entry_message_for_logger}"

    log_level_int = getattr(logging, level.upper(), logging.DEBUG)

    if log_level_int == logging.DEBUG:
        logger.debug(log_output)
    elif log_level_int == logging.INFO:
        logger.info(log_output)
    elif log_level_int == logging.WARNING:
        logger.warning(log_output)
    elif log_level_int == logging.ERROR:
        logger.error(log_output)
    else:
        logger.log(log_level_int, log_output)


def log_operation_error(
    operation_type: str,
    error_msg: str,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Log browser operation errors. Always logs at INFO level or higher regardless of log level.

    Args:
        operation_type: Type of operation ("click_element", "input_text", etc.)
        error_msg: Error message
        details: Error details (ref_id, URL, etc.)
    """
    # Format detail information
    details_str = ""
    if details:
        try:
            details_list = [f"{k}={v}" for k, v in details.items()]
            details_str = f" ({', '.join(details_list)})"
        except (TypeError, ValueError):
            details_str = f" ({details})"

    # Log error message at INFO level
    logger.info("Operation error - %s: %s%s", operation_type, error_msg, details_str)


def log_json_debug(
    name: str, data: dict[Any, Any] | list[Any], level: str = "DEBUG"
) -> None:
    """
    Log JSON data and save it to a file.

    Args:
        name: Log group name
        data: JSON-serializable dict or list
        level: Log level string ("DEBUG", "INFO", etc.)
    """
    log_level = getattr(logging, level.upper(), logging.DEBUG)
    # Output and save to file if the specified level is enabled
    if logger.isEnabledFor(log_level):
        try:
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
        except (TypeError, ValueError) as e:
            logger.log(log_level, "[%s] JSON serialization error: %s", name, e)
            return
        # Console output
        logger.log(log_level, "[%s] JSON Data:\n%s", name, json_str)
        # File output: save formatted JSON to log/YYYY-MM-DD_HH-MM-SS.json
        try:
            # Create log directory in project root
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            log_dir = os.path.join(project_root, "log")
            os.makedirs(log_dir, exist_ok=True)
            # Timestamped filename
            now = datetime.datetime.now()
            file_name = now.strftime("%Y-%m-%d_%H-%M-%S") + ".json"
            file_path = os.path.join(log_dir, file_name)
            # Write as formatted JSON file
            record = {
                "timestamp": now.isoformat(),
                "group": name,
                "level": level.upper(),
                "data": data,
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
        except (IOError, OSError) as e:
            logger.error("[%s] Failed to write log file: %s", name, e)
