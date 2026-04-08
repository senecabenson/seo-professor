#!/usr/bin/env python3
"""
Python subprocess entry point for the Trigger.dev TypeScript task.

Called by trigger/audit_task.ts as:
    python3 trigger/run_audit.py '<json payload>'

Runs the full 4-phase audit pipeline and prints the result as JSON to stdout.
All progress/debug output goes to stderr so stdout stays clean for JSON parsing.
"""

import asyncio
import json
import os
import sys

# Add project root to Python path so src/ and tools/ are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from src.audit import run_audit, validate_url, extract_domain, store_results
from src.ai_analyzer import format_for_analysis, analyze_with_claude
from src.report_generator import generate_report


def log(msg: str):
    """Write progress messages to stderr so stdout stays clean for JSON."""
    print(msg, file=sys.stderr, flush=True)


async def main():
    payload = json.loads(sys.argv[1])
    url = validate_url(payload["url"])
    max_pages = int(payload.get("max_pages", 50))
    single_page = bool(payload.get("single_page", False))
    domain = extract_domain(url)
    business_context = payload.get("business_context") or {}

    log(f"[run_audit] Starting audit: {domain}")

    # Phase 1: Crawl + Audit
    audit_result = await run_audit(
        url,
        single_page=single_page,
        max_pages=max_pages,
        business_context=business_context or None,
    )
    aggregated = audit_result["aggregated"]
    pages = audit_result["pages"]
    log(f"[run_audit] Crawl complete: {aggregated['pages_audited']} pages, score {aggregated['site_score']}")

    # Phase 2: AI Analysis
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    analysis_result = format_for_analysis(
        aggregated, domain, business_context=business_context or None
    )
    log("[run_audit] Running AI analysis via Claude API...")
    ai_analysis = analyze_with_claude(analysis_result["prompt"], api_key)
    log("[run_audit] AI analysis complete")

    # Phase 3: Generate PDF
    tmp_dir = "/tmp/seo-professor"
    os.makedirs(tmp_dir, exist_ok=True)
    pdf_path = os.path.join(tmp_dir, f"{domain}-audit.pdf")
    generate_report(aggregated, ai_analysis, pdf_path)
    log(f"[run_audit] PDF generated: {pdf_path}")

    # Phase 4: Store in Supabase
    report_url = store_results(domain, aggregated, pages, ai_analysis, pdf_path)
    log(f"[run_audit] Stored in Supabase: {report_url}")

    result = {
        "domain": domain,
        "pdf_url": report_url,
        "aggregated": aggregated,
        "ai_analysis": ai_analysis,
    }

    # Print JSON to stdout — this is what the TypeScript task reads
    print(json.dumps(result))


asyncio.run(main())
