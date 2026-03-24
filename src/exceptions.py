"""
exceptions.py — WebPulse Domain-Specific Exceptions

Defines a hierarchy of custom exceptions so that every failure mode
in the pipeline can be caught, logged, and handled gracefully rather
than surfacing raw stack-traces to the end user.
"""


class WebPulseError(Exception):
    """Base exception for all WebPulse operations."""


class NavigationError(WebPulseError):
    """Raised when the HTTP request to a target URL fails.

    Common triggers: HTTP 403 / 404, connection timeout, DNS resolution
    failure, or SSL certificate errors.
    """

    def __init__(self, url: str, reason: str, status_code: int | None = None):
        self.url = url
        self.reason = reason
        self.status_code = status_code
        detail = f"[HTTP {status_code}] " if status_code else ""
        super().__init__(f"Navigation failed for {url} — {detail}{reason}")


class ContentExtractionError(WebPulseError):
    """Raised when the HTML document contains no extractable content.

    This typically occurs on empty pages, login walls, or heavily
    JavaScript-rendered single-page applications.
    """

    def __init__(self, url: str, reason: str = "No meaningful content found"):
        self.url = url
        self.reason = reason
        super().__init__(f"Content extraction failed for {url} — {reason}")


class AuditSynthesisError(WebPulseError):
    """Raised when both the LLM and heuristic fallback fail to produce
    a valid business summary.

    This is the last-resort error — it means the pipeline genuinely
    cannot generate any output for the given content.
    """

    def __init__(self, reason: str = "Unable to synthesize a business profile"):
        self.reason = reason
        super().__init__(f"Audit synthesis failed — {reason}")
