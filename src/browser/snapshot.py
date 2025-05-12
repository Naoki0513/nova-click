"""browser.snapshot

A module that contains utility functions for retrieving ARIA Snapshots
using the Playwright ``page`` object. By centralizing JavaScript/Evaluate
operations in one place, it makes them easier to reuse outside of the
browser worker thread.
"""

from __future__ import annotations

from typing import Any, Dict, List

import main as constants

from ..utils import add_debug_log

__all__ = [
    "take_aria_snapshot",
    "get_snapshot_with_stats",
]

_JS_GET_SNAPSHOT = r"""() => {
    const snapshotResult = [];
    let refIdCounter = 1;
    let errorCount = 0; // Error counter

    try {
        // Get interactive elements in the document
        const interactiveElements = document.querySelectorAll(
            'button, a, input, select, textarea, ' +
            '[role="button"], [role="link"], [role="checkbox"], [role="radio"], ' +
            '[role="tab"], [role="combobox"], [role="textbox"], [role="searchbox"]'
        );

        interactiveElements.forEach(element => {
            try {
                // Determine role
                let role = element.getAttribute('role');
                if (!role) {
                    switch (element.tagName.toLowerCase()) {
                        case 'button': role = 'button'; break;
                        case 'a': role = 'link'; break;
                        case 'input':
                            switch (element.type) {
                                case 'text': role = 'textbox'; break;
                                case 'checkbox': role = 'checkbox'; break;
                                case 'radio': role = 'radio'; break;
                                case 'search': role = 'searchbox'; break;
                                default: role = element.type; break;
                            }
                            break;
                        case 'select': role = 'combobox'; break;
                        case 'textarea': role = 'textbox'; break;
                        default: role = 'unknown'; break;
                    }
                }

                // Get element name (name/label)
                let name = '';
                if (element.hasAttribute('aria-label')) {
                    name = element.getAttribute('aria-label');
                } else if (element.hasAttribute('aria-labelledby')) {
                    const labelledById = element.getAttribute('aria-labelledby');
                    const labelEl = document.getElementById(labelledById);
                    if (labelEl) {
                        name = labelEl.textContent.trim();
                    }
                } else if (element.hasAttribute('placeholder')) {
                    name = element.getAttribute('placeholder');
                } else if (element.hasAttribute('name')) {
                    name = element.getAttribute('name');
                } else if (element.hasAttribute('title')) {
                    name = element.getAttribute('title');
                } else if (element.hasAttribute('alt')) {
                    name = element.getAttribute('alt');
                } else {
                    name = (element.textContent || '').trim();
                    if (element.tagName.toLowerCase() === 'input' && element.id) {
                        const labels = document.querySelectorAll(`label[for="${element.id}"]`);
                        if (labels.length > 0) {
                            name = labels[0].textContent.trim();
                        }
                    }
                }

                // Add ref-id
                const refIdValue = refIdCounter++;
                element.setAttribute('data-ref-id', `ref-${refIdValue}`);

                // Visibility check
                const rect = element.getBoundingClientRect();
                const isVisible = rect.width > 0 && rect.height > 0 &&
                                  window.getComputedStyle(element).visibility !== 'hidden' &&
                                  window.getComputedStyle(element).display !== 'none';

                const isDisabled = element.disabled === true || element.hasAttribute('disabled');
                const isReadOnly = element.readOnly === true || element.hasAttribute('readonly');

                if (!isDisabled && !isReadOnly && isVisible && role !== 'unknown') {
                    snapshotResult.push({
                        role: role,
                        name: name || 'Unnamed Element',
                        ref_id: refIdValue
                    });
                }
            } catch (elError) {
                console.error('Error processing element:', element, elError);
                errorCount++;
            }
        });
    } catch (mainError) {
        console.error('Snapshot process error:', mainError);
        return { error: `Snapshot process error: ${mainError.message}`, errorCount: errorCount, snapshot: snapshotResult };
    }

    return { snapshot: snapshotResult, errorCount: errorCount };
}"""


async def get_snapshot_with_stats(page: Any) -> Dict[str, Any]:
    """Retrieves a snapshot from Playwright ``page`` and returns it with statistics."""

    add_debug_log(
        "snapshot.get_snapshot_with_stats: Retrieving snapshot using JavaScript"
    )
    result = await page.evaluate(_JS_GET_SNAPSHOT)

    # Check expected type
    if not isinstance(result, dict):
        add_debug_log(
            "snapshot.get_snapshot_with_stats: Unexpected type returned from JS",
            level="WARNING",
        )
        return {"snapshot": [], "errorCount": 1, "error": "Unexpected return from JS"}

    return result  # type: ignore[return-value]


async def take_aria_snapshot(page: Any) -> List[Dict[str, Any]]:
    """Retrieves only a flat list of elements (snapshot) from the ``page``."""

    data = await get_snapshot_with_stats(page)
    snapshot_list = data.get("snapshot", [])

    # Filter by ALLOWED_ROLES
    filtered = [e for e in snapshot_list if e.get("role") in constants.ALLOWED_ROLES]

    add_debug_log(f"snapshot.take_aria_snapshot: Retrieved {len(filtered)} elements")
    return filtered
