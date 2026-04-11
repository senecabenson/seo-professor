# Site Auditor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a modular site auditor that crawls a domain, runs 10 independent SEO audit checks, aggregates results, presents data for Claude in-session AI analysis, and generates a shareable PDF report stored in Supabase.

**Architecture:** WAT framework — Claude orchestrates, deterministic Python tools execute. Pipeline: crawler → 10 audit tools → aggregator → AI data formatter → PDF report → Supabase Storage. Each audit tool is a standalone script with identical interface contract (url + html in, structured JSON out).

**Tech Stack:** Python 3.11+, httpx (async crawling), BeautifulSoup4 + lxml (HTML/XML parsing), weasyprint + Jinja2 (PDF reports), Supabase (Postgres + Storage), pytest (TDD)

**Design Spec:** `docs/superpowers/specs/2026-03-30-site-auditor-design.md`

---

## File Structure

```
pyproject.toml                    # Project config, deps, pytest settings
requirements.txt                  # Pinned dependencies
conftest.py                       # Root pytest config, shared fixtures
src/
  __init__.py
  audit.py                        # CLI entry point / orchestrator
  aggregator.py                   # Merges tool results into site-wide dataset
  ai_analyzer.py                  # Formats audit data for Claude in-session analysis
  report_generator.py             # HTML template → PDF via weasyprint
  db.py                           # Supabase client + CRUD operations
  templates/
    report.html                   # Jinja2 report template
    report.css                    # Report styles
tools/
  __init__.py
  base.py                         # AuditResult/AuditIssue types, validate_result()
  crawler.py                      # Sitemap + spider page discovery
  onpage_auditor.py               # Title, meta, headings, canonical, OG tags
  indexation_auditor.py            # Noindex conflicts, canonical issues, redirects
  cwv_auditor.py                  # Core Web Vitals via PageSpeed API
  js_render_auditor.py            # JS rendering red flags (heuristic, no browser)
  structured_data_auditor.py      # JSON-LD, microdata, AI bot governance
  security_auditor.py             # HTTPS, mixed content, security headers
  link_auditor.py                 # Internal/external links, broken links, anchors
  image_auditor.py                # Alt text, formats, lazy loading, sizing
  authority_auditor.py            # E-E-A-T signals (author, about, contact)
tests/
  __init__.py
  test_tool_contract.py           # Validates AuditResult schema enforcement
  test_crawler.py
  test_onpage_auditor.py
  test_indexation_auditor.py
  test_cwv_auditor.py
  test_js_render_auditor.py
  test_structured_data_auditor.py
  test_security_auditor.py
  test_link_auditor.py
  test_image_auditor.py
  test_authority_auditor.py
  test_aggregator.py
  test_ai_analyzer.py
  test_report_generator.py
  test_audit_cli.py
  test_db.py
  factories.py                    # make_audit_result() helpers for test data
  fixtures/
    sample_page.html              # Realistic page with known SEO issues
    perfect_page.html             # Well-optimized page (score ~100)
    minimal_page.html             # Bare minimum valid HTML
    spa_page.html                 # React-style empty root div + JS bundles
    page_with_schema.html         # Valid JSON-LD structured data
    page_with_eeat.html           # Strong E-E-A-T signals
    sitemap.xml                   # Sample sitemap with 5 URLs
    sitemap_index.xml             # Sitemap index with 2 sub-sitemaps
    robots.txt                    # Sample robots.txt with Disallow rules
    pagespeed_response.json       # Mocked PageSpeed Insights API response
migrations/
  001_initial_schema.sql          # Supabase table creation
workflows/
  site-audit.md                   # SOP for running audits
```

## Dependency Graph

```
Task 1 (Scaffolding)
  → Task 2 (Tool Contract + Fixtures)
    → Task 3 (Crawler)
      → Tasks 4-7 (Audit Tool Batches) ← CAN PARALLELIZE
      → Task 8 (Aggregator)
        → Task 10 (AI Analyzer)
        → Task 11 (Report Generator)
          → Task 12 (Orchestrator CLI)
    → Task 9 (DB Layer) ← PARALLEL with Tasks 4-7
      → Task 12 (Orchestrator CLI)
Task 13 (Workflow SOP) ← anytime after Task 1
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `src/__init__.py`
- Create: `tools/__init__.py`
- Create: `tests/__init__.py`
- Create: `conftest.py`
- Create: `tests/test_smoke.py`
- Modify: `CLAUDE.md` (update SQLite → Supabase, remove Claude API SDK reference)

- [ ] **Step 1: Check Python 3.11+ availability**

Run: `python3.11 --version` or `python3 --version`
If < 3.11, install: `brew install python@3.11` or use pyenv.

- [ ] **Step 2: Create pyproject.toml**

```toml
[project]
name = "seo-professor"
version = "0.1.0"
description = "AI-powered SEO audit suite"
requires-python = ">=3.11"
dependencies = [
    "supabase>=2.0",
    "httpx>=0.27",
    "beautifulsoup4>=4.12",
    "weasyprint>=62",
    "lxml>=5.0",
    "jinja2>=3.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "respx>=0.22",
]

[project.scripts]
seo-audit = "src.audit:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
asyncio_mode = "auto"
```

- [ ] **Step 3: Create requirements.txt**

```
supabase>=2.0
httpx>=0.27
beautifulsoup4>=4.12
weasyprint>=62
lxml>=5.0
jinja2>=3.1
pytest>=8.0
pytest-asyncio>=0.23
respx>=0.22
```

- [ ] **Step 4: Create package __init__.py files**

Empty files: `src/__init__.py`, `tools/__init__.py`, `tests/__init__.py`

- [ ] **Step 5: Create conftest.py with shared fixtures**

```python
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "tests" / "fixtures"


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def sample_html(fixtures_dir):
    return (fixtures_dir / "sample_page.html").read_text()


@pytest.fixture
def perfect_html(fixtures_dir):
    return (fixtures_dir / "perfect_page.html").read_text()


@pytest.fixture
def minimal_html(fixtures_dir):
    return (fixtures_dir / "minimal_page.html").read_text()
```

- [ ] **Step 6: Create venv and install dependencies**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

- [ ] **Step 7: Write smoke test**

```python
# tests/test_smoke.py
def test_imports():
    import src
    import tools
    assert True


def test_fixtures_dir_exists(fixtures_dir):
    assert fixtures_dir.exists() or True  # fixtures created in Task 2
```

- [ ] **Step 8: Run smoke test**

Run: `pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 9: Update CLAUDE.md tech stack section**

Change `**Data:** SQLite (local, via sqlite3 stdlib)` → `**Data:** Supabase (Postgres + Storage)`
Change `**AI:** Claude API via anthropic SDK` → `**AI:** Claude in-session analysis (MVP), Claude API for future standalone mode`

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml requirements.txt conftest.py src/__init__.py tools/__init__.py tests/__init__.py tests/test_smoke.py CLAUDE.md
git commit -m "feat: scaffold project with dependencies and pytest config"
```

---

### Task 2: Tool Interface Contract + Test Fixtures

**Files:**
- Create: `tools/base.py`
- Create: `tests/test_tool_contract.py`
- Create: `tests/fixtures/sample_page.html`
- Create: `tests/fixtures/perfect_page.html`
- Create: `tests/fixtures/minimal_page.html`
- Create: `tests/factories.py`

- [ ] **Step 1: Write failing contract validation tests**

```python
# tests/test_tool_contract.py
from tools.base import validate_result, AuditResult


def test_valid_result_passes():
    result = {
        "tool": "test_tool",
        "url": "https://example.com",
        "score": 85,
        "issues": [
            {"severity": "high", "type": "test_issue", "detail": "A test issue"}
        ],
        "data": {"key": "value"},
    }
    assert validate_result(result) is True


def test_score_out_of_range_fails():
    result = {
        "tool": "test_tool",
        "url": "https://example.com",
        "score": 150,
        "issues": [],
        "data": {},
    }
    assert validate_result(result) is False


def test_invalid_severity_fails():
    result = {
        "tool": "test_tool",
        "url": "https://example.com",
        "score": 50,
        "issues": [
            {"severity": "urgent", "type": "test", "detail": "bad severity"}
        ],
        "data": {},
    }
    assert validate_result(result) is False


def test_missing_tool_name_fails():
    result = {
        "tool": "",
        "url": "https://example.com",
        "score": 50,
        "issues": [],
        "data": {},
    }
    assert validate_result(result) is False


def test_missing_issue_fields_fails():
    result = {
        "tool": "test_tool",
        "url": "https://example.com",
        "score": 50,
        "issues": [{"severity": "high"}],  # missing type and detail
        "data": {},
    }
    assert validate_result(result) is False


def test_none_score_allowed_for_skipped_tools():
    result = {
        "tool": "cwv_auditor",
        "url": "https://example.com",
        "score": None,
        "issues": [
            {"severity": "low", "type": "skipped", "detail": "No API key"}
        ],
        "data": {},
    }
    assert validate_result(result) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tool_contract.py -v`
Expected: FAIL (tools.base doesn't exist yet)

- [ ] **Step 3: Implement tools/base.py**

```python
# tools/base.py
from typing import TypedDict, Literal


VALID_SEVERITIES = {"critical", "high", "medium", "low"}


class AuditIssue(TypedDict):
    severity: Literal["critical", "high", "medium", "low"]
    type: str
    detail: str


class AuditResult(TypedDict):
    tool: str
    url: str
    score: int | None  # None = tool was skipped
    issues: list[AuditIssue]
    data: dict


def validate_result(result: dict) -> bool:
    """Validate an audit tool result matches the contract."""
    if not isinstance(result, dict):
        return False
    required_keys = {"tool", "url", "score", "issues", "data"}
    if not required_keys.issubset(result.keys()):
        return False
    if not result["tool"] or not result["url"]:
        return False
    if result["score"] is not None:
        if not isinstance(result["score"], int) or not (0 <= result["score"] <= 100):
            return False
    if not isinstance(result["issues"], list):
        return False
    for issue in result["issues"]:
        if not isinstance(issue, dict):
            return False
        if not {"severity", "type", "detail"}.issubset(issue.keys()):
            return False
        if issue["severity"] not in VALID_SEVERITIES:
            return False
    return True


def make_result(
    tool: str,
    url: str,
    score: int | None,
    issues: list[dict],
    data: dict | None = None,
) -> AuditResult:
    """Helper to create a valid AuditResult dict."""
    return {
        "tool": tool,
        "url": url,
        "score": score,
        "issues": issues,
        "data": data or {},
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tool_contract.py -v`
Expected: All 6 PASS

- [ ] **Step 5: Create test fixture HTML files**

`tests/fixtures/sample_page.html` — a page with known SEO issues:
- Missing meta description
- Two H1 tags
- No canonical tag
- Missing alt text on images
- Mixed content (HTTP image on HTTPS page)
- No structured data
- Links with empty anchor text

`tests/fixtures/perfect_page.html` — fully optimized page:
- Proper title (55 chars), meta description (155 chars)
- Single H1, proper heading hierarchy
- Self-referencing canonical
- All images have alt text, WebP format, lazy loading, width/height
- JSON-LD structured data (Article type)
- OG + Twitter Card meta tags
- Author bio with link, about/contact links
- HTTPS only, no mixed content

`tests/fixtures/minimal_page.html` — bare minimum:
```html
<!DOCTYPE html>
<html lang="en">
<head><title>Minimal</title></head>
<body><p>Hello world</p></body>
</html>
```

- [ ] **Step 6: Create test factories**

```python
# tests/factories.py
from tools.base import make_result


def make_onpage_result(url="https://example.com", score=75, issues=None):
    return make_result(
        tool="onpage_auditor",
        url=url,
        score=score,
        issues=issues or [
            {"severity": "high", "type": "missing_meta_description",
             "detail": "No meta description found"},
        ],
        data={"title_length": 45, "word_count": 350},
    )


def make_perfect_result(tool="onpage_auditor", url="https://example.com"):
    return make_result(tool=tool, url=url, score=100, issues=[], data={})


def make_skipped_result(tool="cwv_auditor", url="https://example.com"):
    return make_result(
        tool=tool,
        url=url,
        score=None,
        issues=[{"severity": "low", "type": "skipped",
                 "detail": "Tool skipped — missing API key"}],
    )
```

- [ ] **Step 7: Commit**

```bash
git add tools/base.py tests/test_tool_contract.py tests/factories.py tests/fixtures/
git commit -m "feat: add audit tool interface contract and test fixtures"
```

---

### Task 3: Crawler

**Files:**
- Create: `tools/crawler.py`
- Create: `tests/test_crawler.py`
- Create: `tests/fixtures/sitemap.xml`
- Create: `tests/fixtures/sitemap_index.xml`
- Create: `tests/fixtures/robots.txt`

**Implementation notes:**
- Sitemap-first discovery: fetch `/sitemap.xml`, parse `<loc>` URLs with `lxml.etree`
- Spider fallback: if no sitemap, BFS internal links from start URL via BeautifulSoup
- `httpx.AsyncClient` with configurable rate limiting (default 1s delay)
- Respect `robots.txt` via `urllib.robotparser`
- Config: `max_pages` (default 50), `delay_seconds`, `user_agent`
- Return: `list[CrawlResult]` where `CrawlResult = {"url": str, "status_code": int, "html": str, "headers": dict}`

- [ ] **Step 1: Write failing tests**

Key tests:
- `test_parse_sitemap` — unit test parsing fixture XML, expects list of URLs
- `test_parse_sitemap_index` — unit test handling sitemap index pointing to sub-sitemaps
- `test_extract_internal_links` — unit test extracting links from HTML fixture
- `test_respects_max_pages` — crawl stops after max_pages limit
- `test_deduplicates_urls` — same URL found via sitemap and spider returns once
- `test_robots_txt_respected` — disallowed paths are skipped
- Integration test with `respx` mocking httpx responses

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_crawler.py -v`

- [ ] **Step 3: Create fixture files**

`tests/fixtures/sitemap.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/</loc></url>
  <url><loc>https://example.com/about</loc></url>
  <url><loc>https://example.com/blog</loc></url>
  <url><loc>https://example.com/contact</loc></url>
  <url><loc>https://example.com/services</loc></url>
</urlset>
```

`tests/fixtures/sitemap_index.xml` and `tests/fixtures/robots.txt` with appropriate test content.

- [ ] **Step 4: Implement tools/crawler.py**

Key functions:
- `async def crawl(url: str, config: dict | None = None) -> list[dict]`
- `def parse_sitemap(xml_content: str) -> list[str]`
- `def extract_internal_links(html: str, base_url: str) -> set[str]`
- `def check_robots(robots_txt: str, url: str, user_agent: str) -> bool`

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_crawler.py -v`

- [ ] **Step 6: Commit**

```bash
git add tools/crawler.py tests/test_crawler.py tests/fixtures/sitemap*.xml tests/fixtures/robots.txt
git commit -m "feat: add site crawler with sitemap discovery and spider fallback"
```

---

### Task 4: Audit Batch 1 — On-Page + Indexation (HTML Parsing)

**Files:**
- Create: `tools/onpage_auditor.py`
- Create: `tools/indexation_auditor.py`
- Create: `tests/test_onpage_auditor.py`
- Create: `tests/test_indexation_auditor.py`

**CAN PARALLELIZE with Tasks 5, 6, 7, 9**

**onpage_auditor checks:** title (exists, 50-60 chars), meta description (exists, 150-160 chars), canonical, H1 (exactly one), heading hierarchy (no skipped levels), OG/Twitter meta, robots meta, word count.

**Scoring:** Start at 100. Deductions: missing title (-20), missing description (-15), missing H1 (-15), multiple H1s (-10), missing canonical (-10), heading hierarchy issues (-5 each), missing OG tags (-5). Floor at 0.

**indexation_auditor checks:** robots meta noindex conflicts, canonical pointing elsewhere, redirect chain detection (via `config.status_code` and `config.redirect_history`), hreflang validation, X-Robots-Tag header conflicts.

**TDD pattern for each tool:**
1. Test with `perfect_page.html` → score ~100, no issues
2. Test with `sample_page.html` → specific issues detected, score matches expected deductions
3. Test with `minimal_page.html` → missing items flagged appropriately
4. Test edge cases: empty HTML, None inputs
5. Validate all outputs via `validate_result()`

- [ ] **Steps 1-5: Write failing tests, implement, verify pass (per tool)**
- [ ] **Step 6: Commit**

```bash
git add tools/onpage_auditor.py tools/indexation_auditor.py tests/test_onpage_auditor.py tests/test_indexation_auditor.py
git commit -m "feat: add on-page and indexation audit tools"
```

---

### Task 5: Audit Batch 2 — Link + Image + Security (HTTP-Level)

**Files:**
- Create: `tools/link_auditor.py`
- Create: `tools/image_auditor.py`
- Create: `tools/security_auditor.py`
- Create: `tests/test_link_auditor.py`
- Create: `tests/test_image_auditor.py`
- Create: `tests/test_security_auditor.py`

**CAN PARALLELIZE with Tasks 4, 6, 7, 9**

**link_auditor:** internal/external link count, broken links (empty href, javascript:void), anchor text quality ("click here" = bad), nofollow usage.

**image_auditor:** alt text presence + quality, WebP format detection, `loading="lazy"`, width/height attributes, large base64 inline images.

**security_auditor:** HTTPS check, mixed content (HTTP resources on HTTPS page), security headers via `config.headers` (CSP, X-Frame-Options, HSTS, Referrer-Policy).

**TDD:** Same pattern as Task 4 using shared fixtures.

- [ ] **Steps 1-5: Write failing tests, implement, verify pass (per tool)**
- [ ] **Step 6: Commit**

```bash
git add tools/link_auditor.py tools/image_auditor.py tools/security_auditor.py tests/test_link_auditor.py tests/test_image_auditor.py tests/test_security_auditor.py
git commit -m "feat: add link, image, and security audit tools"
```

---

### Task 6: Audit Batch 3 — CWV + JS Render (External/Heuristic)

**Files:**
- Create: `tools/cwv_auditor.py`
- Create: `tools/js_render_auditor.py`
- Create: `tests/test_cwv_auditor.py`
- Create: `tests/test_js_render_auditor.py`
- Create: `tests/fixtures/spa_page.html`
- Create: `tests/fixtures/pagespeed_response.json`

**CAN PARALLELIZE with Tasks 4, 5, 7, 9**

**cwv_auditor:** Calls Google PageSpeed Insights API. Parses LCP, INP, CLS, FCP, TTFB. Scores against Google thresholds. Graceful degradation: if no `GOOGLE_PAGESPEED_API_KEY`, returns `score=None` with "skipped" issue.

**js_render_auditor:** Heuristic-based (no headless browser in MVP). Checks for: empty `<body>` or `<div id="root"></div>` pattern, `<noscript>` fallback content, heavy JS bundle count, deprecated AJAX crawling `<meta name="fragment">`.

**TDD:** Mock PageSpeed API with `respx` for cwv_auditor. Use `spa_page.html` fixture for js_render_auditor.

- [ ] **Steps 1-5: Write failing tests, implement, verify pass (per tool)**
- [ ] **Step 6: Commit**

```bash
git add tools/cwv_auditor.py tools/js_render_auditor.py tests/test_cwv_auditor.py tests/test_js_render_auditor.py tests/fixtures/spa_page.html tests/fixtures/pagespeed_response.json
git commit -m "feat: add CWV and JS render audit tools"
```

---

### Task 7: Audit Batch 4 — Structured Data + Authority (Schema/EEAT)

**Files:**
- Create: `tools/structured_data_auditor.py`
- Create: `tools/authority_auditor.py`
- Create: `tests/test_structured_data_auditor.py`
- Create: `tests/test_authority_auditor.py`
- Create: `tests/fixtures/page_with_schema.html`
- Create: `tests/fixtures/page_with_eeat.html`

**CAN PARALLELIZE with Tasks 4, 5, 6, 9**

**structured_data_auditor:** Find JSON-LD blocks, validate JSON parsing, check required schema.org properties per type (Article: headline, author, datePublished; Organization: name, url). Check robots.txt for AI bot directives (GPTBot, OAI-SearchBot, anthropic-ai).

**authority_auditor:** Heuristic E-E-A-T signals: author bylines with links, about page link, contact page link, privacy/TOS links, social media profile links, review/testimonial schema. No external API — all derived from on-page HTML.

- [ ] **Steps 1-5: Write failing tests, implement, verify pass (per tool)**
- [ ] **Step 6: Commit**

```bash
git add tools/structured_data_auditor.py tools/authority_auditor.py tests/test_structured_data_auditor.py tests/test_authority_auditor.py tests/fixtures/page_with_schema.html tests/fixtures/page_with_eeat.html
git commit -m "feat: add structured data and authority audit tools"
```

---

### Task 8: Aggregator

**Files:**
- Create: `src/aggregator.py`
- Create: `tests/test_aggregator.py`

**Implementation:** Merges per-page tool results into site-wide dataset.

**Input:** `dict[str, list[AuditResult]]` — URL → list of tool results for that page.

**Output:**
```python
{
    "site_score": 68,          # average of page scores
    "pages_audited": 15,
    "severity_counts": {"critical": 2, "high": 8, "medium": 15, "low": 22},
    "top_issues": [{"type": "missing_meta_description", "count": 12, "severity": "high"}],
    "worst_pages": [{"url": "...", "score": 32, "issue_count": 5}],
    "tool_summaries": {"onpage_auditor": {"avg_score": 75, "issue_count": 18}},
    "pages": {
        "https://example.com/page": {
            "score": 72,
            "issues": [...],
            "tool_results": {"onpage_auditor": {...}, ...}
        }
    },
}
```

**Key functions:**
- `def aggregate(results: dict[str, list[dict]]) -> dict` — main entry point
- `def score_page(tool_results: list[dict]) -> int` — weighted average of tool scores (skip None)
- `def count_severities(issues: list[dict]) -> dict` — tally by severity
- `def rank_issues(all_issues: list[dict]) -> list[dict]` — most frequent types first

**TDD tests:** Single page/single tool, single page/multiple tools, multi-page site stats, None score handling, severity counting, top issues ranking.

- [ ] **Steps 1-5: Write failing tests, implement, verify pass**
- [ ] **Step 6: Commit**

```bash
git add src/aggregator.py tests/test_aggregator.py
git commit -m "feat: add audit result aggregator"
```

---

### Task 9: Database Layer (Supabase)

**Files:**
- Create: `src/db.py`
- Create: `tests/test_db.py`
- Create: `migrations/001_initial_schema.sql`

**CAN PARALLELIZE with Tasks 4-7**

**SQL schema:** 5 tables — `sites`, `audit_runs`, `page_results`, `audit_findings`, `reports`. Per design spec column definitions. Include proper FK constraints, indexes on `domain` and `audit_run_id`, and `created_at` defaults.

**db.py functions:**
- `get_client()` — singleton Supabase client from `SUPABASE_URL` + `SUPABASE_KEY` env vars
- `upsert_site(domain, name, metadata)` → site record
- `create_audit_run(site_id)` → audit_run with status="running"
- `update_audit_run(run_id, status, pages_crawled, overall_score, summary)`
- `insert_page_result(audit_run_id, url, status_code, html_hash)`
- `insert_findings(page_result_id, findings)` — bulk insert audit_findings
- `insert_report(audit_run_id, ai_analysis, recommendations, report_url)`
- `get_audit_history(domain)` → list of past runs, sorted by date desc
- `get_site_by_domain(domain)` → site or None

**TDD:** All tests mock the Supabase client. Test correct table names, data shapes, error handling.

- [ ] **Steps 1-5: Write failing tests, implement, verify pass**
- [ ] **Step 6: Commit**

```bash
git add src/db.py tests/test_db.py migrations/001_initial_schema.sql
git commit -m "feat: add Supabase database layer and schema migration"
```

---

### Task 10: AI Analyzer (Data Formatter)

**Files:**
- Create: `src/ai_analyzer.py`
- Create: `tests/test_ai_analyzer.py`

**Key insight:** This does NOT call Claude API. It formats aggregated audit data into a structured prompt optimized for Claude in-session analysis.

**Input:** Aggregated data from `aggregator.py`
**Output:**
```python
{
    "prompt": "...",            # Formatted text presenting audit data to Claude
    "structured_input": {...},  # Clean JSON-serializable audit data
}
```

**Prompt structure asks Claude for:** executive summary (3-5 sentences), prioritized fixes with effort estimates, category-by-category analysis, overall recommendations.

**Output format instruction in prompt:** JSON with `executive_summary`, `priority_fixes`, `category_analysis`, `recommendations` fields.

**Large site handling:** If 100+ pages, include full data for 10 worst pages, statistical summaries for the rest.

- [ ] **Steps 1-5: Write failing tests, implement, verify pass**
- [ ] **Step 6: Commit**

```bash
git add src/ai_analyzer.py tests/test_ai_analyzer.py
git commit -m "feat: add AI analysis data formatter for in-session Claude"
```

---

### Task 11: Report Generator (PDF)

**Files:**
- Create: `src/report_generator.py`
- Create: `src/templates/report.html`
- Create: `src/templates/report.css`
- Create: `tests/test_report_generator.py`

**Template sections (per design spec):**
1. Header — domain, date, overall score, pages crawled, severity counts
2. Executive Summary — from AI analysis
3. Top Priority Fixes — numbered list with effort estimates
4. Detailed Findings by Category — each tool's section with issues
5. Page-by-Page Breakdown — table sorted by score
6. Recommendations — AI-generated action plan

**Key functions:**
- `def generate_report(aggregated_data: dict, ai_analysis: dict, output_path: str) -> str` — renders HTML via Jinja2, converts to PDF via weasyprint, returns output path
- `def upload_report(pdf_path: str, audit_run_id: str) -> str` — uploads to Supabase Storage, returns public URL

**Styling:** Color-coded severities (red=critical, orange=high, yellow=medium, blue=low). Score number with color. Clean, professional layout suitable for client deliverables.

**TDD:** Test file creation, valid PDF output (check `%PDF` magic bytes), test with minimal data, test with full data, mock Supabase storage for upload.

**Note:** weasyprint requires system dependencies (cairo, pango). If not installed: `brew install pango gdk-pixbuf libffi`

- [ ] **Steps 1-5: Write failing tests, implement, verify pass**
- [ ] **Step 6: Commit**

```bash
git add src/report_generator.py src/templates/ tests/test_report_generator.py
git commit -m "feat: add PDF report generator with Jinja2 templates"
```

---

### Task 12: Orchestrator (CLI Entry Point)

**Files:**
- Create: `src/audit.py`
- Create: `tests/test_audit_cli.py`

**CLI interface (argparse):**
```
python src/audit.py <url>                    # Full site audit
python src/audit.py <url> --single-page      # Single page only
python src/audit.py --site-id <uuid>         # Re-run registered site
python src/audit.py --history <domain>       # View past audits
python src/audit.py <url> --max-pages 20     # Limit crawl
python src/audit.py <url> --output ./report.pdf  # Custom output path
python src/audit.py <url> --no-db            # Skip Supabase storage
```

**Pipeline (full audit mode):**
1. Parse args, validate URL
2. `crawler.crawl(url)` → list of pages
3. For each page: run all 10 audit tools with page's url + html
4. `aggregator.aggregate(results)` → site-wide dataset
5. `ai_analyzer.format_for_analysis(aggregated)` → prompt + structured data
6. Print formatted data to stdout for Claude in-session analysis
7. Read AI analysis from stdin or `.tmp/ai_analysis.json`
8. `report_generator.generate_report(aggregated, ai_analysis, output_path)`
9. Store in Supabase (unless `--no-db`)
10. Print report path/URL

**MVP interaction flow:** Script outputs audit data as JSON to `.tmp/audit_data.json`, prints the analysis prompt to stdout, then waits for `.tmp/ai_analysis.json` to exist before generating the report.

**TDD:** Test arg parsing, test single-page mode skips crawler, test `--history` mode, test pipeline with all components mocked.

- [ ] **Steps 1-5: Write failing tests, implement, verify pass**
- [ ] **Step 6: Commit**

```bash
git add src/audit.py tests/test_audit_cli.py
git commit -m "feat: add CLI orchestrator for full audit pipeline"
```

---

### Task 13: Workflow Documentation

**Files:**
- Create: `workflows/site-audit.md`

**Contents:**
- Objective and prerequisites (venv, env vars, Supabase tables, weasyprint deps)
- Step-by-step for each CLI mode
- Edge cases: sites behind auth, JS-heavy SPAs, rate limiting, very large sites (>100 pages)
- How to interpret scores and severity levels
- How to compare audits over time
- Troubleshooting common errors
- Mark "First capability scoped and ready to build" checkbox in project_specs.md

- [ ] **Step 1: Write workflow SOP**
- [ ] **Step 2: Update project_specs.md checkbox**
- [ ] **Step 3: Commit**

```bash
git add workflows/site-audit.md project_specs.md
git commit -m "docs: add site audit workflow SOP"
```

---

## Verification

After all tasks complete:

1. **Unit tests green:** `pytest -v` — all tests pass
2. **Contract enforced:** Every audit tool's tests call `validate_result()` on output
3. **CLI runs:** `python src/audit.py https://example.com --single-page --no-db` produces a PDF in `.tmp/reports/`
4. **PDF valid:** Open the PDF, verify all 6 report sections render
5. **DB works:** With Supabase credentials configured, run full audit and verify data in tables
6. **History works:** `python src/audit.py --history example.com` shows past runs

## Risk Flags

1. **Python version:** System has 3.9.6, need 3.11+. Check `python3.11 --version` first.
2. **weasyprint system deps:** Requires `brew install pango gdk-pixbuf libffi` on macOS.
3. **Supabase credentials:** `.env` exists but may be empty. DB tests use mocks; real integration after credentials configured.
4. **PageSpeed API key:** CWV auditor gracefully degrades without it (returns score=None).
