# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
A personal full-stack SEO suite that combines website auditing, content optimization, keyword rank tracking, and reporting into a single AI-powered system. Built for Seneca's SEO work across multiple projects.

## Commands

```bash
# Setup
source .venv/bin/activate
pip install -e ".[dev]"
# macOS system deps (WeasyPrint): brew install pango gdk-pixbuf libffi

# Run full audit
python -m src.audit https://example.com

# Common flags
python -m src.audit https://example.com --single-page   # one page only
python -m src.audit https://example.com --max-pages 20   # limit crawl
python -m src.audit https://example.com --no-db           # skip Supabase
python -m src.audit https://example.com --output ./out.pdf
python -m src.audit --history example.com                 # view past audits

# Tests
pytest                          # all tests
pytest tests/test_crawler.py    # single file
pytest -v                       # verbose
```

---

## Architecture: WAT Framework

You operate inside the WAT framework (Workflows, Agents, Tools).

- **Workflows** (`workflows/`): Markdown SOPs — objective, inputs,
  tools to use, expected outputs, edge cases
- **Agent** (You): Read workflows, make decisions, call tools,
  recover from errors, ask when unclear
- **Tools** (`tools/`): Deterministic Python scripts — API calls,
  data transforms, file ops, DB queries

**Why this separation matters:** When AI handles every step directly,
accuracy compounds downward. Offload execution to deterministic scripts.
You focus on orchestration and judgment.

### Audit Pipeline

The CLI orchestrator (`src/audit.py`) runs this pipeline:

1. **Crawl** → `tools/crawler.py` — sitemap discovery + BFS spider, respects robots.txt, 1s delay, max 50 pages
2. **Audit** → Run 10 tools on each page → collect `AuditResult[]` per URL
3. **Aggregate** → `src/aggregator.py` — merge per-page results into site-wide metrics
4. **Format for AI** → `src/ai_analyzer.py` — build structured prompt + input data
5. **AI Analysis** → Three-mode priority: (1) `ANTHROPIC_API_KEY` set → calls Claude API directly; (2) `.tmp/ai_analysis.json` exists → loads it (Claude Code in-session mode); (3) neither → default analysis, PDF still generates
6. **Generate Report** → `src/report_generator.py` — Jinja2 template (`src/templates/`) + WeasyPrint → PDF
7. **Store** → `src/db.py` — upsert to Supabase (skipped with `--no-db`)

### Tool Contract

Every audit tool in `tools/` follows the contract defined in `tools/base.py`:

```python
def audit(url: str, html: str, config: dict | None = None) -> AuditResult

# AuditResult = {"tool": str, "url": str, "score": 0-100|None, "issues": list[AuditIssue], "data": dict}
# AuditIssue  = {"severity": "critical"|"high"|"medium"|"low", "type": str, "detail": str}
```

Use `make_result()` to construct results and `validate_result()` to verify structure. New tools plug in by following this contract and adding themselves to `AUDIT_TOOLS` in `src/audit.py`.

### 12 Audit Tools

`onpage_auditor` · `indexation_auditor` · `link_auditor` · `image_auditor` · `security_auditor` · `cwv_auditor` · `js_render_auditor` · `structured_data_auditor` · `authority_auditor` · `aeo_auditor` · `gsc_auditor` · `ga_auditor`

### Database

Schema: `migrations/001_initial_schema.sql` (5 tables: sites, audit_runs, page_results, audit_findings, reports). Use `--no-db` for local-only mode — reports save to `.tmp/reports/`.

---

## Connected Integrations

| Service | Role |
|---------|------|
| Supabase | Postgres database + file storage (sites, audits, reports) |
| Claude API | AI-powered analysis, content generation, recommendations |
| Google APIs (TBD) | Search Console, Analytics, PageSpeed data |
| ClickUp | Task management for SEO action items |

---

## File Structure

```
workflows/       # Markdown SOPs (one per workflow)
tools/           # Audit tool modules (deterministic Python scripts)
src/             # CLI orchestrator, aggregator, AI analyzer, report generator, DB client
src/templates/   # Jinja2 HTML + CSS for PDF reports
migrations/      # Supabase SQL schema
tests/           # pytest tests (one per tool + integration tests)
tests/fixtures/  # Sample HTML pages, mock API responses
.claude/skills/  # Skill definitions (one SKILL.md per skill, loaded by Claude Code)
references/      # Context docs and preserved guidelines
files/           # Data files, handoffs, briefs
.tmp/            # Temporary processing files (disposable, regenerable)
```

**Project-local rule:** ALL project assets live in THIS project directory —
not at the global `~/.claude/` level. This includes:
- **Skills** → `.claude/skills/` (Claude Code loads from here)
- **Tools** → `tools/`
- **Workflows** → `workflows/`
- **References** → `references/`
- **Design specs** → `docs/superpowers/specs/`

Everything in `.tmp/` is disposable. Final deliverables live in cloud services.

---

## Development Rules

### Rule 1: Read First
Before any action, read `CLAUDE.md` and `project_specs.md`.
If either doesn't exist, create it before proceeding.

### Rule 2: Spec Before Code
Before writing any code, create or update `project_specs.md`:
- What the app does and who uses it
- Tech stack
- Data models and storage locations
- Third-party services
- Definition of "done" for this task

Show the file. Wait for approval. No code before approval.

### Rule 3: Look Before You Create
Check existing files in `tools/` and `workflows/` before building
anything new. If something exists for this task, use it.
If anything is unclear, ask before starting.

### Rule 4: Test Before You Respond
After any code change, run the relevant tests or dev server.
Check happy path AND error path. Verify data passes correctly
between steps. Never say "done" untested.

### Rule 5: Minimize Context
Actively reduce context window usage. Remove redundant files.
Consolidate where possible. If there's a leaner path that
preserves functionality, take it and flag the optimization.

### Rule 6: Research Before Testing
Before proposing any test, check if the answer already exists.
If the data is conclusive, make it a production rule.
Only test variables where the answer depends on YOUR specific audience.

### Rule 7: Capture What Works
After any session, check if the output revealed new patterns,
constraints, or preferences. Update `workflows/` and reference
files. The system must get smarter over time.

### Rule 8: Challenge the Direction
Think critically about every path. If there's a faster, smarter,
or more effective approach, say so. Don't just execute — push back
when you see a better way.

### Rule 9: Quality Gate
Rate every deliverable honestly. No inflated scores.
If it's not ready, say what's wrong and fix it before proceeding.

### Rule 10: Self-Improvement Loop
When something fails:
1. Read the full error and trace
2. Fix the script and retest (check before rerunning paid APIs)
3. Document what you learned in the relevant workflow
4. Verify the fix works
5. Move on with a stronger system

---

## Code Standards

- Python 3.11+ with `|` union type syntax
- Simple, readable code — clarity over cleverness
- One change at a time; don't touch unrelated code
- Build exactly what's needed, nothing more
- All secrets in `.env`, never in code (see `references/response-guidelines.md`)

---

## Core Rule

Do exactly what is asked. Nothing more, nothing less.
If something is unclear, ask before starting.
