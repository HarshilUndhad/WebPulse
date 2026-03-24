# 🔍 Project WebPulse — AI-Powered Website Auditor & Summarizer

> Extract, clean, and analyse any website to generate a structured business intelligence report — powered by Google Gemini with an automatic heuristic fallback.

---

## Architecture

```
main.py                     ← Clean CLI entry point
├── src/
│   ├── collector.py        ← The Explorer   — HTTP navigation + Deep Search
│   ├── cleaner.py          ← The Refiner    — Signal/noise separation
│   ├── auditor.py          ← The Brain      — LLM + Heuristic fallback
│   ├── schema.py           ← Pydantic models for validated JSON output
│   ├── logger.py           ← Branded terminal logger
│   └── exceptions.py       ← Custom exception hierarchy
├── output/
│   └── report.json         ← Generated audit report
├── requirements.txt
├── .env.example
└── README.md
```

### Pipeline Flow

```
   URL Input
       │
       ▼
 ┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
 │  COLLECT     │───▶│  CLEAN       │───▶│  AUDIT       │───▶│  VALIDATE    │
 │  (Explorer)  │    │  (Refiner)   │    │  (Brain)     │    │  (Pydantic)  │
 └─────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
       │                                       │
       ▼                                       ▼
  Deep Search                          LLM ──or── Heuristic
  (sub-pages)                          Fallback
```

---

## Quick Start

### 1. Clone & Set Up

```bash
git clone <repo-url>
cd Website_Extracter

# Create a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure API Key (Optional)

```bash
copy .env.example .env
# Edit .env and paste your Gemini API key
# Get one free at: https://aistudio.google.com/apikey
```

> **Note:** If you skip this step, WebPulse will still work — it will use the heuristic fallback analyzer instead of the LLM. See the [Reliability Layer](#-reliability-layer) section below.

### 3. Run an Audit

```bash
python main.py https://example.com
```

**Options:**

| Flag                | Description                              |
|---------------------|------------------------------------------|
| `--no-deep-search`  | Skip automatic sub-page discovery        |
| `--output PATH`     | Custom path for the JSON report          |

**Examples:**

```bash
# Basic audit
python main.py https://books.toscrape.com

# Skip sub-page discovery
python main.py https://example.com --no-deep-search

# Save to a custom location
python main.py https://example.com --output results/my_report.json
```

---

## Output Format

The tool produces a Pydantic-validated JSON report:

```json
{
  "url": "https://example.com",
  "page_title": "Example Domain",
  "headings": ["Example Domain"],
  "cleaned_content": "This domain is for use in illustrative examples...",
  "summary": "Example.com is a reserved domain used for documentation and illustrative examples in technical writing. It serves as a safe placeholder URL that will never host real content. The site is maintained by IANA as part of the RFC 2606 standard.",
  "business_type": "General / Unclassified",
  "sub_pages": [],
  "audit_metadata": {
    "timestamp": "2026-03-24T17:30:00.000000",
    "synthesis_method": "llm",
    "sub_pages_discovered": 0,
    "elapsed_seconds": 3.21
  }
}
```

---

## 🛡 Reliability Layer

WebPulse implements a **dual-strategy synthesis architecture** to guarantee output even when external APIs are unavailable:

### Strategy 1: LLM-Powered Analysis (Primary)

When a valid `GEMINI_API_KEY` is configured, the system sends the cleaned content and headings to Google Gemini (`gemini-2.0-flash`) with a structured prompt. The LLM returns a 3–5 line business summary and a business-type classification.

### Strategy 2: Heuristic Fallback (Automatic)

When the LLM is unavailable (no API key, network failure, malformed response), the system automatically activates the `HeuristicFallbackAnalyzer`:

1. **First-Paragraph Extraction** — Selects the first 3–5 meaningful sentences from the content as a naive summary.
2. **Keyword Frequency Analysis** — Counts non-stopword terms and matches them against domain-specific keyword sets (E-Commerce, SaaS, Healthcare, Education, etc.) to classify the business type.

The fallback is logged clearly in the terminal:
```
[WEBPULSE] ⚠ LLM unavailable — engaging heuristic fallback analyzer
```

The `audit_metadata.synthesis_method` field in the JSON output will show `"heuristic"` so consumers know which strategy was used.

---

## 🔎 Deep Search

WebPulse automatically discovers and crawls internal sub-pages to build a more comprehensive profile:

### How It Works

1. The Explorer scans all `<a>` tags on the root page.
2. Internal links whose final path segment matches high-value patterns are selected:
   - `/about`, `/about-us`, `/services`, `/contact`, `/team`, `/products`, `/pricing`, `/careers`, `/faq`
3. Up to **5 sub-pages** are fetched and cleaned.
4. Each sub-page's title, headings, and a 500-character content snippet are included in the output.
5. Sub-page content is also fed to the LLM/heuristic analyzer for a richer summary.

### Disabling Deep Search

```bash
python main.py https://example.com --no-deep-search
```

---

## Project Components

| Module            | Class / Function                | Responsibility                                    |
|-------------------|---------------------------------|---------------------------------------------------|
| `collector.py`    | `SiteIntelligenceCollector`     | HTTP navigation, User-Agent rotation, deep search |
| `cleaner.py`      | `ContentRefinery`               | DOM clutter removal, signal extraction            |
| `auditor.py`      | `BusinessProfileSynthesizer`    | Gemini LLM integration                            |
| `auditor.py`      | `HeuristicFallbackAnalyzer`     | Keyword frequency + first-paragraph fallback      |
| `auditor.py`      | `WebsiteAuditor`                | Unified facade (LLM → fallback)                   |
| `schema.py`       | `WebsiteAuditReport`           | Pydantic output validation                        |
| `logger.py`       | `pulse_logger`                  | Branded terminal status updates                   |
| `exceptions.py`   | `NavigationError`, etc.         | Structured error handling                         |

---

## Error Handling

| Scenario              | Behaviour                                                   |
|-----------------------|-------------------------------------------------------------|
| HTTP 403 / 404        | `NavigationError` raised with status code and reason        |
| Connection timeout    | `NavigationError` raised — audit aborts gracefully          |
| Sub-page load failure | Logged as warning, skipped — other sub-pages still crawled  |
| LLM API failure       | Heuristic fallback activates automatically                  |
| No API key set        | Heuristic fallback activates automatically                  |
| Empty page content    | Warning logged, best-effort analysis of headings            |

---

## Tech Stack

- **Python 3.10+**
- **Requests** — HTTP client with session reuse
- **BeautifulSoup4** — HTML parsing and DOM traversal
- **Pydantic v2** — Output schema validation
- **Google Generative AI SDK** — Gemini LLM integration
- **python-dotenv** — Environment variable management
