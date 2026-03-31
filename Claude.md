# CLAUDE.md

## Project Overview
A personal full-stack SEO suite that combines website auditing, content optimization, keyword rank tracking, and reporting into a single AI-powered system. Built for Seneca's SEO work across multiple projects.

## Connected Integrations
| Service | Role |
|---------|------|
| Supabase | Postgres database + file storage (sites, audits, reports) |
| Claude API | AI-powered analysis, content generation, recommendations |
| Google APIs (TBD) | Search Console, Analytics, PageSpeed data |
| ClickUp | Task management for SEO action items |

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

## How to Respond

Every response includes:
- **What I just did** — plain English
- **What you need to do** — step by step
- **Why** — one sentence on what it does or why it matters
- **Next step** — one clear action
- **Errors** — if something broke, explain simply and say how to fix it

---

## File Structure

workflows/       # Markdown SOPs (one per workflow)
tools/           # Python scripts for deterministic execution
skills/          # Skill definitions (one SKILL.md per skill)
src/             # Application source code
references/      # Context docs Claude reads for grounding
files/           # Data files, handoffs, briefs
.tmp/            # Temporary processing files (disposable, regenerable)
.env             # API keys and secrets (NEVER commit)
CLAUDE.md        # This file — system operating instructions
project_specs.md # What's being built and definition of done

**Project-local rule:** ALL project assets live in THIS project directory —
not at the global `~/.claude/` level. This includes:
- **Skills** → `skills/` (not `.claude/skills/`)
- **Tools** → `tools/`
- **Workflows** → `workflows/`
- **References** → `references/`
- **Config** → project-level `.claude/` only for Claude Code internals

When installing external skills/templates, always copy them into the
project root directories so they're visible in the project dropdown.
Everything this project creates or uses should be self-contained here.

**Core principle:** Local files are for processing.
Final deliverables live in cloud services where stakeholders access them.
Everything in `.tmp/` is disposable.

---

## Code Standards

- Simple, readable code — clarity over cleverness
- One change at a time
- Don't touch code unrelated to the current task
- Build exactly what's needed, nothing more
- Never put API keys in code
- Never commit `.env`
- Ask before deleting or renaming important files

---

## Tech Stack

- **Language:** Python 3.11+
- **AI:** Claude in-session analysis (MVP), Claude API for future standalone mode
- **Data:** Supabase (Postgres + Storage)
- **Integrations:** Google Search Console, Google Analytics, PageSpeed Insights (TBD)

---

## Secrets & Safety

- All API keys and credentials live in `.env` only
- Never hardcode secrets anywhere in the codebase
- Never commit `.env` or `credentials.json` to version control
- If a script needs a key, it reads from environment variables
- Ask before deleting or renaming any important files

---

## Testing Protocol

Before marking any task as done:
1. Run the relevant script and confirm it exits successfully
2. Check for errors, warnings, or unexpected output
3. Verify existing behavior wasn't broken by the change
4. Test the happy path AND the error path
5. Confirm data passes correctly between steps
6. If it uses paid API calls, check with me before rerunning

Never say "done" if the code is untested.

---

## Core Rule

Do exactly what is asked. Nothing more, nothing less. 
If something is unclear, ask before starting.
