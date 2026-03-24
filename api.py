"""
api.py — WebPulse FastAPI Backend

Exposes the full audit pipeline as a REST API.
Run with:
    uvicorn api:app --reload
    # or
    py api.py
"""

from __future__ import annotations

import sys
import time
from copy import deepcopy
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Ensure the project root is on the path so ``src`` is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.auditor import WebsiteAuditor
from src.cleaner import ContentRefinery
from src.collector import SiteIntelligenceCollector
from src.exceptions import NavigationError
from src.logger import pulse_logger
from src.schema import AuditMetadata, SubPageIntelligence, WebsiteAuditReport


load_dotenv()


# FastAPI App

app = FastAPI(
    title="WebPulse API",
    description=(
        "AI-Powered Website Auditor & Summarizer — "
        "Extracts, cleans, and analyses website content to produce "
        "a structured business brief."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request / Response Models

class AuditRequest(BaseModel):
    #Request body for the /audit endpoint.
    url: str = Field(..., description="Target URL to audit (e.g. https://youtube.com)")
    deep_search: bool = Field(True, description="Whether to discover and analyse sub-pages")


class ErrorResponse(BaseModel):
    #Structured error response.
    error: str
    detail: str


#Core Pipeline 

def _run_pipeline(url: str, deep_search: bool = True) -> WebsiteAuditReport:
    #Execute the full WebPulse pipeline and return the report object.

    start_time = time.time()

    pulse_logger.info("WebPulse v1.0 — Starting audit for %s", url)

    # Ensure URL has a scheme
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # 1. COLLECT 
    collector = SiteIntelligenceCollector()
    _raw_html, root_soup = collector.harvest_page_intelligence(url)

    # 2. DISCOVER SUB-PAGES 
    sub_page_results = []
    if deep_search:
        sub_page_urls = collector.discover_sub_pages(root_soup, url)
        if sub_page_urls:
            sub_page_results = collector.harvest_sub_pages(sub_page_urls)

    # 3. CLEAN 
    refinery = ContentRefinery()

    cleaned_soup = refinery.strip_digital_clutter(deepcopy(root_soup))
    page_title, headings, body_text = refinery.extract_content_signals(cleaned_soup)
    cleaned_content = refinery.distill_readable_text(body_text)

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

    # 4. AUDIT 
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

    # 5. BUILD REPORT 
    elapsed = round(time.time() - start_time, 2)

    report = WebsiteAuditReport(
        url=url,
        page_title=page_title,
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

    pulse_logger.info("Audit complete in %.1fs", elapsed)
    return report


# API Endpoints 

@app.get("/", tags=["Health"], include_in_schema=False)
def serve_frontend():
    return FileResponse(
        Path(__file__).resolve().parent / "static" / "index.html",
        media_type="text/html",
    )


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "online",
        "service": "WebPulse API",
        "version": "1.0.0",
    }


@app.post("/audit", response_model=WebsiteAuditReport, tags=["Audit"])
def run_audit(request: AuditRequest):
    try:
        report = _run_pipeline(url=request.url, deep_search=request.deep_search)
        return report
    except NavigationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Navigation failed for {exc.url} — {exc.reason}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Internal audit error — {exc}",
        )


@app.post("/audit/quick", response_model=WebsiteAuditReport, tags=["Audit"])
def run_quick_audit(request: AuditRequest):
    """Run a quick audit without sub-page discovery (faster)."""
    try:
        report = _run_pipeline(url=request.url, deep_search=False)
        return report
    except NavigationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Navigation failed for {exc.url} — {exc.reason}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Internal audit error — {exc}",
        )


#Run directly 

if __name__ == "__main__":
    import uvicorn
    print("\n  Starting WebPulse API server...")
    print("   Swagger docs → http://127.0.0.1:8000/docs\n")
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
