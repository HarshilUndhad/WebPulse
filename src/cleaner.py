"""
cleaner.py — The Refiner

Separates *signal* (meaningful content) from *noise* (navigation bars,
cookie banners, footers, social widgets, ads) in raw HTML documents.

Pipeline:
    1. ``strip_digital_clutter``  → remove noisy DOM elements entirely.
    2. ``extract_content_signals`` → pull out title, headings, and body text.
    3. ``distill_readable_text``  → normalise whitespace and strip leftover
       HTML entities so the text is ready for the LLM.
"""

from __future__ import annotations

import re
import unicodedata
from html import unescape
from typing import Optional

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from src.logger import pulse_logger

# ── Constants ───────────────────────────────────────────────────────────

# Tags that never carry primary content
_NOISY_TAGS = {
    "script", "style", "noscript", "iframe",
    "nav", "footer", "header",
    "aside", "form", "button",
    "svg", "canvas", "video", "audio",
}

# CSS class / id fragments that usually indicate noise
_NOISE_PATTERNS = re.compile(
    r"cookie|consent|banner|popup|modal|overlay|sidebar|social|share|"
    r"widget|advert|newsletter|subscribe|footer|nav|menu|breadcrumb|"
    r"pagination|comment|disqus|signup|login",
    re.IGNORECASE,
)

# Maximum characters to keep from a sub-page snippet
_SNIPPET_LENGTH = 500


# ── The Refiner ─────────────────────────────────────────────────────────

class ContentRefinery:
    """Cleans raw HTML and extracts structured, readable content."""

    # ── Public API ──────────────────────────────────────────────────────

    def strip_digital_clutter(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Remove all noise elements from the DOM **in-place**.

        This mutates the passed ``soup`` object — callers should make a
        copy if they need the original tree intact.

        Targets removed:
            • Tags in ``_NOISY_TAGS``
            • Elements whose ``class`` or ``id`` match ``_NOISE_PATTERNS``
            • HTML comments
        """
        # 1. Strip known noisy tags
        for tag_name in _NOISY_TAGS:
            for element in soup.find_all(tag_name):
                element.decompose()

        # 2. Strip elements whose class or id smells like noise
        for element in soup.find_all(True):
            if element.attrs is None:
                continue
            css_classes = " ".join(element.get("class", []))
            element_id = element.get("id", "") or ""
            combined = f"{css_classes} {element_id}"
            if _NOISE_PATTERNS.search(combined):
                element.decompose()

        # 3. Strip HTML comments
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            comment.extract()

        pulse_logger.info("Stripped digital clutter from the DOM")
        return soup

    def extract_content_signals(
        self, soup: BeautifulSoup
    ) -> tuple[Optional[str], list[str], str]:
        """Pull structured signals from a de-cluttered DOM.

        Returns:
            A tuple of ``(page_title, headings, body_text)`` where:
            - ``page_title`` is the content of ``<title>``.
            - ``headings`` is a list of all ``<h1>`` and ``<h2>`` texts.
            - ``body_text`` is the concatenated text from the most
              content-dense container (``<article>``, ``<main>``, or
              the heaviest ``<div>``).
        """
        # ── Title ───────────────────────────────────────────────────────
        title_tag = soup.find("title")
        page_title = title_tag.get_text(strip=True) if title_tag else None

        # ── Headings ────────────────────────────────────────────────────
        headings: list[str] = []
        for tag in soup.find_all(["h1", "h2"]):
            text = tag.get_text(strip=True)
            if text and text not in headings:
                headings.append(text)

        # ── Body text — smart container detection ───────────────────────
        body_text = self._extract_primary_content(soup)

        pulse_logger.info(
            "Extracted %d heading(s) and %d chars of body text",
            len(headings),
            len(body_text),
        )
        return page_title, headings, body_text

    def distill_readable_text(self, raw_text: str) -> str:
        """Post-process extracted text into a clean, human-readable string.

        Operations:
            • Decode residual HTML entities (``&amp;`` → ``&``).
            • Normalise Unicode (NFKC).
            • Collapse runs of whitespace into single spaces.
            • Strip leading/trailing whitespace per line.
            • Remove completely blank lines.
        """
        text = unescape(raw_text)
        text = unicodedata.normalize("NFKC", text)

        # Collapse whitespace but preserve paragraph breaks
        lines = text.splitlines()
        cleaned_lines: list[str] = []
        for line in lines:
            stripped = re.sub(r"[ \t]+", " ", line).strip()
            if stripped:
                cleaned_lines.append(stripped)

        return "\n".join(cleaned_lines)

    def create_sub_page_snippet(self, soup: BeautifulSoup) -> str:
        """Generate a short content snippet from a sub-page DOM.

        Useful for the ``SubPageIntelligence.content_snippet`` field.
        """
        _, _, body_text = self.extract_content_signals(soup)
        cleaned = self.distill_readable_text(body_text)
        return cleaned[:_SNIPPET_LENGTH]

    # ── Private Helpers ─────────────────────────────────────────────────

    def _extract_primary_content(self, soup: BeautifulSoup) -> str:
        """Identify the most content-rich container and return its text.

        Strategy (in priority order):
            1. ``<article>`` tag.
            2. ``<main>`` tag.
            3. The ``<div>`` with the most direct text content.
            4. ``<body>`` fallback.
        """
        # Try semantic containers first
        for semantic_tag in ("article", "main"):
            container = soup.find(semantic_tag)
            if container and len(container.get_text(strip=True)) > 100:
                return container.get_text(separator="\n", strip=True)

        # Fall back to the heaviest <div> by text length
        best_div: Optional[Tag] = None
        best_length = 0
        for div in soup.find_all("div"):
            text_length = len(div.get_text(strip=True))
            if text_length > best_length:
                best_length = text_length
                best_div = div

        if best_div and best_length > 100:
            return best_div.get_text(separator="\n", strip=True)

        # Last resort — grab everything from <body>
        body = soup.find("body")
        if body:
            return body.get_text(separator="\n", strip=True)

        return soup.get_text(separator="\n", strip=True)
