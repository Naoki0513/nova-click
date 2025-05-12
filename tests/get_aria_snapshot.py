#!/usr/bin/env python3
"""ARIA Snapshot Test Script

Launches the browser worker, navigates to the specified (or default) URL,
and retrieves the latest ARIA Snapshot, which is output to the console.

Environment variables:
    HEADLESS - If 'true', runs the browser in headless mode
"""
import json
import logging
import os
import sys
import traceback

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.browser import (cleanup_browser, get_aria_snapshot, goto_url,
                         initialize_browser)
from src.utils import setup_logging


# Test parameters (modify these to change test conditions)
TEST_URL = "https://www.google.co.jp/maps/"


def main():
    """
    Main execution function - Runs the ARIA snapshot retrieval test.
    """
    # Apply settings
    url = TEST_URL

    setup_logging()
    # Always set log level to DEBUG
    logging.getLogger().setLevel(logging.DEBUG)

    # Output test parameters
    logging.info(
        "Test parameters: url=%s, headless=%s",
        url,
        os.environ.get("HEADLESS", "false"),
    )

    try:
        # Launch browser
        init_res = initialize_browser()
        if init_res.get("status") != "success":
            logging.error("Browser initialization failed: %s", init_res.get("message"))
            return 1

        # Navigate to URL
        goto_res = goto_url(url)
        if goto_res.get("status") != "success":
            logging.error("URL navigation failed: %s", goto_res.get("message"))
            return 1

        current_url = goto_res.get("current_url", url)
        logging.info("Navigated to page: %s", current_url)

        # Verification: Confirm navigation to correct URL
        if current_url != url and not current_url.startswith(url):
            logging.warning(
                "Destination URL differs from specified URL: specified=%s, actual=%s",
                url,
                current_url,
            )

        # Get ARIA Snapshot
        aria_res = get_aria_snapshot()
        if aria_res.get("status") != "success":
            logging.error("ARIA Snapshot retrieval failed: %s", aria_res.get("message"))
            return 1

        snapshot = aria_res.get("aria_snapshot", [])
        logging.info("Number of elements retrieved: %d", len(snapshot))

        # Verification: Basic validity check of snapshot
        if not snapshot:
            logging.error("ARIA snapshot is empty")
            return 1

        # Verify basic structure of snapshot
        valid_structure = all(isinstance(e, dict) for e in snapshot)
        if not valid_structure:
            logging.error("ARIA snapshot structure is invalid")
            return 1

        # Check for existence of basic elements
        key_roles = ["document", "heading", "link"]
        found_roles = {role: False for role in key_roles}

        for element in snapshot:
            role = element.get("role")
            if role in key_roles:
                found_roles[role] = True
                logging.info(
                    "Basic element found: role=%s, name=%s",
                    role,
                    element.get("name", "(No name)"),
                )

        for role, found in found_roles.items():
            if found:
                logging.info("Basic element '%s' exists", role)
            else:
                logging.warning("Basic element '%s' not found", role)

        # Output results (show details for first 10 elements only)
        logging.info("First 10 elements of the snapshot:")
        for i, elem in enumerate(snapshot[:10]):
            logging.info(
                "Element #%d: ref_id=%s, role=%s, name=%s",
                i + 1,
                elem.get("ref_id"),
                elem.get("role"),
                elem.get("name"),
            )

        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        return 0
    except (RuntimeError, IOError) as e:
        # Specify more concrete exception types
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
