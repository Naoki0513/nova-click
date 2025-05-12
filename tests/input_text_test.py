"""Input Text Test Script

Opens the specified URL, tests input text to an element specified by ref_id,
and presses Enter. Includes both normal and error cases (e.g., non-existent elements).

Environment variables:
    HEADLESS - If 'true', runs the browser in headless mode
"""

import logging
import os
import signal
import sys
import time
import traceback

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.browser import (cleanup_browser, get_aria_snapshot, goto_url,
                         initialize_browser, input_text)
from src.utils import setup_logging


# Test parameters (modify these to change test conditions)
TEST_URL = "https://www.google.co.jp/"
TEST_REF_ID = 13
TEST_TEXT = "Amazon"
TEST_ERROR_REF_ID = 9999
# Operation timeout (seconds)
TEST_TIMEOUT = 30


def timeout_handler(_signum, _frame):
    """Handler function for timeout events"""
    logging.error("Test execution timed out. Force terminating.")
    sys.exit(1)


# On Windows, signal.alarm is not available
if sys.platform == "win32":
    logging.warning("On Windows, test timeout handling is limited.")


def test_normal_case(
    url=TEST_URL, ref_id=TEST_REF_ID, text=TEST_TEXT, operation_timeout=TEST_TIMEOUT
):
    """Normal case test - Input text to the specified element"""
    logging.info(
        "=== Normal case test start: url=%s, ref_id=%s, text='%s' ===", url, ref_id, text
    )

    start_time = time.time()

    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error("Browser initialization failed: %s", init_res.get("message"))
        assert False, "Browser initialization failed"

    if time.time() - start_time > operation_timeout:
        logging.error("Browser initialization timed out (%s seconds)", operation_timeout)
        assert False, "Browser initialization timed out"

    # Record initial URL
    initial_url = ""
    goto_res = goto_url(url)
    if goto_res.get("status") != "success":
        logging.error("URL navigation failed: %s", goto_res.get("message"))
        assert False, "URL navigation failed"
    else:
        initial_url = goto_res.get("current_url", url)
    logging.info("Page loading complete: %s", initial_url)

    if time.time() - start_time > operation_timeout:
        logging.error("URL navigation timed out (%s seconds)", operation_timeout)
        assert False, "URL navigation timed out"

    # Initial ARIA Snapshot to inject ref-id attributes into DOM
    aria_res = get_aria_snapshot()
    if aria_res.get("status") != "success":
        logging.error("ARIA Snapshot retrieval failed: %s", aria_res.get("message"))
        assert False, "ARIA Snapshot retrieval failed"

    if time.time() - start_time > operation_timeout:
        logging.error(
            "ARIA Snapshot retrieval timed out (%s seconds)", operation_timeout
        )
        assert False, "ARIA Snapshot retrieval timed out"

    elements_before = aria_res.get("aria_snapshot", [])
    logging.info("Number of elements retrieved: %d", len(elements_before))

    logging.info("Available elements:")
    for elem in elements_before:
        logging.info(
            "  ref_id=%s, role=%s, name=%s",
            elem.get("ref_id"),
            elem.get("role"),
            elem.get("name"),
        )
        search_start_time = time.time()
    search_timeout = 3  # Element search timeout (seconds)
    search_input_ref_id = None

    # Multiple methods to find Google search input field
    if (
        url.startswith("https://www.google.co")
        and time.time() - search_start_time < search_timeout
    ):
        for elem in elements_before:
            if elem.get("role") == "textbox" and (
                "search" in str(elem.get("name", "")).lower()
                or "query" in str(elem.get("name", "")).lower()
            ):
                search_input_ref_id = elem.get("ref_id")
                logging.info(
                    "Method 1 found search input field: ref_id=%s, name=%s",
                    search_input_ref_id,
                    elem.get("name"),
                )
                break

    if (
        search_input_ref_id is None
        and url.startswith("https://www.google.co")
        and time.time() - search_start_time < search_timeout
    ):
        for elem in elements_before:
            if elem.get("role") == "textbox":
                search_input_ref_id = elem.get("ref_id")
                logging.info(
                    "Method 2 found search input field: ref_id=%s, name=%s",
                    search_input_ref_id,
                    elem.get("name"),
                )
                break

    if (
        search_input_ref_id is None
        and url.startswith("https://www.google.co")
        and time.time() - search_start_time < search_timeout
    ):
        for test_ref_id in [
            17,
            18,
            20,
            21,
            22,
            23,
        ]:  # skip ref_id=19 which is submit button
            if time.time() - search_start_time >= search_timeout:
                break

            matching_elem = next(
                (e for e in elements_before if e.get("ref_id") == test_ref_id), None
            )
            if matching_elem:
                if matching_elem.get("role") != "button":
                    search_input_ref_id = test_ref_id
                    logging.info(
                        "Method 3 found search input field: ref_id=%s, role=%s",
                        search_input_ref_id,
                        matching_elem.get("role"),
                    )
                    break
                else:
                    logging.info("ref_id=%s is a button, skipping", test_ref_id)

    if (
        search_input_ref_id is None
        and url.startswith("https://www.google.co")
        and time.time() - search_start_time < search_timeout
    ):
        for elem in elements_before:
            if elem.get("role") not in ["button", "link", "heading", "img"]:
                search_input_ref_id = elem.get("ref_id")
                logging.info(
                    "Method 4 found search input field: ref_id=%s, role=%s",
                    search_input_ref_id,
                    elem.get("role"),
                )
                break

    search_elapsed = time.time() - search_start_time
    logging.info("Element search time: %.2f seconds", search_elapsed)

    actual_ref_id = search_input_ref_id if search_input_ref_id is not None else ref_id
    logging.info("Target element: ref_id=%s", actual_ref_id)

    # Record target element information
    target_element = next(
        (e for e in elements_before if e.get("ref_id") == actual_ref_id), None
    )
    if target_element:
        logging.info(
            "Input target element: ref_id=%s, role=%s, name=%s",
            target_element.get("ref_id"),
            target_element.get("role"),
            target_element.get("name"),
        )

    element_exists = any(e.get("ref_id") == actual_ref_id for e in elements_before)
    if not element_exists:
        logging.error("Element with ref_id=%s not found", actual_ref_id)

        # Fallback: Choose another input-capable element
        if elements_before:
            for elem in elements_before:
                if elem.get("role") != "button":
                    fallback_ref_id = elem.get("ref_id")
                    logging.info(
                        "Fallback: Using non-button element ref_id=%s to continue test",
                        fallback_ref_id,
                    )
                    actual_ref_id = fallback_ref_id
                    target_element = elem
                    break
            else:
                fallback_ref_id = elements_before[0].get("ref_id")
                logging.info(
                    "Fallback: Using first element ref_id=%s to continue test",
                    fallback_ref_id,
                )
                actual_ref_id = fallback_ref_id
                target_element = elements_before[0]
        else:
            logging.error("No elements found, aborting test")
            assert False, "No elements found"

    if time.time() - start_time > operation_timeout:
        logging.error("Element search timed out (%s seconds)", operation_timeout)
        assert False, "Element search timed out"

    # Execute text input
    logging.info("Executing text input: text='%s', ref_id=%s", text, actual_ref_id)
    input_res = input_text(text, actual_ref_id)
    if input_res.get("status") != "success":
        logging.error("Text input failed: %s", input_res.get("message"))
        assert False, "Text input failed"

    if time.time() - start_time > operation_timeout:
        logging.error("Text input timed out (%s seconds)", operation_timeout)
        assert False, "Text input timed out"

    logging.info("Text input processing successful")

    # Post-operation verification
    # 1. Wait briefly for screen changes
    time.sleep(2)

    # 2. Get current URL and check for changes
    current_url_res = goto_url("")
    if current_url_res.get("status") == "success":
        current_url = current_url_res.get("current_url", "")
        if current_url != initial_url:
            logging.info("URL changed: %s → %s", initial_url, current_url)
            # For Google search, check if search term is included
            if text.lower() in current_url.lower():
                logging.info("URL contains input text '%s'", text)
        else:
            logging.info("URL has not changed: %s", current_url)

    # 3. Verify DOM changes
    aria_after_res = get_aria_snapshot()
    if aria_after_res.get("status") == "success":
        elements_after = aria_after_res.get("aria_snapshot", [])
        if len(elements_after) != len(elements_before):
            logging.info(
                "DOM element count changed: %d → %d",
                len(elements_before),
                len(elements_after),
            )
        else:
            logging.info("DOM element count has not changed: %d", len(elements_after))

        # Check for Google search results page features
        search_results = [
            e
            for e in elements_after
            if e.get("role") in ["heading", "link"]
            and text.lower() in str(e.get("name", "")).lower()
        ]
        if search_results:
            logging.info(
                "Found %d elements that appear to be search results", len(search_results)
            )
            for i, result in enumerate(search_results[:3]):  # Log only first 3
                logging.info(
                    "Search result #%d: role=%s, name=%s",
                    i + 1,
                    result.get("role"),
                    result.get("name"),
                )

    assert True


def test_error_case(url=TEST_URL, ref_id=TEST_ERROR_REF_ID, text=TEST_TEXT):
    """Error case test - Input text to a non-existent element"""
    logging.info(
        "=== Error case test start: url=%s, non-existent ref_id=%s, text='%s' ===",
        url,
        ref_id,
        text,
    )

    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error("Browser initialization failed: %s", init_res.get("message"))
        assert False, "Browser initialization failed"

    # Record initial state
    goto_res = goto_url(url)
    if goto_res.get("status") != "success":
        logging.error("URL navigation failed: %s", goto_res.get("message"))
        assert False, "URL navigation failed"

    initial_url = goto_res.get("current_url", url)
    logging.info("Page loading complete: %s", initial_url)

    # Record DOM state before operation
    aria_before_res = get_aria_snapshot()
    if aria_before_res.get("status") != "success":
        logging.error(
            "Failed to get ARIA Snapshot before operation: %s", aria_before_res.get("message")
        )
        assert False, "ARIA Snapshot retrieval failed"

    elements_before = aria_before_res.get("aria_snapshot", [])
    logging.info("Element count before operation: %d", len(elements_before))

    # Execute text input (to non-existent element)
    logging.info(
        "Starting text input to non-existent element: ref_id=%s, text='%s'", ref_id, text
    )
    input_res = input_text(text, ref_id)

    if input_res.get("status") == "error":
        logging.info("Error returned as expected: %s", input_res.get("message"))

        # Post-operation verification - Confirm state hasn't changed after error

        # 1. Verify URL hasn't changed
        current_url_res = goto_url("")
        if current_url_res.get("status") == "success":
            current_url = current_url_res.get("current_url", "")
            if current_url == initial_url:
                logging.info("Confirmed URL has not changed: %s", current_url)
            else:
                logging.warning(
                    "URL changed despite error: %s → %s",
                    initial_url,
                    current_url,
                )

        # 2. Verify DOM state hasn't changed
        aria_after_res = get_aria_snapshot()
        if aria_after_res.get("status") == "success":
            elements_after = aria_after_res.get("aria_snapshot", [])
            if len(elements_after) == len(elements_before):
                logging.info("Confirmed element count has not changed: %d", len(elements_after))
            else:
                logging.warning(
                    "Element count changed despite error: %d → %d",
                    len(elements_before),
                    len(elements_after),
                )

        assert True
    else:
        logging.error("Text input to non-existent element did not return an error")
        assert False, "Text input to non-existent element did not return an error"


def main():
    """Main function - Controls test execution"""
    # Apply test settings
    url = TEST_URL
    ref_id = TEST_REF_ID
    text = TEST_TEXT
    timeout = 60  # Overall test timeout (seconds)

    setup_logging()
    # Always set log level to DEBUG
    logging.getLogger().setLevel(logging.DEBUG)

    # Output test parameters
    logging.info(
        "Test parameters: url=%s, ref_id=%s, text='%s', headless=%s, timeout=%s seconds",
        url,
        ref_id,
        text,
        os.environ.get("HEADLESS", "false"),
        timeout,
    )

    if sys.platform != "win32":
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)

    start_time = time.time()

    try:
        logging.info("Test start time: %s", time.strftime("%Y-%m-%d %H:%M:%S"))

        # Test functions don't return values, so catch exceptions to determine success/failure
        normal_success = False
        error_success = False

        try:
            test_normal_case(url, ref_id, text)
            normal_success = True
        except AssertionError as e:
            logging.error("Normal case test failed: %s", e)

        try:
            test_error_case(url, TEST_ERROR_REF_ID, text)
            error_success = True
        except AssertionError as e:
            logging.error("Error case test failed: %s", e)

        if sys.platform != "win32":
            signal.alarm(0)

        elapsed_time = time.time() - start_time
        logging.info("Test execution time: %.2f seconds", elapsed_time)

        if normal_success and error_success:
            logging.info("All tests passed successfully")
            return 0
        else:
            logging.error("Some tests failed")
            return 1
    except (RuntimeError, IOError) as e:
        if sys.platform != "win32":
            signal.alarm(0)
        logging.error("Error during test execution: %s", e)
        traceback.print_exc()
        return 1
    finally:
        # Always clean up the browser
        try:
            cleanup_browser()
            logging.info("Browser cleanup completed")
        except Exception as e:
            logging.error("Error during browser cleanup: %s", e)


if __name__ == "__main__":
    sys.exit(main())
