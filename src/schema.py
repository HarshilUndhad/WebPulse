"""
schema.py — Pydantic Models for Validated Audit Output

Every piece of data that leaves the WebPulse pipeline passes through
these models.  This guarantees that the final JSON is always
well-structured, type-safe, and free of surprise `None` fields that
would break downstream consumers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SubPageIntelligence(BaseModel):
    #Structured representation of a single sub-page (e.g. /about).

    url: str = Field(..., description="Fully-qualified URL of the sub-page")
    title: Optional[str] = Field(None, description="HTML <title> of the sub-page")
    headings: list[str] = Field(
        default_factory=list,
        description="All H1/H2 headings discovered on the sub-page",
    )
    content_snippet: str = Field(
        "",
        description="First ~500 characters of cleaned body text",
    )


class AuditMetadata(BaseModel):
    
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="ISO-8601 timestamp of the audit run",
    )
    synthesis_method: str = Field(
        "llm",
        description="'llm' if the summary came from Gemini, 'heuristic' if fallback was used",
    )
    sub_pages_discovered: int = Field(
        0,
        description="Number of sub-pages that were found and analysed",
    )
    elapsed_seconds: Optional[float] = Field(
        None,
        description="Total wall-clock time of the audit in seconds",
    )


class WebsiteAuditReport(BaseModel):
   #Top-level output schema returned by the WebPulse pipeline.

    url: str = Field(..., description="The root URL that was audited")
    title: Optional[str] = Field(None, description="HTML <title> of the root page")
    headings: list[str] = Field(
        default_factory=list,
        description="All H1/H2 headings from the root page",
    )
    cleaned_content: str = Field(
        "",
        description="De-cluttered main body text of the root page",
    )
    summary: str = Field(
        "",
        description="3-5 line AI-generated (or heuristic) summary",
    )
    business_type: str = Field(
        "General / Unclassified",
        description="Predicted industry or business category",
    )
    sub_pages: list[SubPageIntelligence] = Field(
        default_factory=list,
        description="Intelligence gathered from discovered sub-pages",
    )
    audit_metadata: AuditMetadata = Field(
        default_factory=AuditMetadata,
        description="Operational metadata for the audit run",
    )
