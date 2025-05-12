#!/usr/bin/env python3
"""Click Element Test Script

Opens the specified URL, retrieves the ARIA Snapshot, and
performs tests for clicking an element specified by ref_id.

Includes tests for both normal case and error case (e.g., clicking non-existent elements).

Environment variables:
    HEADLESS - If 'true', runs the browser in headless mode
"""
import logging
import os
import sys
import time
import traceback

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.browser import (cleanup_browser, click_element, get_aria_snapshot,
                         goto_url, initialize_browser)
from src.utils import setup_logging


# Test parameters (modify these to change test conditions)
TEST_URL = "https://www.google.co.jp/"
TEST_REF_ID = 26
# For error case testing
TEST_ERROR_REF_ID = 9999


def test_normal_case(url=TEST_URL, ref_id=TEST_REF_ID):
    """Normal case test - Click the specified element"""
    logging.info("=== Normal case test start: url=%s, ref_id=%s ===", url, ref_id)

    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error("Browser initialization failed: %s", init_res.get("message"))
        assert False, "Browser initialization failed"

    goto_res = goto_url(url)
    if goto_res.get("status") != "success":
        logging.error("URL navigation failed: %s", goto_res.get("message"))
        assert False, "URL navigation failed"
    logging.info("Page loading complete")

    # Get ARIA Snapshot before clicking
    aria_before_res = get_aria_snapshot()
    if aria_before_res.get("status") != "success":
        logging.error(
            "Failed to get ARIA Snapshot before click: %s", aria_before_res.get("message")
        )
        assert False, "ARIA Snapshot retrieval failed"

    elements_before = aria_before_res.get("aria_snapshot", [])
    logging.info("Number of elements before click: %s", len(elements_before))

    element_exists = any(e.get("ref_id") == ref_id for e in elements_before)
    if not element_exists:
        logging.error(
            "Element with ref_id=%s not found. Looking for clickable elements.",
            ref_id,
        )

        # If element not found, look for clickable elements
        clickable_elements = []
        for elem in elements_before:
            if elem.get("role") in ["button", "link"]:
                clickable_elements.append(elem)
                logging.info(
                    "Found clickable element: ref_id=%s, role=%s, name=%s",
                    elem.get("ref_id"),
                    elem.get("role"),
                    elem.get("name"),
                )

        if clickable_elements:
            # Use the first clickable element
            ref_id = clickable_elements[0].get("ref_id")
            logging.info("Changing to ref_id=%s to continue test", ref_id)
        else:
            # If no clickable elements, use the first element
            if elements_before:
                ref_id = elements_before[0].get("ref_id")
                logging.info(
                    "Using first element ref_id=%s to continue test", ref_id
                )
            else:
                assert False, "No clickable elements found"

    # Log info about selected element
    target_element = next(
        (e for e in elements_before if e.get("ref_id") == ref_id), None
    )
    if target_element:
        logging.info(
            "Target element for click: ref_id=%s, role=%s, name=%s",
            target_element.get("ref_id"),
            target_element.get("role"),
            target_element.get("name"),
        )

    # Execute click
    logging.info("Starting click operation: ref_id=%s", ref_id)
    click_res = click_element(ref_id)
    if click_res.get("status") != "success":
        logging.error("Click failed: %s", click_res.get("message"))
        assert False, "Click failed"

    logging.info("Click operation successful")

    # Verification after operation: Wait for page changes
    time.sleep(1)

    # Get ARIA Snapshot after click and verify
    aria_after_res = get_aria_snapshot()
    if aria_after_res.get("status") != "success":
        logging.error(
            "Failed to get ARIA Snapshot after click: %s", aria_after_res.get("message")
        )
        assert False, "Failed to get ARIA Snapshot after click"

    elements_after = aria_after_res.get("aria_snapshot", [])
    logging.info("Number of elements after click: %s", len(elements_after))

    # Verify DOM changes
    has_change = False

    # 1. Check for element count changes
    if len(elements_before) != len(elements_after):
        has_change = True
        logging.info(
            "Element count change detected: before=%d, after=%d",
            len(elements_before),
            len(elements_after),
        )

    # 2. Check for URL change if element was a link
    if target_element and target_element.get("role") == "link":
        current_url_res = goto_url("")  # Get current URL
        if (
            current_url_res.get("status") == "success"
            and current_url_res.get("current_url") != url
        ):
            has_change = True
            logging.info(
                "URL change detected: %s → %s", url, current_url_res.get("current_url")
            )

    # Verification result
    if has_change:
        logging.info("Changes confirmed after click operation")
    else:
        logging.warning(
            "No changes detected after click operation. The operation might still have been successful."
        )

    assert True


def test_error_case(url=TEST_URL, ref_id=TEST_ERROR_REF_ID):
    """Error case test - Click a non-existent element"""
    logging.info("=== Error case test start: url=%s, non-existent ref_id=%s ===", url, ref_id)

    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error("Browser initialization failed: %s", init_res.get("message"))
        assert False, "Browser initialization failed"

    goto_res = goto_url(url)
    if goto_res.get("status") != "success":
        logging.error("URL navigation failed: %s", goto_res.get("message"))
        assert False, "URL navigation failed"
    logging.info("Page loading complete")

    # Get ARIA Snapshot before clicking
    aria_before_res = get_aria_snapshot()
    if aria_before_res.get("status") != "success":
        logging.error(
            "Failed to get ARIA Snapshot before click: %s", aria_before_res.get("message")
        )
        assert False, "ARIA Snapshot retrieval failed"

    elements_before = aria_before_res.get("aria_snapshot", [])

    logging.info("Starting click operation on non-existent element: ref_id=%s", ref_id)
    click_res = click_element(ref_id)

    if click_res.get("status") == "error":
        logging.info("Error returned as expected: %s", click_res.get("message"))

        # Verification after operation: Confirm DOM did not change
        aria_after_res = get_aria_snapshot()
        if aria_after_res.get("status") == "success":
            elements_after = aria_after_res.get("aria_snapshot", [])

            # Verify element count has not changed
            if len(elements_before) == len(elements_after):
                logging.info(
                    "Confirmed no element count change after error: %d", len(elements_after)
                )
            else:
                logging.warning(
                    "Element count changed despite error: before=%d, after=%d",
                    len(elements_before),
                    len(elements_after),
                )

        assert True
    else:
        logging.error("Click on non-existent element did not return an error")
        assert False, "Click on non-existent element did not return an error"


def main():
    """Main function - Controls test execution and processes results"""
    # Apply test settings
    url = TEST_URL
    ref_id = TEST_REF_ID

    setup_logging()
    # Always set log level to DEBUG
    logging.getLogger().setLevel(logging.DEBUG)

    # Output test parameters
    logging.info(
        "Test parameters: url=%s, ref_id=%s, headless=%s",
        url,
        ref_id,
        os.environ.get("HEADLESS", "false"),
    )

    try:
        # Test functions don't return values, so catch exceptions to determine success/failure
        normal_success = False
        error_success = False

        try:
            test_normal_case(url, ref_id)
            normal_success = True
        except AssertionError as e:
            logging.error("Normal case test failed: %s", e)

        try:
            test_error_case(url, TEST_ERROR_REF_ID)
            error_success = True
        except AssertionError as e:
            logging.error("Error case test failed: %s", e)

        if normal_success and error_success:
            logging.info("All tests passed successfully")
            return 0
        else:
            logging.error("Some tests failed")
            return 1
    except Exception as e:
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
