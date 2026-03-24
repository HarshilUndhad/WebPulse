"""
collector.py — The Explorer

Responsible for navigating to target URLs, fetching raw HTML, and
discovering internal sub-pages (Deep Search) that may contain
additional business intelligence (e.g. /about, /services, /contact).

"""

from __future__ import annotations

import random
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from src.exceptions import NavigationError
from src.logger import pulse_logger

# Constants
# Connectors, the user agent to avoid bot detection
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]

_DISCOVERY_PATTERNS = {
    "about", "about-us", "about_us",
    "services", "our-services", "what-we-do",
    "contact", "contact-us",
    "team", "our-team", "people",
    "products", "solutions",
    "pricing", "plans",
    "careers", "jobs",
    "faq", "help",
}

_MAX_SUB_PAGES = 5
_REQUEST_TIMEOUT_SECONDS = 15


# The Explorer

class SiteIntelligenceCollector:
    # Navigates to websites and extracts their raw HTML.

    def __init__(self) -> None:
        self.session = requests.Session()

    # Public API

    def harvest_page_intelligence(
        self, url: str
    ) -> tuple[str, BeautifulSoup]:
        raw_html = self._navigate_to(url)
        soup = BeautifulSoup(raw_html, "html.parser")
        pulse_logger.info("Successfully navigated to %s", url)
        return raw_html, soup

    def discover_sub_pages(
        self, soup: BeautifulSoup, base_url: str
    ) -> list[str]:
        # Scan the DOM for internal links that match high-value patterns.
        parsed_base = urlparse(base_url)
        base_domain = parsed_base.netloc
        discovered: dict[str, str] = {}  # slug → absolute URL

        for anchor in soup.find_all("a", href=True):
            href: str = anchor["href"].strip()

            # Skip empty, fragment-only, and external links
            if not href or href.startswith("#") or href.startswith("javascript"):
                continue

            absolute_url = urljoin(base_url, href)
            parsed = urlparse(absolute_url)

            # Only follow links on the same domain
            if parsed.netloc != base_domain:
                continue

            # Check if the last path segment matches any discovery pattern
            path_segments = [
                seg for seg in parsed.path.strip("/").split("/") if seg
            ]
            if not path_segments:
                continue

            slug = path_segments[-1].lower()
            if slug in _DISCOVERY_PATTERNS and slug not in discovered:
                discovered[slug] = absolute_url

            if len(discovered) >= _MAX_SUB_PAGES:
                break

        urls = list(discovered.values())
        if urls:
            pulse_logger.info(
                "Discovered %d sub-page(s): %s",
                len(urls),
                ", ".join(urlparse(u).path for u in urls),
            )
        else:
            pulse_logger.info("No additional sub-pages discovered")

        return urls

    def harvest_sub_pages(
        self, sub_page_urls: list[str]
    ) -> list[tuple[str, BeautifulSoup, str]]:
       #Fetch each sub-page URL and return a list of parsed results.
        results: list[tuple[str, BeautifulSoup, str]] = []
        for page_url in sub_page_urls:
            try:
                raw_html, soup = self.harvest_page_intelligence(page_url)
                results.append((raw_html, soup, page_url))
            except NavigationError as exc:
                pulse_logger.warning(
                    "Skipping sub-page %s — %s", page_url, exc.reason
                )
        return results

    # Private Helpers 

    def _navigate_to(self, url: str) -> str:
       # Low-level HTTP GET with User-Agent rotation and error mapping.
        headers = {"User-Agent": random.choice(_USER_AGENTS)}

        try:
            response = self.session.get(
                url, headers=headers, timeout=_REQUEST_TIMEOUT_SECONDS
            )
        except requests.exceptions.Timeout:
            raise NavigationError(url, "Connection timed out")
        except requests.exceptions.ConnectionError:
            raise NavigationError(url, "Could not establish connection")
        except requests.exceptions.RequestException as exc:
            raise NavigationError(url, str(exc))

        if response.status_code == 403:
            raise NavigationError(url, "Access forbidden by the server", 403)
        if response.status_code == 404:
            raise NavigationError(url, "Page not found", 404)
        if response.status_code >= 400:
            raise NavigationError(
                url,
                f"Server returned an error",
                response.status_code,
            )

        return response.text
