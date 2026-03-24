"""
auditor.py — The Brain

Synthesises a structured business profile from cleaned website content.
Two strategies are available:

    1. LLM-powered 
       Uses the Openai API (``gpt-4o-mini``) to produce a
       rich 3–5 line summary and a business-type classification.

    2. Heuristic fallback 
       Activates automatically when the API key is missing, the request
       fails, or the response is malformed.  Uses frequency analysis of
       key phrases and first-paragraph extraction to produce a
       best-effort summary.

The Duel Strategy ensures the pipeline always returns something useful instead of just relying on LLM 
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from typing import Optional

from openai import OpenAI

from src.exceptions import AuditSynthesisError
from src.logger import pulse_logger



_LLM_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = (
    "You are a senior business analyst. You will be given:\n"
    "  1. The target URL\n"
    "  2. Headings and text content extracted from the website\n"
    "  3. Optionally, snippets from sub-pages\n\n"
    "Produce a JSON object with exactly two keys:\n"
    '  "summary": a 3-5 line paragraph summarising what the website actually is and does,\n'
    '  "business_type": a short label for the industry or category '
    "(e.g. 'Social Media', 'Search Engine', 'E-Commerce', 'SaaS', "
    "'Video Streaming', 'Healthcare', 'Education', 'News & Media').\n\n"
    "IMPORTANT RULES:\n"
    "- The URL itself is a strong identity signal. Use it along with any "
    "available content to identify the website.\n"
    "- If the extracted content is sparse or mostly boilerplate (login pages, "
    "cookie notices, JavaScript placeholders), use the URL and domain name "
    "to identify the website and provide an accurate summary based on your "
    "knowledge of that website.\n"
    "- NEVER fabricate generic descriptions. Be specific to the actual website.\n"
    "- Prioritize Main Content over Sub-Page Snippets for classification.\n"
    "- Return ONLY the JSON object, no markdown fences, no extra text."
)

# Common stop-words to exclude from frequency analysis
_STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "is", "it", "as", "are",
    "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may",
    "can", "this", "that", "these", "those", "not", "no", "so",
    "if", "than", "too", "very", "just", "about", "up", "out",
    "all", "also", "into", "over", "after", "before", "between",
    "own", "same", "other", "each", "more", "most", "some", "such",
    "only", "new", "one", "our", "its", "your", "their", "we",
    "us", "you", "he", "she", "they", "them", "his", "her", "my",
    "me", "i", "what", "which", "who", "when", "where", "how",
    "there", "here", "then", "now", "any", "many", "much",
}


#LLM Strategy 
class BusinessProfileSynthesizer:
    #Using Openai API to generate a business summary

    def __init__(self) -> None:
        self._client: OpenAI | None = None
        self._available: Optional[bool] = None
        self._last_url: str = "unknown"

    
    def is_available(self) -> bool:
        #Check whether an OpenAI API key is set.
        if self._available is not None:
            return self._available

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            self._available = False
            return False

        try:
            self._client = OpenAI(api_key=api_key)
            self._available = True
        except Exception:
            self._available = False

        return self._available

    def synthesize_business_profile(
        self,
        content: str,
        headings: list[str],
        sub_page_snippets: list[str] | None = None,
        url: str = "unknown",
    ) -> tuple[str, str]:
        
        self._last_url = url
        if not self.is_available():
            raise AuditSynthesisError("OpenAI API is not configured")

        # Build the user prompt
        heading_block = "\n".join(f"  {h}" for h in headings) if headings else "(none)"
        user_prompt = (
            f"## Target URL\n{self._last_url or 'unknown'}\n\n"
            f"## Headings\n{heading_block}\n\n"
            f"## Main Content (truncated to 3000 chars)\n{content[:3000]}"
        )
        if sub_page_snippets:
            combined = "\n---\n".join(sub_page_snippets[:3])
            user_prompt += f"\n\n## Sub-Page Snippets\n{combined}"

        try:
            response = self._client.chat.completions.create(
                model=_LLM_MODEL,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            raw_text = response.choices[0].message.content.strip()

            # Strip potential markdown code fences if they appear
            raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
            raw_text = re.sub(r"\s*```$", "", raw_text)

            data = json.loads(raw_text)
            summary = data.get("summary", "").strip()
            business_type = data.get("business_type", "General / Unclassified").strip()

            if not summary:
                raise AuditSynthesisError("LLM returned an empty summary")

            pulse_logger.info("LLM synthesis complete — identified as '%s'", business_type)
            return summary, business_type

        except json.JSONDecodeError:
            raise AuditSynthesisError("LLM response was not valid JSON")
        except AuditSynthesisError:
            raise
        except Exception as exc:
            raise AuditSynthesisError(f"LLM call failed — {exc}")


# Heuristic Fallback Strategy 

class HeuristicFallbackAnalyzer:
    # Safety-net analyser that runs when the LLM is unavailable.

    # Strategy:
    #     1. First-paragraph extraction: Grabs the first 3–5 sentences
    #        as a naive summary.
    #     2. Frequency analysis: Counts the most common non-stopword
    #        terms to guess the business domain.
    

    def synthesize_business_profile(
        self,
        content: str,
        headings: list[str],
        sub_page_snippets: list[str] | None = None,
    ) -> tuple[str, str]:
        
        pulse_logger.warning(
            "LLM unavailable — engaging heuristic fallback analyzer"
        )

        # Combine all available text for analysis
        all_text = content
        if sub_page_snippets:
            all_text += "\n" + "\n".join(sub_page_snippets)

        summary = self._extract_lead_paragraph(all_text, headings)
        business_type = self._guess_business_type(all_text, headings)

        pulse_logger.info(
            "Heuristic analysis complete — classified as '%s'", business_type
        )
        return summary, business_type

    # Private Helpers 
    def _extract_lead_paragraph(
        self, text: str, headings: list[str]
    ) -> str:
        #Build a summary from the first few meaningful sentences.
        # Split into sentences (rough heuristic)
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        meaningful = [
            s for s in sentences
            if len(s.split()) >= 5 and not s.startswith("http")
        ]

        # Take the first 3–5 sentences
        lead = meaningful[:5]
        if not lead and headings:
            lead = [
                f"This website covers topics including: {', '.join(headings[:5])}."
            ]
        elif not lead:
            lead = ["No meaningful content could be extracted from this website."]

        return " ".join(lead)

    def _guess_business_type(
        self, text: str, headings: list[str]
    ) -> str:
        """Attempt to classify the website using keyword frequency."""
        combined = f"{text} {' '.join(headings)}".lower()
        words = re.findall(r"[a-z]{3,}", combined)
        filtered = [w for w in words if w not in _STOP_WORDS]
        counter = Counter(filtered)

        # Keyword → business type mapping
        _DOMAIN_SIGNALS: dict[str, list[str]] = {
            "E-Commerce / Retail": [
                "shop", "cart", "price", "buy", "product", "store",
                "order", "shipping", "discount", "sale",
            ],
            "SaaS / Technology": [
                "software", "platform", "api", "cloud", "dashboard",
                "integration", "saas", "app", "deploy", "developer",
            ],
            "Healthcare / Medical": [
                "health", "medical", "patient", "doctor", "clinic",
                "hospital", "treatment", "diagnosis", "care", "wellness",
            ],
            "Education / E-Learning": [
                "learn", "course", "student", "education", "training",
                "university", "school", "tutorial", "teach", "curriculum",
            ],
            "News & Media": [
                "news", "article", "journalist", "editor", "press",
                "media", "report", "breaking", "publish", "blog",
            ],
            "Finance / Fintech": [
                "finance", "bank", "invest", "loan", "insurance",
                "payment", "credit", "fintech", "trading", "fund",
            ],
            "Non-Profit / NGO": [
                "donate", "charity", "volunteer", "nonprofit", "mission",
                "cause", "community", "foundation", "impact", "advocacy",
            ],
            "Government / Public Sector": [
                "government", "public", "citizen", "policy", "regulation",
                "department", "federal", "municipal", "compliance", "law",
            ],
        }

        best_type = "General / Unclassified"
        best_score = 0

        for domain, keywords in _DOMAIN_SIGNALS.items():
            score = sum(counter.get(kw, 0) for kw in keywords)
            if score > best_score:
                best_score = score
                best_type = domain

        # Only trust the classification if there's a meaningful signal
        if best_score < 3:
            return "General / Unclassified"

        return best_type


 

class WebsiteAuditor:
    #High-level facade that tries the LLM first, then falls back to heuristics
    # This is the only class that ``main.py`` needs to interact with
    

    def __init__(self) -> None:
        self._llm = BusinessProfileSynthesizer()
        self._heuristic = HeuristicFallbackAnalyzer()

    def generate_business_brief(
        self,
        content: str,
        headings: list[str],
        sub_page_snippets: list[str] | None = None,
        url: str = "unknown",
    ) -> tuple[str, str, str]:
        # Attempt LLM first
        if self._llm.is_available():
            try:
                summary, biz = self._llm.synthesize_business_profile(
                    content, headings, sub_page_snippets, url=url
                )
                return summary, biz, "llm"
            except AuditSynthesisError as exc:
                pulse_logger.warning("LLM synthesis failed — %s", exc.reason)

        # Fallback to heuristics
        summary, biz = self._heuristic.synthesize_business_profile(
            content, headings, sub_page_snippets
        )
        return summary, biz, "heuristic"
