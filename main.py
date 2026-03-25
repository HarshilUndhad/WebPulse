"""
main.py — WebPulse Entry Point

Orchestrates the full audit pipeline:
    Collect  →  Clean  →  Audit  →  Validate  →  Output

"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from copy import deepcopy
from pathlib import Path

from dotenv import load_dotenv

# Ensure the project root is on the path so ``src`` is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.auditor import WebsiteAuditor
from src.cleaner import ContentRefinery
from src.collector import SiteIntelligenceCollector
from src.exceptions import ContentExtractionError, NavigationError, WebPulseError
from src.logger import pulse_logger
from src.schema import AuditMetadata, SubPageIntelligence, WebsiteAuditReport

load_dotenv()


# CLI Argument Parsing 

def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="webpulse",
        description=(
            "WebPulse — AI-Powered Website Auditor & Summarizer. "
            "Extracts, cleans, and analyses website content to produce "
            "a structured business brief."
        ),
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="The target URL to audit (e.g. https://example.com). If omitted, you will be prompted.",
    )
    parser.add_argument(
        "--no-deep-search",
        action="store_true",
        default=False,
        help="Skip automatic sub-page discovery",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Path to save the JSON report (default: output/report.json)",
    )
    return parser


# Pipeline Orchestration

def run_audit(url: str, deep_search: bool = True, output_path: str | None = None) -> None:
   #Execute the full WebPulse pipeline for a given URL.

    start_time = time.time()

    pulse_logger.info("WebPulse v1.0 — Starting audit for %s", url)
    print()  # Visual separator

    #1. COLLECT
    collector = SiteIntelligenceCollector()

    try:
        _raw_html, root_soup = collector.harvest_page_intelligence(url)
    except NavigationError as exc:
        pulse_logger.error("Audit aborted — %s", exc)
        sys.exit(1)

    #2. DISCOVER SUB-PAGES
    sub_page_results = []
    if deep_search:
        sub_page_urls = collector.discover_sub_pages(root_soup, url)
        if sub_page_urls:
            sub_page_results = collector.harvest_sub_pages(sub_page_urls)

    #3. CLEAN
    refinery = ContentRefinery()

    # Work on a copy so the original soup remains intact for debugging
    cleaned_soup = refinery.strip_digital_clutter(deepcopy(root_soup))
    page_title, headings, body_text = refinery.extract_content_signals(cleaned_soup)
    cleaned_content = refinery.distill_readable_text(body_text)

    if not cleaned_content.strip():
        pulse_logger.warning("No meaningful content found on the root page")

    # Clean sub-pages
    sub_page_intelligence: list[SubPageIntelligence] = []
    sub_page_snippets: list[str] = []

    for _sp_html, sp_soup, sp_url in sub_page_results:
        sp_cleaned = refinery.strip_digital_clutter(deepcopy(sp_soup))
        sp_title_tag = sp_cleaned.find("title")
        sp_title = sp_title_tag.get_text(strip=True) if sp_title_tag else None
        sp_headings = [
            tag.get_text(strip=True)
            for tag in sp_cleaned.find_all(["h1", "h2"])
            if tag.get_text(strip=True)
        ]
        snippet = refinery.create_sub_page_snippet(sp_cleaned)
        sub_page_snippets.append(snippet)

        sub_page_intelligence.append(
            SubPageIntelligence(
                url=sp_url,
                title=sp_title,
                headings=sp_headings,
                content_snippet=snippet,
            )
        )

    #4. AUDIT
    auditor = WebsiteAuditor()
    summary, business_type, method = auditor.generate_business_brief(
        cleaned_content, headings, sub_page_snippets or None, url=url
    )

    if method == "llm":
        pulse_logger.info(
            "Summary generated using AI (OpenAI %s) — Business type: '%s'",
            "gpt-4o-mini", business_type,
        )
    else:
        pulse_logger.warning(
            "Summary generated using HEURISTIC FALLBACK (no LLM) — "
            "Set OPENAI_API_KEY in .env for AI-powered summaries"
        )

    #5. VALIDATE & OUTPUT
    elapsed = round(time.time() - start_time, 2)

    report = WebsiteAuditReport(
        url=url,
        title=page_title,
        headings=headings,
        cleaned_content=cleaned_content[:2000],  
        summary=summary,
        business_type=business_type,
        sub_pages=sub_page_intelligence,
        audit_metadata=AuditMetadata(
            synthesis_method=method,
            sub_pages_discovered=len(sub_page_intelligence),
            elapsed_seconds=elapsed,
        ),
    )

    report_json = report.model_dump_json(indent=2)

    # Print to terminal
    print()
    pulse_logger.info("Audit complete in %.1fs — report below", elapsed)
    print()
    print(report_json)

    # Save to file
    if output_path is None:
        output_dir = Path(__file__).resolve().parent / "output"
        output_dir.mkdir(exist_ok=True)
        output_path = str(output_dir / "report.json")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(report_json, encoding="utf-8")
    print()
    pulse_logger.info("Report saved to %s", output_path)


#Main

def main() -> None:
    parser = _build_argument_parser()
    args = parser.parse_args()

    url = args.url
    if not url:
        print(" Welcome to Project WebPulse")
        try:
            url = input("Enter the target URL to audit (e.g., example.com): ").strip()
        except KeyboardInterrupt:
            print("\n[WEBPULSE] Audit cancelled.")
            sys.exit(0)
            
        if not url:
            print("[WEBPULSE] Error: A valid URL is required.", file=sys.stderr)
            sys.exit(1)

    
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    run_audit(
        url=url,
        deep_search=not args.no_deep_search,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
