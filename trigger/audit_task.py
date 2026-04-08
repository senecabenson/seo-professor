"""
Trigger.dev v3 Python task — SEO Professor audit pipeline.

Deploy: npx trigger deploy
Docs:   https://trigger.dev/docs/sdk/python

Environment variables required in Trigger.dev project:
  ANTHROPIC_API_KEY
  SUPABASE_URL
  SUPABASE_KEY
"""

import asyncio
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Add project root to path so src/ and tools/ are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trigger import task, logger  # noqa: E402  (install: pip install trigger.dev)

from src.audit import run_audit, validate_url, extract_domain, store_results
from src.ai_analyzer import format_for_analysis, analyze_with_claude
from src.report_generator import generate_report


@task(id="seo-audit")
async def seo_audit_task(payload: dict):
    """
    Run a full SEO audit and store results in Supabase.

    Payload:
        url (str):          The URL to audit
        max_pages (int):    Max pages to crawl (default 50)
        single_page (bool): Audit only the given URL (default False)

    Returns:
        audit_run_id (str): Supabase audit_run.id
        domain (str):       Audited domain
        pdf_url (str):      Public URL of the generated PDF in Supabase Storage
        aggregated (dict):  Full aggregated audit data
        ai_analysis (dict): Claude's structured analysis
    """
    url = validate_url(payload["url"])
    max_pages = int(payload.get("max_pages", 50))
    single_page = bool(payload.get("single_page", False))
    domain = extract_domain(url)

    logger.info("Starting audit", domain=domain, max_pages=max_pages, single_page=single_page)

    # --- Phase 1: Crawl + Audit ---
    pages_done = 0

    def on_page_audited(n: int):
        nonlocal pages_done
        pages_done = n
        logger.info("Page audited", pages_done=n)

    audit_result = await run_audit(
        url,
        single_page=single_page,
        max_pages=max_pages,
        progress_callback=on_page_audited,
    )
    aggregated = audit_result["aggregated"]
    pages = audit_result["pages"]

    logger.info(
        "Crawl + audit complete",
        pages=aggregated["pages_audited"],
        score=aggregated["site_score"],
    )

    # --- Phase 2: AI Analysis ---
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in Trigger.dev environment")

    analysis_result = format_for_analysis(aggregated, domain)
    logger.info("Running AI analysis via Claude API...")
    ai_analysis = analyze_with_claude(analysis_result["prompt"], api_key)
    logger.info("AI analysis complete")

    # --- Phase 3: Generate PDF ---
    tmp_dir = "/tmp/seo-professor"
    os.makedirs(tmp_dir, exist_ok=True)
    pdf_path = os.path.join(tmp_dir, f"{domain}-audit.pdf")
    generate_report(aggregated, ai_analysis, pdf_path)
    logger.info("PDF generated", path=pdf_path)

    # --- Phase 4: Store in Supabase ---
    try:
        report_url = store_results(domain, aggregated, pages, ai_analysis, pdf_path)
        logger.info("Results stored in Supabase", report_url=report_url)
    except Exception as e:
        logger.error("Supabase storage failed", error=str(e))
        raise

    return {
        "domain": domain,
        "pdf_url": report_url,
        "aggregated": aggregated,
        "ai_analysis": ai_analysis,
    }
