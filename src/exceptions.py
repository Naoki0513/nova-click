"""exceptions

Common exception classes used in the browser automation agent.

Defines a common base exception `BrowserAgentError` and
subclasses for specific functional areas to maintain
consistency in exception handling.
"""

from __future__ import annotations


class BrowserAgentError(Exception):
    """Base exception for the entire library."""


class BedrockAPIError(BrowserAgentError):
    """Exception related to Bedrock API calls."""


class BrowserWorkerError(BrowserAgentError):
    """Exception related to browser worker thread."""
