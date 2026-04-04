# Site Audit Workflow

## Objective
Run a full SEO audit on a website: crawl pages, check technical SEO and AEO across 10 audit dimensions, aggregate results, get AI analysis, and generate a PDF report.

## Prerequisites

1. **Python 3.11+** with venv activated:
   ```bash
   source .venv/bin/activate
   ```

2. **System dependencies** (macOS):
   ```bash
   brew install pango gdk-pixbuf libffi
   ```

3. **Environment variables** (in `.env`):
   - `SUPABASE_URL` + `SUPABASE_KEY` — required for DB storage (skip with `--no-db`)
   - `GOOGLE_PAGESPEED_API_KEY` — optional, CWV auditor degrades gracefully without it

4. **Supabase tables** — run `migrations/001_initial_schema.sql` in Supabase SQL editor

---

## CLI Usage

### Full Site Audit
```bash
python -m src.audit https://example.com
```
Crawls up to 50 pages via sitemap (falls back to spider), runs all audits, saves results to Supabase, generates PDF.

### Single Page Audit
```bash
python -m src.audit https://example.com/page --single-page --no-db
```
Fastest option. Fetches one page, runs all 10 audit tools, generates PDF locally.

### Limit Crawl Depth
```bash
python -m src.audit https://example.com --max-pages 20
```

### Custom Output Path
```bash
python -m src.audit https://example.com --output ./my-report.pdf --no-db
```

### View Audit History
```bash
python -m src.audit --history example.com
```
Requires Supabase credentials.

### Skip Database Storage
```bash
python -m src.audit https://example.com --no-db
```
Report saved locally to `.tmp/reports/<domain>-audit.pdf`.

---

## Pipeline Steps

1. **Crawl** — Discovers pages via `/sitemap.xml` (preferred) or BFS spider fallback. Respects `robots.txt`. Returns URL, HTML, status code, and headers per page.

2. **Audit** — Runs 10 tools on each page:
   | Tool | What It Checks |
   |------|---------------|
   | `onpage_auditor` | Title, meta description, H1, headings, canonical, OG/Twitter tags, word count |
   | `indexation_auditor` | Noindex conflicts, canonical issues, redirects, hreflang |
   | `link_auditor` | Internal/external links, broken links, anchor text quality |
   | `image_auditor` | Alt text, WebP format, lazy loading, dimensions |
   | `security_auditor` | HTTPS, mixed content, security headers (CSP, HSTS, X-Frame-Options) |
   | `cwv_auditor` | Core Web Vitals via PageSpeed API (LCP, CLS, TBT) |
   | `js_render_auditor` | SPA detection, empty root div, noscript fallback, script count |
   | `structured_data_auditor` | JSON-LD validation, schema.org types, AI bot governance |
   | `authority_auditor` | E-E-A-T signals: author, about/contact links, social profiles |
   | `aeo_auditor` | AI search optimization: direct answer patterns, Q&A headings, citation signals (stats + sources), content freshness, llms.txt, trust bottleneck detection |

3. **Aggregate** — Merges per-page results into site-wide metrics: overall score, severity counts, top issues, worst pages, per-tool summaries.

4. **AI Analysis** — Formats data as a prompt, saves to `.tmp/audit_data.json`, prints prompt to stdout. Waits for `.tmp/ai_analysis.json` with Claude's analysis.

5. **Report** — Generates PDF via Jinja2 + WeasyPrint with 6 sections: header, executive summary, priority fixes, detailed findings, page-by-page table, recommendations.

6. **Store** — Uploads PDF to Supabase Storage, saves audit run and findings to Postgres (unless `--no-db`).

---

## AI Analysis Step (MVP Flow)

The script pauses after step 4 and waits for AI input:

1. Script prints the analysis prompt to stdout
2. Script saves data to `.tmp/audit_data.json`
3. Script prompts: "Press Enter when ai_analysis.json is ready"
4. You (or Claude in-session) write analysis to `.tmp/ai_analysis.json`
5. Press Enter to continue to report generation

**Expected JSON structure for `.tmp/ai_analysis.json`:**
```json
{
  "executive_summary": "3-5 sentences summarizing SEO health",
  "priority_fixes": [
    {"issue": "str", "effort": "low|medium|high", "impact": "low|medium|high", "description": "str"}
  ],
  "category_analysis": {
    "tool_name": {"score": 85, "assessment": "str", "key_issues": ["str"]}
  },
  "recommendations": [
    {"action": "str", "priority": 1, "rationale": "str"}
  ]
}
```

**Skip AI analysis:** Press Ctrl+C during the wait to generate the report with a placeholder summary.

---

## Scoring

- Each tool scores 0-100 (or `null` if skipped)
- Page score = average of non-null tool scores
- Site score = average of all page scores
- Issue severities: **critical** > **high** > **medium** > **low**

### Score Interpretation
| Range | Meaning |
|-------|---------|
| 90-100 | Excellent — minor optimizations only |
| 70-89 | Good — some issues to address |
| 50-69 | Needs work — significant issues |
| 0-49 | Poor — critical problems require immediate attention |

---

## Edge Cases

- **Sites behind auth:** Crawler can't access authenticated pages. Use `--single-page` with a publicly accessible URL, or implement cookie-based auth in future.
- **JS-heavy SPAs:** The `js_render_auditor` flags SPA patterns heuristically (empty root div, heavy JS). No headless browser in MVP — scores may be conservative.
- **Rate limiting:** Crawler uses 1-second delay between requests. For aggressive sites, the crawl may be slow.
- **Very large sites (100+ pages):** AI analyzer truncates to 10 worst pages for the prompt. Use `--max-pages` to limit crawl scope.
- **No PageSpeed API key:** CWV auditor returns `score=None` with a "skipped" issue. Other 9 tools still run normally.
- **No Supabase credentials:** Use `--no-db` flag. Report saves locally. History mode won't work.
- **AEO auditor on thin content:** Pages with no H2/H3 headings skip the direct-answer and question-heading checks gracefully (ratio = 0.0, no issue flagged). The tool is most useful on content-heavy pages.
- **Trust bottleneck false positives:** Words like "best" are only flagged when no statistic or data point appears in the same paragraph. Legitimate data-backed claims are not penalized.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` | Run `source .venv/bin/activate && pip install -e ".[dev]"` |
| `weasyprint` crashes | Run `brew install pango gdk-pixbuf libffi` |
| `SUPABASE_URL must be set` | Add credentials to `.env` or use `--no-db` |
| Crawler returns 0 pages | Check if robots.txt blocks the user agent, or site requires auth |
| Score is 0 for all pages | Likely HTTP errors — check `status_code` in `.tmp/audit_data.json` |
| `ai_analysis.json` parse error | Ensure valid JSON with required keys |
| AEO score low on landing pages | Landing pages often lack Q&A structure — expected. Focus AEO optimization on blog/content pages |

---

## Comparing Audits Over Time

With Supabase configured:
1. Run audits periodically: `python -m src.audit https://example.com`
2. View history: `python -m src.audit --history example.com`
3. Compare `overall_score` and `pages_crawled` across runs
4. Check `severity_counts` in summary to track issue reduction
