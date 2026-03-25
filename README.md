# Project WebPulse -- AI-Powered Website Auditor and Summarizer

WebPulse takes any website URL as input, extracts and cleans the content, then uses AI to generate a structured business summary. It works both as a command-line tool and as a REST API.

---

## Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [Usage](#usage)
  - [Command Line](#command-line)
  - [REST API](#rest-api)
- [Output Format](#output-format)
- [How It Works](#how-it-works)
- [Reliability Layer](#reliability-layer)
- [Deep Search](#deep-search)
- [Error Handling](#error-handling)
- [Tech Stack](#tech-stack)

---

## Features

- Extracts page title, headings (H1, H2), and main body text from any website
- Removes navigation bars, footers, ads, cookie banners, and other noise
- Generates a 3-5 line AI-powered business summary using OpenAI (gpt-4o-mini)
- Classifies the business type (E-Commerce, SaaS, Healthcare, etc.)
- Automatically discovers and analyses sub-pages (/about, /services, /contact)
- Falls back to heuristic analysis if no API key is available
- Outputs a validated JSON report
- Includes both CLI and FastAPI REST API interfaces

---

## Project Structure

```
Website_Extracter/
    main.py              -- CLI entry point
    api.py               -- FastAPI REST API server
    test_api.py          -- API key diagnostic script
    requirements.txt     -- Python dependencies
    .env                 -- API key configuration (not committed)
    .env.example         -- Example environment file
    static/
        index.html       -- Web frontend for the API
    output/
        report.json      -- Generated audit report
    src/
        collector.py     -- Fetches web pages and discovers sub-pages
        cleaner.py       -- Removes noise and extracts meaningful content
        auditor.py       -- AI summary generation with heuristic fallback
        schema.py        -- Pydantic models for validated JSON output
        logger.py        -- Colour-coded terminal logger
        exceptions.py    -- Custom exception classes
```

---

## Setup

### 1. Clone the Repository

```bash
git clone <repo-url>
cd Website_Extracter
```

### 2. Create a Virtual Environment (Recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API Key (Optional)

```bash
copy .env.example .env
```

Open the `.env` file and add your OpenAI API key:

```
OPENAI_API_KEY=sk-your_api_key_here
```

You can get an API key at: https://platform.openai.com/api-keys

If you skip this step, WebPulse will still work using the heuristic fallback analyzer instead of AI. See the [Reliability Layer](#reliability-layer) section for details.


## Run With Command Line

Run from the project root directory:

```bash
# Interactive mode (prompts for URL)
py main.py

# Direct URL input
py main.py https://youtube.com

# Skip sub-page discovery
py main.py https://youtube.com --no-deep-search

# Save report to a custom location
py main.py https://youtube.com --output results/my_report.json
```

Note: On Windows, use `py` instead of `python` if Python is not in your PATH.

## Run With REST API (with Web Frontend)

Start the FastAPI server:

```bash
py api.py
```

Open `http://127.0.0.1:8000` in your browser to use the **web frontend** -- a clean interface where you can enter a URL, toggle deep search, and view the structured audit results directly in the browser.

For API documentation, visit `http://127.0.0.1:8000/docs` (Swagger UI).

#### Endpoints

| Method | Endpoint       | Description                          |
|--------|----------------|--------------------------------------|
| GET    | /              | Web frontend (audit page)            |
| GET    | /health        | Health check                         |
| POST   | /audit         | Full audit with sub-page discovery   |
| POST   | /audit/quick   | Quick audit without sub-pages        |

#### Example API Request

```bash
curl -X POST http://127.0.0.1:8000/audit -H "Content-Type: application/json" -d "{\"url\": \"https://youtube.com\", \"deep_search\": true}"
```

---

## Output Format

WebPulse produces a JSON report with the following structure:

```json
{
  "url": "https://www.youtube.com",
  "page_title": "YouTube",
  "headings": ["About YouTube"],
  "cleaned_content": "About YouTube. Our mission is to give everyone a voice...",
  "summary": "YouTube is a platform dedicated to giving everyone a voice and showcasing diverse stories from around the world...",
  "business_type": "Media & Entertainment",
  "sub_pages": [
    {
      "url": "https://www.youtube.com/about/",
      "title": "About YouTube",
      "headings": ["About YouTube"],
      "content_snippet": "Our mission is to give everyone a voice..."
    }
  ],
  "audit_metadata": {
    "timestamp": "2026-03-24T23:11:10.282683",
    "synthesis_method": "llm",
    "sub_pages_discovered": 1,
    "elapsed_seconds": 7.16
  }
}
```

Key fields:

- `summary` -- A 3-5 line business summary generated by AI or heuristics
- `business_type` -- The predicted industry category
- `synthesis_method` -- Shows `"llm"` if AI was used, `"heuristic"` if fallback was used
- `sub_pages` -- Data extracted from discovered internal pages

---

## How It Works

The pipeline runs in five steps:

```
URL Input --> COLLECT --> CLEAN --> AUDIT --> VALIDATE --> JSON Output
```

1. **Collect** -- Fetches the HTML from the target URL using rotating User-Agent headers. Discovers internal sub-pages like /about, /services, /contact.

2. **Clean** -- Removes noisy HTML elements (scripts, styles, nav bars, footers, cookie banners, ads) and extracts the meaningful content, headings, and page title.

3. **Audit** -- Sends the cleaned content to OpenAI's gpt-4o-mini model to generate a structured business summary and classification. If the API is unavailable, automatically falls back to heuristic analysis.

4. **Validate** -- All output passes through Pydantic models to ensure the JSON is well-structured and type-safe.

5. **Output** -- The validated report is saved as JSON and displayed in the terminal.

---

## Reliability Layer

WebPulse uses a dual-strategy approach to guarantee output even when the AI API is unavailable:

### Primary: AI-Powered Analysis

When a valid `OPENAI_API_KEY` is configured, the system sends the cleaned content to OpenAI (gpt-4o-mini) with structured prompts. The model returns a business summary and type classification in JSON format.

The terminal shows:
```
[WEBPULSE] Summary generated using AI (OpenAI gpt-4o-mini) -- Business type: 'Media & Entertainment'
```

### Fallback: Heuristic Analysis

When the API is unavailable (no key, network failure, or API error), the system automatically activates the heuristic analyzer:

1. **First-Paragraph Extraction** -- Selects the first 3-5 meaningful sentences as a summary
2. **Keyword Frequency Analysis** -- Counts domain-specific terms to classify the business type

The terminal shows:
```
[WEBPULSE] Summary generated using HEURISTIC FALLBACK (no LLM) -- Set OPENAI_API_KEY in .env for AI-powered summaries
```

The `synthesis_method` field in the output JSON indicates which strategy was used.

---

## Deep Search

WebPulse automatically discovers and analyses internal sub-pages for a more comprehensive business profile:

1. Scans all links on the root page
2. Matches internal links against known business-relevant patterns: /about, /services, /contact, /team, /products, /pricing, /careers, /faq
3. Fetches up to 5 sub-pages
4. Extracts title, headings, and a 500-character content snippet from each
5. Feeds sub-page content to the AI/heuristic analyzer for a richer summary

To disable deep search:

```bash
py main.py https://example.com --no-deep-search
```

Or in the API, set `"deep_search": false` in the request body.

---

## Error Handling

| Scenario              | Behaviour                                              |
|-----------------------|--------------------------------------------------------|
| HTTP 403 / 404        | Audit aborts with a clear error message                |
| Connection timeout    | Audit aborts gracefully                                |
| Sub-page load failure | Skipped with a warning, other sub-pages still crawled  |
| API key missing       | Heuristic fallback activates automatically             |
| API key invalid       | Heuristic fallback activates automatically             |
| Empty page content    | Warning logged, best-effort analysis of headings       |

---

## Tech Stack

- Python 3.10+
- Requests -- HTTP client with session reuse
- BeautifulSoup4 -- HTML parsing and DOM traversal
- Pydantic v2 -- Output schema validation
- OpenAI SDK -- GPT-4o-mini integration for AI summaries
- FastAPI -- REST API framework
- Uvicorn -- ASGI server
- python-dotenv -- Environment variable management
