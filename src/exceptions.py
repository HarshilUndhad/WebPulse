"""
exceptions.py — WebPulse Domain-Specific Exceptions

Defines a hierarchy of custom exceptions so that every failure mode
in the pipeline can be caught, logged, and handled gracefully rather
than surfacing raw stack-traces to the end user.
"""


class WebPulseError(Exception):
    pass

class NavigationError(WebPulseError):
   #Raised when the HTTP request to a target URL fails.

    def __init__(self, url: str, reason: str, status_code: int | None = None):
        self.url = url
        self.reason = reason
        self.status_code = status_code
        detail = f"[HTTP {status_code}] " if status_code else ""
        super().__init__(f"Navigation failed for {url} — {detail}{reason}")


class ContentExtractionError(WebPulseError):
    #Raised when the HTML document contains no extractable content.

    def __init__(self, url: str, reason: str = "No meaningful content found"):
        self.url = url
        self.reason = reason
        super().__init__(f"Content extraction failed for {url} — {reason}")


class AuditSynthesisError(WebPulseError):
    #Raised when both the LLM and heuristic fallback fail to produce

    def __init__(self, reason: str = "Unable to synthesize a business profile"):
        self.reason = reason
        super().__init__(f"Audit synthesis failed — {reason}")
