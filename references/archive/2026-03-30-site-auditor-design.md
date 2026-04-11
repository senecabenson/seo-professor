# Site Auditor — Design Spec

## Purpose

A full-site SEO auditor that crawls a domain, runs 11 independent audit checks (including AEO for AI search engines), sends aggregated results to Claude for AI-powered analysis, and generates a shareable PDF report with prioritized recommendations. Built for Seneca's personal SEO work and client deliverables.

## Architecture

Modular pipeline following the WAT framework (Workflows, Agents, Tools):

```
[URL / Domain]
       |
       v
  crawler.py          -- discovers pages via sitemap.xml, falls back to spider
       |
       v
  Audit Tool Pipeline -- 11 independent tools, each produces structured JSON
       |
       v
  aggregator.py       -- merges all tool results per page into one dataset
       |
       v
  ai_analyzer.py      -- sends aggregated data to Claude API for analysis
       |
       v
  report_generator.py -- renders PDF report via weasyprint
       |
       v
  Supabase Storage    -- stores PDF, returns shareable URL
```

## Audit Tools (Priority Order)

Each tool is a standalone Python script in `tools/`. Input: URL + raw HTML. Output: structured JSON.

| # | Tool | Checks | Why (2025-2026 Expert Consensus) |
|---|------|--------|----------------------------------|
| 1 | `crawler.py` | Sitemap discovery, spider crawl, page inventory | Foundation for everything else |
| 2 | `indexation_auditor.py` | Crawl budget, orphan pages, redirect chains/loops, noindex conflicts, 302 vs 301 | #1 missed audit item per Lily Ray, Google docs |
| 3 | `onpage_auditor.py` | Titles, descriptions, canonicals, robots, H1-H6 structure, keyword alignment | Combined meta + headings. On-page is table stakes (Grumpy SEO Guy) |
| 4 | `cwv_auditor.py` | LCP (<2.5s), INP (<200ms), CLS (<0.1), mobile-friendliness, image performance | Core ranking signal. INP replaced FID in 2024 |
| 5 | `js_render_auditor.py` | Content behind JS, initial HTML vs rendered DOM diff, JS-dependent nav | Google two-phase crawl — JS content may never get indexed (John Mueller) |
| 6 | `structured_data_auditor.py` | Schema presence/validity/accuracy, AI bot governance (robots.txt for GPTBot, OAI-SearchBot) | Schema is "the language of LLMs" — bridge to AI search (Aleyda Solis 2026) |
| 7 | `security_auditor.py` | HTTPS everywhere, mixed content, SSL validity, HSTS, HTTP->HTTPS redirects | Baseline trust signal |
| 8 | `link_auditor.py` | Internal/external links, broken links, anchor text, link equity flow | Internal linking drives crawl priority |
| 9 | `image_auditor.py` | Alt text, file sizes, formats (WebP), lazy loading | Lower priority but matters for accessibility + LCP |
| 10 | `authority_auditor.py` | E-E-A-T signals (author pages, about, contact info, review signals). Competitive authority benchmarking deferred until a backlink data API is added | When on-page is equal, authority wins (Grumpy SEO Guy) |
| 11 | `aeo_auditor.py` | Direct answer patterns, content structure for AI extraction, question-format headings, citation-worthiness signals (stats + sources), content freshness, llms.txt, AI-optimized meta descriptions, trust bottleneck detection | AEO bridges traditional SEO and AI search — 41% visibility lift from statistics alone (Frase.io 2025). 44.2% of LLM citations come from first 30% of text |

### Tool Interface Contract

Every audit tool follows the same interface:

**Input:** `url` (str), `html` (str), `config` (dict, optional)
**Output:**
```json
{
  "tool": "tool_name",
  "url": "https://example.com/page",
  "score": 72,
  "issues": [
    {
      "severity": "high",
      "type": "missing_meta_description",
      "detail": "No meta description found"
    }
  ],
  "data": {}
}
```

Severity levels: `critical`, `high`, `medium`, `low`

## Database Schema (Supabase / Postgres)

### sites
| Column | Type | Notes |
|--------|------|-------|
| id | uuid, PK | |
| domain | text, unique | |
| name | text | |
| created_at | timestamptz | |
| metadata | jsonb | Site type, notes, client info |

### audit_runs
| Column | Type | Notes |
|--------|------|-------|
| id | uuid, PK | |
| site_id | FK -> sites | |
| started_at | timestamptz | |
| completed_at | timestamptz | |
| status | text | running, completed, failed |
| pages_crawled | int | |
| overall_score | int | 0-100 aggregate |
| summary | jsonb | High-level stats |

### page_results
| Column | Type | Notes |
|--------|------|-------|
| id | uuid, PK | |
| audit_run_id | FK -> audit_runs | |
| url | text | |
| status_code | int | |
| html_hash | text | Detect content changes between audits |
| crawled_at | timestamptz | |

### audit_findings
| Column | Type | Notes |
|--------|------|-------|
| id | uuid, PK | |
| page_result_id | FK -> page_results | |
| tool | text | Which audit tool found this |
| severity | text | critical, high, medium, low |
| issue_type | text | e.g. missing_meta_description |
| detail | text | Human-readable description |
| data | jsonb | Raw tool output for this finding |
| created_at | timestamptz | |

### reports
| Column | Type | Notes |
|--------|------|-------|
| id | uuid, PK | |
| audit_run_id | FK -> audit_runs | |
| ai_analysis | text | Claude's full analysis |
| recommendations | jsonb | Prioritized action items |
| report_url | text | Supabase Storage path to PDF |
| generated_at | timestamptz | |

## AI Analysis

**MVP (Claude Code in-session):** The orchestrator collects and aggregates audit data, then presents it to Claude within the Claude Code session for analysis. No separate API call needed — Claude analyzes the data directly in conversation and produces the structured output for the report generator.

**Future (standalone/automated):** If audits need to run unattended (scheduled, web app, CI pipeline), add `anthropic` SDK + API key to call Claude directly from the script. This is a future enhancement, not MVP.

**Analysis structure (regardless of mode):**
1. Site context (domain, page count, site type)
2. Aggregated findings by category with severity counts
3. Top issues across all pages
4. Output: executive summary, prioritized fixes with effort estimates, category-by-category analysis

**Output format:** Structured JSON with `executive_summary`, `priority_fixes`, `category_analysis`, `recommendations` fields.

## PDF Report

Generated via `weasyprint` (HTML template rendered to PDF). Stored in Supabase Storage.

**Report sections:**
1. **Header** — domain, date, overall score, pages crawled, issue counts by severity
2. **Executive Summary** — Claude AI, 3-5 sentences
3. **Top Priority Fixes** — numbered list with effort estimates
4. **Detailed Findings by Category** — each of the 11 audit tool sections with issues
5. **Page-by-Page Breakdown** — sorted by score/issue count
6. **Recommendations** — Claude AI prioritized action plan

## CLI Entry Point

```bash
# Full site audit
python src/audit.py https://example.com

# Single page quick check
python src/audit.py https://example.com/about --single-page

# Re-run audit on registered site
python src/audit.py --site-id <uuid>

# View past audits
python src/audit.py --history example.com
```

Orchestrator (`src/audit.py`) manages the full pipeline: crawl -> audit -> aggregate -> AI analyze -> generate PDF -> store -> print URL.

## Workflow

`workflows/site-audit.md` documents the SOP: when to run, what inputs are needed, edge cases (sites behind auth, JS-heavy SPAs, rate limiting), and how to interpret results.

## Dependencies

- `supabase` — Supabase Python SDK
- `httpx` — async HTTP client for crawling
- `beautifulsoup4` — HTML parsing
- `weasyprint` — HTML to PDF rendering
- `lxml` — XML/HTML processing (sitemap parsing)

## Environment Variables (.env)

```
SUPABASE_URL=
SUPABASE_KEY=
GOOGLE_PAGESPEED_API_KEY=  # for CWV auditor
```

## File Structure

```
src/
  audit.py              # CLI entry point / orchestrator
  aggregator.py         # Merges tool results
  ai_analyzer.py        # Claude API integration
  report_generator.py   # PDF report rendering
  db.py                 # Supabase client + queries
tools/
  crawler.py
  indexation_auditor.py
  onpage_auditor.py
  cwv_auditor.py
  js_render_auditor.py
  structured_data_auditor.py
  security_auditor.py
  link_auditor.py
  image_auditor.py
  authority_auditor.py
  aeo_auditor.py
workflows/
  site-audit.md         # SOP for running audits
```

## Success Criteria

- Run `python src/audit.py https://example.com` and get a PDF report
- Report contains AI-powered executive summary and prioritized recommendations
- All 11 audit tools produce valid JSON output
- Results stored in Supabase with full audit history
- PDF is shareable (Supabase Storage URL)
- Single-page mode works for quick checks
- Audit history is queryable per domain
