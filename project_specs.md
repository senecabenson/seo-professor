# Project Specs: SEO Professor

## What It Does
A personal full-stack SEO suite that combines website auditing, content optimization, keyword rank tracking, and reporting into a single AI-powered system. Built for Seneca's own SEO work across multiple projects.

## Who Uses It
Seneca Benson — personal tool for managing SEO across projects (The Capture Corner, NILE Growth Works, client work, etc.)

## Core Capabilities
1. **Site Auditing** — crawl pages, check technical SEO (meta tags, headings, page speed, mobile-friendliness, broken links, structured data)
2. **Content Optimization** — analyze content against target keywords, suggest improvements, generate SEO-optimized drafts
3. **Rank Tracking** — monitor keyword positions over time, track competitors, alert on significant changes
4. **Reporting** — generate SEO performance reports, track progress, surface actionable insights

## Tech Stack
- **Language:** Python
- **AI:** Claude API via `anthropic` SDK (analysis, content generation, recommendations)
- **Data:** TBD (local SQLite for MVP, migrate if needed)
- **Integrations:** TBD — will add as capabilities are built (Google Search Console, Analytics, PageSpeed, third-party SEO APIs)

## Data Models
TBD — will define as each capability is built. Expected entities:
- Sites (domains being tracked)
- Pages (individual URLs)
- Keywords (target keywords per site/page)
- Audits (audit results with timestamps)
- Rankings (keyword position snapshots)
- Reports (generated reports)

## Third-Party Services
TBD — integrations will be added incrementally:
- Google Search Console API
- Google Analytics API
- Google PageSpeed Insights API
- Potential: Ahrefs, SEMrush, or Moz APIs for backlink/keyword data

## Definition of Done (Project Initialization)
- [x] CLAUDE.md configured with project-specific values
- [x] Directory structure created (workflows/, tools/, skills/, src/, references/, files/, .tmp/)
- [x] project_specs.md created and approved
- [x] .env file created with placeholder keys
- [x] .gitignore configured
- [x] Git repository initialized
- [x] SEO skills installed (seo-audit, seo-optimizer)
- [x] First capability scoped and ready to build
