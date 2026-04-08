# Site Remediator — Revised Design Spec

## Purpose

A remediation engine that consumes Site Auditor findings, generates fixes, applies approved changes to local project files, and validates results through targeted re-audit. Built to run inside Claude Code sessions where Claude has direct file access. Pairs with the Site Auditor but operates independently — the auditor diagnoses, the remediator treats.

## Relationship to Site Auditor

The remediator reads from the auditor's database. The auditor never knows the remediator exists. Both share the same Supabase backend.

```
Site Auditor (read-only, safe to run anytime)
       |
       | writes: audit_findings, page_results, audit_runs
       v
    Supabase (shared backend)
       |
       | reads: audit_findings for a given audit_run_id
       v
Site Remediator (writes files, requires approval)
       |
       | triggers: targeted audit tool re-runs for validation
       v
Site Auditor tools (re-run to confirm fixes)
```

---

## Architecture: Two Modes

```
                            SITE AUDITOR (existing)
                                    |
                    audit_findings + page_results
                                    |
                                    v
                        +-------------------+
                        | project_mapper.py |  <-- NEW: URL-to-file mapping
                        +-------------------+
                           |             |
                    has local files   no local files
                           |             |
                    +------+------+      +---> recommendation-only mode
                    |             |             (diffs against fetched HTML)
                    v             v
            +------------+  +---------------+
            |  MODE A    |  |   MODE B      |
            | Claude     |  | CLI Pipeline  |
            | in-session |  | (future)      |
            +------------+  +---------------+
                    |             |
                    v             v
            Claude reads    tools/generators/*.py
            local files,    produce FixResult dicts
            applies fixes        |
            directly             v
                    |       interactive review
                    |       (approve/reject/edit)
                    |             |
                    v             v
            +----------------------------+
            |    validator.py            |
            |    (local file content)    |
            +----------------------------+
                          |
                          v
                   remediation_runs table
```

### Mode A — "Claude in-session" (MVP, ships first)

Claude Code IS the remediation engine. The `site-remediator` skill provides structured instructions. Claude reads audit findings from `.tmp/audit_data.json` or the database, reads local source files directly, applies fixes using standard file editing, and validates by reading the modified content back through the relevant audit tool's logic. No CLI pipeline, no generator scripts, no interactive review UI.

**Why this is the MVP:** Claude already understands HTML, SEO best practices, and the audit tool contracts. Writing 22 generator scripts to do what Claude does natively is premature engineering. Mode A proves which fix patterns work, establishes the data model, and delivers value immediately.

### Mode B — "Standalone CLI" (future)

A full `python -m src.remediate` pipeline with argparse, generator scripts in `tools/generators/`, interactive approve/reject review, and batch processing. Build this when: (1) Mode A has been used on 5+ sites, (2) fix patterns are stable, (3) there is a need for unattended/automated remediation.

---

## URL-to-File Mapping (`tools/project_mapper.py`)

### The Problem

The auditor crawls `https://example.com/about` but the remediator needs to edit local files like `src/pages/about.html`. No mapping mechanism exists.

### Design

```python
# tools/project_mapper.py

from typing import TypedDict, Literal

class ProjectMapping(TypedDict):
    framework: str                    # "nextjs" | "hugo" | "static" | "unknown"
    base_url: str                     # "https://example.com"
    project_root: str                 # "/Users/seneca/projects/mysite"
    url_map: dict[str, str | None]    # URL -> local file path (None = no local file)
    mode: Literal["local", "recommendation"]

def detect_framework(project_root: str) -> str:
    """Detect framework from config files in project_root."""
    ...

def build_url_map(
    project_root: str,
    framework: str,
    base_url: str,
    urls: list[str],
) -> dict[str, str | None]:
    """Map audit URLs to local file paths based on framework routing rules."""
    ...

def map_project(
    project_root: str,
    base_url: str,
    urls: list[str],
) -> ProjectMapping:
    """Main entry point: detect framework, build mapping, determine mode."""
    ...
```

### Framework Detection Rules

| Config File | Framework | Routing Pattern |
|---|---|---|
| `next.config.js` or `next.config.mjs` | Next.js | `app/page.tsx` or `pages/*.tsx` -> URL path segments |
| `hugo.toml` or `hugo.yaml` | Hugo | `content/**/*.md` -> URL path from front matter or directory |
| `astro.config.mjs` | Astro | `src/pages/*.astro` -> URL path segments |
| `gatsby-config.js` | Gatsby | `src/pages/*.tsx` -> URL path segments |
| `_config.yml` (with `jekyll`) | Jekyll | `_posts/*.md` + pages -> URL from permalink config |
| `*.html` in root or `/public` | Static HTML | Direct path mapping: URL path = file path |
| None of the above | Unknown | Falls back to recommendation-only mode |

### Mode Decision

- If `framework != "unknown"` AND local files resolve for at least 1 URL: `mode = "local"`
- If `framework == "unknown"` OR no local files resolve: `mode = "recommendation"`

In recommendation-only mode, the remediator generates unified diffs against the fetched HTML (stored in `page_results.html` after schema migration). The user applies these manually.

The mapping is stored in the `remediation_runs` table as `project_mapping jsonb`.

---

## Data Model Fixes

### Problem

Generators/Claude need data that `audit_findings` does not currently store. Current schema: `tool`, `severity`, `issue_type`, `detail`, `data jsonb`. Missing: full HTML, DOM location, local file path.

### Solution

**Change 1: Store full HTML in `page_results`**

The crawler already captures full HTML but `src/audit.py` only stores an MD5 hash. Add an `html` column. In `store_results()`, pass `html=page["html"]` to `insert_page_result`.

**Change 2: Add `dom_context` to `audit_findings`**

An optional field telling generators/Claude exactly where in the DOM the issue lives. CSS selector, line range, or element identifier. Audit tools populate it when they can.

Example values:
- `"head > title"` for a missing/bad title
- `"head > meta[name='description']"` for meta description issues
- `"img:nth-of-type(3)"` for an image missing alt text
- `"h1:first-of-type"` for H1 issues
- `null` when DOM location is not applicable (e.g., missing robots.txt)

Additive change — existing audit tools continue to work. The `dom_context` field is populated incrementally as tools are updated.

**Change 3: For Mode A, no extra storage needed**

Claude reads local files directly via the file system. The `dom_context` field helps Claude locate the issue faster, but Claude can also search file content using `detail` and `issue_type`.

---

## Database Schema Additions

Migration: `migrations/002_remediation_schema.sql`

```sql
-- Add full HTML storage to page_results
ALTER TABLE page_results ADD COLUMN IF NOT EXISTS html text;

-- Add DOM context to audit_findings for targeted remediation
ALTER TABLE audit_findings ADD COLUMN IF NOT EXISTS dom_context text;

-- remediation_runs: tracks a remediation session
CREATE TABLE IF NOT EXISTS remediation_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_run_id uuid REFERENCES audit_runs(id) ON DELETE CASCADE,
    site_id uuid REFERENCES sites(id) ON DELETE CASCADE,
    started_at timestamptz DEFAULT now(),
    completed_at timestamptz,
    status text NOT NULL DEFAULT 'running',
    mode text NOT NULL DEFAULT 'local',
    project_mapping jsonb DEFAULT '{}'::jsonb,
    config jsonb DEFAULT '{}'::jsonb,
    summary jsonb DEFAULT '{}'::jsonb
);

-- remediation_fixes: individual fix records
CREATE TABLE IF NOT EXISTS remediation_fixes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    remediation_run_id uuid REFERENCES remediation_runs(id) ON DELETE CASCADE,
    finding_id uuid REFERENCES audit_findings(id) ON DELETE SET NULL,
    generator text NOT NULL,
    file_path text,
    url text NOT NULL,
    fix_type text NOT NULL,
    status text NOT NULL DEFAULT 'pending',
    diff text,
    description text,
    validated_at timestamptz,
    validation_result jsonb,
    created_at timestamptz DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_remediation_runs_audit_run_id
    ON remediation_runs(audit_run_id);
CREATE INDEX IF NOT EXISTS idx_remediation_runs_site_id
    ON remediation_runs(site_id);
CREATE INDEX IF NOT EXISTS idx_remediation_fixes_run_id
    ON remediation_fixes(remediation_run_id);
CREATE INDEX IF NOT EXISTS idx_remediation_fixes_finding_id
    ON remediation_fixes(finding_id);
```

---

## Fix Generator Contract (`tools/generators/base.py`)

Mirrors the pattern from `tools/base.py` for audit tools.

```python
from typing import TypedDict, Literal

VALID_FIX_TYPES = {"auto", "semi_auto", "manual", "recommendation"}

class FixResult(TypedDict):
    generator: str
    url: str
    file_path: str | None
    fix_type: Literal["auto", "semi_auto", "manual", "recommendation"]
    applied: bool
    diff: str | None
    description: str
    issues_addressed: list[str]   # list of issue_type strings this fix covers
    new_content: str | None       # full file content after fix (for auto mode)

def validate_fix(result: dict) -> bool: ...
def make_fix(...) -> FixResult: ...
```

### Generator Interface (Mode B)

```python
def generate(
    url: str,
    html: str,
    findings: list[dict],
    file_path: str | None,
    file_content: str | None,
    config: dict | None = None,
) -> FixResult:
    """Generate a fix. Does NOT write to disk."""
    ...
```

Key rules:
- Generators NEVER write to disk — return `new_content` and `diff`
- Generators NEVER modify content outside their scope
- Generators operate on `file_content` when available, falling back to `html`
- The `findings` list is pre-filtered to only relevant findings

---

## Complete Generator List (4 Phases)

### Phase 1 — MVP Scope (auto, low risk, high frequency)

| Generator | Source Audit Tool | Issue Types |
|---|---|---|
| `meta_fixer` | onpage_auditor | missing_title, title_too_long/short, missing_meta_description, description_too_long/short |
| `schema_fixer` | structured_data_auditor | no_structured_data, missing_schema_property, invalid_json_ld |
| `heading_fixer` | onpage_auditor, aeo_auditor | missing_h1, multiple_h1, heading_hierarchy_skip |
| `robots_fixer` | indexation_auditor, onpage_auditor | noindex_meta, noindex_detected, nofollow_detected (unintentional) |

**In Mode A, Claude doesn't need these scripts.** The phases define which fix CATEGORIES are supported, not which scripts exist.

### Phase 2 — Auto Generators (broader scope)

| Generator | Source | Issue Types | Fix Type |
|---|---|---|---|
| `canonical_fixer` | indexation_auditor, onpage_auditor | missing_canonical, canonical_mismatch | auto |
| `image_alt_fixer` | image_auditor | missing_alt_text, empty_alt_text | semi_auto |
| `og_tags_fixer` | onpage_auditor | missing_og_tags, missing_twitter_tags | auto |
| `security_headers_fixer` | security_auditor | missing_hsts, missing_csp, missing_x_frame | auto |
| `lazy_loading_fixer` | image_auditor | missing_lazy_loading, missing_image_dimensions | auto |

### Phase 3 — Semi-Auto Generators

| Generator | Source | Issue Types | Fix Type |
|---|---|---|---|
| `redirect_fixer` | indexation_auditor | redirect_302, meta_refresh_redirect | semi_auto |
| `link_fixer` | link_auditor | broken_internal_link, empty_anchor_text | semi_auto |
| `mixed_content_fixer` | security_auditor | mixed_content | semi_auto |
| `hreflang_fixer` | indexation_auditor | missing_self_hreflang, invalid_hreflang_code | semi_auto |
| `sitemap_fixer` | indexation_auditor | missing_from_sitemap, sitemap_stale | semi_auto |
| `image_format_fixer` | image_auditor | not_webp_format, oversized_image | semi_auto |
| `word_count_advisor` | onpage_auditor | low_word_count | semi_auto |
| `eeat_advisor` | authority_auditor | missing_author_info, missing_about_link, missing_contact_link | semi_auto |
| `aeo_advisor` | aeo_auditor | low_direct_answer_ratio, no_question_headings, missing_statistics | semi_auto |

### Phase 4 — Assisted Manual Generators

| Generator | Source | Issue Types | Fix Type |
|---|---|---|---|
| `content_optimizer` | aeo_auditor, onpage_auditor | thin_content, poor_keyword_alignment | manual |
| `js_render_advisor` | js_render_auditor | spa_detected, no_noscript_fallback, heavy_js | manual |
| `structured_data_advisor` | structured_data_auditor | wrong_schema_type, ai_bot_governance | manual |
| `link_equity_advisor` | link_auditor | orphan_page, poor_internal_linking | manual |

**Total: 22 generators across 4 phases.**

---

## Mode A: Skill-Driven Flow (MVP)

### Workflow

```
User: "Fix the SEO issues found in the last audit"
  |
  v
Claude reads .tmp/audit_data.json
  |
  v
Claude runs: python -c "from tools.project_mapper import map_project; ..."
  |
  v
Claude gets ProjectMapping with url_map
  |
  v
For each finding (severity desc):
  +-> Claude reads local file via Read tool
  +-> Claude proposes fix with explanation
  +-> User approves / rejects / edits
  +-> Claude applies fix via Edit tool
  +-> Claude validates: runs audit tool logic on new content
  +-> Claude logs to .tmp/remediation_log.json
  |
  v
Claude prints summary: N fixes applied, M skipped, K validated
```

### `.tmp/remediation_log.json` Structure

```json
{
  "started_at": "2026-04-07T10:00:00Z",
  "project_root": "/Users/seneca/projects/mysite",
  "framework": "nextjs",
  "mode": "local",
  "fixes": [
    {
      "url": "https://example.com/about",
      "file_path": "src/pages/about.tsx",
      "issue_type": "missing_meta_description",
      "tool": "onpage_auditor",
      "severity": "high",
      "status": "applied",
      "description": "Added meta description: 'About our company...'",
      "validated": true
    }
  ],
  "summary": {
    "total_findings": 42,
    "fixes_applied": 18,
    "fixes_skipped": 20,
    "fixes_failed": 0,
    "validated_pass": 18,
    "validated_fail": 0
  }
}
```

---

## Mode B: CLI Entry Point (Future)

### `src/remediate.py`

```python
import argparse

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SEO Professor -- Site Remediator")
    parser.add_argument("project_root", help="Path to the local project directory")
    parser.add_argument("--audit-run", help="Audit run ID to remediate (default: latest)")
    parser.add_argument("--base-url", help="Base URL of the site (overrides detection)")
    parser.add_argument("--severity", default="high",
                        choices=["critical", "high", "medium", "low"],
                        help="Minimum severity to fix (default: high)")
    parser.add_argument("--tools", nargs="+",
                        help="Only fix issues from these audit tools")
    parser.add_argument("--auto-apply", action="store_true",
                        help="Apply auto fixes without confirmation")
    parser.add_argument("--dry-run", action="store_true",
                        help="Generate diffs but don't apply")
    parser.add_argument("--no-db", action="store_true",
                        help="Skip Supabase storage")
    parser.add_argument("--no-backup", action="store_true",
                        help="Skip git stash backup")
    parser.add_argument("--rollback", action="store_true",
                        help="Rollback last remediation (git stash pop)")
    return parser
```

### Pipeline

```
1. Parse args, validate project_root exists
2. project_mapper.map_project() -> ProjectMapping
3. Load findings (from DB or .tmp/audit_data.json)
4. Filter by severity threshold and tool whitelist
5. Group findings by URL
6. For each URL:
   a. Read local file (or fetched HTML in recommendation mode)
   b. Run applicable generators
   c. Present diffs for review (unless --auto-apply)
   d. Apply approved fixes
   e. Run validator on modified content
7. Print summary
8. Store remediation_run in DB (unless --no-db)
```

---

## Validation Approach

The validator reads local file content and passes it to the audit tool's `audit(url, html)` function. The URL is just a label — the HTML content is what matters. No need to re-fetch the live URL.

```python
# src/validator.py

TOOL_MAP = {
    "onpage_auditor": onpage_auditor,
    "indexation_auditor": indexation_auditor,
    # ... all 10 tools
}

def validate_fix(
    tool_name: str,
    url: str,
    file_path: str,
    original_findings: list[dict],
) -> dict:
    """Re-run an audit tool on local file content after a fix."""
    with open(file_path) as f:
        html = f.read()

    tool = TOOL_MAP.get(tool_name)
    result = tool.audit(url, html)

    original_types = {f["issue_type"] for f in original_findings}
    remaining_types = {i["type"] for i in result["issues"]}
    fixed = original_types - remaining_types
    still_present = original_types & remaining_types

    return {
        "passed": len(still_present) == 0,
        "score_after": result["score"],
        "fixed_issues": list(fixed),
        "remaining_issues": [i for i in result["issues"] if i["type"] in still_present],
        "new_issues": [i for i in result["issues"] if i["type"] not in original_types],
    }
```

---

## Safety and Rollback

### Before Any Remediation

1. **Git check**: If `project_root` is a git repo with uncommitted changes, warn. Offer to stash or commit first.
2. **Backup**: Create a git stash: `git stash push -m "seo-professor-remediation-backup-{timestamp}"`
3. **Dry-run default** (Mode B): First run shows diffs. Re-run with `--auto-apply` to commit changes.

### During Remediation

4. **Atomic per-file**: Each file modified independently. If a fix fails validation, that file is reverted.
5. **Diff logging**: Every change recorded in `remediation_fixes.diff` and `.tmp/remediation_log.json`.

### After Remediation

6. **Rollback**: `python -m src.remediate --rollback` pops the stash.
7. **Partial rollback**: Individual files via `git checkout -- <file_path>`.

### Scope Limits

- Will not modify files outside `project_root`
- Will not delete files
- Will not modify server configuration (nginx, Apache) — recommendation-only
- Will not modify database content (CMS content stored in DB)
- Will not run build commands — user's responsibility after review

---

## File Structure

```
tools/
  generators/
    __init__.py
    base.py                     # FixResult TypedDict, validate_fix(), make_fix()
    meta_fixer.py               # Phase 1
    schema_fixer.py             # Phase 1
    heading_fixer.py            # Phase 1
    robots_fixer.py             # Phase 1
    # Phase 2+ generators added incrementally
  project_mapper.py             # URL-to-file mapping
src/
  remediate.py                  # Mode B CLI orchestrator (future)
  validator.py                  # Re-runs audit tools on fixed content
skills/
  site-remediator/
    SKILL.md                    # Mode A skill definition
workflows/
  site-remediation.md           # SOP for remediation runs
migrations/
  002_remediation_schema.sql    # New tables + column additions
tests/
  test_project_mapper.py
  test_validator.py
  test_meta_fixer.py
  test_schema_fixer.py
  test_heading_fixer.py
  test_robots_fixer.py
  generators/
    fixtures/
      nextjs_project/
      static_project/
      hugo_project/
```

## Dependencies

No new dependencies for Phase 1. Uses existing stack:
- `beautifulsoup4` — HTML parsing in generators
- `difflib` (stdlib) — unified diff generation
- `pathlib` (stdlib) — file path operations
- `supabase` — DB storage (shared with auditor)
- Git — backup/rollback (graceful degradation if not a git repo)

---

## Implementation Sequencing

```
Task 1: Schema migration (002_remediation_schema.sql)
  + Update db.py with new functions
  + Update src/audit.py to store full HTML
  |
Task 2: tools/project_mapper.py + tests
  |
Task 3: tools/generators/base.py (FixResult contract) + tests
  |
Task 4: src/validator.py + tests
  |
Task 5: skills/site-remediator/SKILL.md
  + workflows/site-remediation.md
  |
Task 6: .tmp/remediation_log.json tracking logic
  |
--- Mode A is usable after Task 6 ---
  |
Task 7-10: Phase 1 generators (can parallelize)
  |
--- Phase 1 generators exist for Mode B foundation ---
  |
Task 11+: Phase 2-4 generators (incremental)
Task N: src/remediate.py CLI orchestrator (Mode B)
```

Tasks 1-6 are the critical path. Mode A is functional after Task 6 with zero generator scripts.

---

## Success Criteria Per Phase

### Phase 1: MVP (Mode A + project_mapper + 4 fix categories)

- [ ] `tools/project_mapper.py` detects static HTML, Next.js, Hugo projects
- [ ] `tools/project_mapper.py` returns `mode = "recommendation"` when no local files found
- [ ] `skills/site-remediator/SKILL.md` guides Claude through Phase 1 fix categories
- [ ] Claude reads audit findings from `.tmp/audit_data.json`
- [ ] Claude creates git backup before modifying files
- [ ] Claude applies and validates: meta tag fixes, heading fixes, schema fixes, robots fixes
- [ ] `.tmp/remediation_log.json` accurately records all actions
- [ ] `migrations/002_remediation_schema.sql` runs without error
- [ ] `src/validator.py` re-runs audit tools on local file content
- [ ] All new code has pytest coverage

### Phase 2: Broader Auto Fixes
- [ ] 5 additional generators implemented and tested
- [ ] Mode A skill updated with Phase 2 categories

### Phase 3: Semi-Auto + Mode B CLI
- [ ] `src/remediate.py` CLI works end-to-end with `--dry-run`
- [ ] Interactive review works in terminal
- [ ] 9 semi-auto generators implemented

### Phase 4: Full Suite
- [ ] All 22 generators implemented
- [ ] Mode B supports `--rollback`
- [ ] Before/after score comparison in summary
