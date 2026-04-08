"""CLI orchestrator for SEO Professor site auditor."""

import argparse
import asyncio
import hashlib
import json
import os
import sys
from collections.abc import Callable
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

load_dotenv()

from tools import (
    crawler,
    onpage_auditor,
    indexation_auditor,
    link_auditor,
    image_auditor,
    security_auditor,
    cwv_auditor,
    js_render_auditor,
    structured_data_auditor,
    authority_auditor,
    aeo_auditor,
    gsc_auditor,
    ga_auditor,
)
from src.aggregator import aggregate
from src.ai_analyzer import format_for_analysis, analyze_with_claude
from src.report_generator import generate_report, upload_report
from src import db

AUDIT_TOOLS = [
    onpage_auditor,
    indexation_auditor,
    link_auditor,
    image_auditor,
    security_auditor,
    cwv_auditor,
    js_render_auditor,
    structured_data_auditor,
    authority_auditor,
    aeo_auditor,
    gsc_auditor,
    ga_auditor,
]

TMP_DIR = ".tmp"
AUDIT_DATA_PATH = os.path.join(TMP_DIR, "audit_data.json")
AI_ANALYSIS_PATH = os.path.join(TMP_DIR, "ai_analysis.json")
DEFAULT_OUTPUT_DIR = os.path.join(TMP_DIR, "reports")


def build_google_clients() -> dict:
    """Build Google Search Console and GA4 API clients from env credentials.

    Returns a dict with gsc_service, ga_client, and ga4_property_id.
    All values are None if GOOGLE_SERVICE_ACCOUNT_JSON is not set.
    """
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    ga4_property_id = os.environ.get("GA4_PROPERTY_ID")
    if not creds_json:
        return {"gsc_service": None, "ga_client": None, "ga4_property_id": None}
    try:
        import json as _json
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        from google.analytics.data_v1beta import BetaAnalyticsDataClient

        creds_data = _json.loads(creds_json)
        creds = Credentials.from_service_account_info(
            creds_data,
            scopes=[
                "https://www.googleapis.com/auth/webmasters.readonly",
                "https://www.googleapis.com/auth/analytics.readonly",
            ],
        )
        gsc_service = build("searchconsole", "v1", credentials=creds)
        ga_client = BetaAnalyticsDataClient(credentials=creds)
        return {"gsc_service": gsc_service, "ga_client": ga_client, "ga4_property_id": ga4_property_id}
    except Exception as exc:
        print(f"Warning: Could not initialize Google API clients: {exc}")
        return {"gsc_service": None, "ga_client": None, "ga4_property_id": None}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SEO Professor — Site Auditor")
    parser.add_argument("url", nargs="?", help="URL to audit")
    parser.add_argument("--single-page", action="store_true", help="Audit single page only (skip crawler)")
    parser.add_argument("--history", metavar="DOMAIN", help="View past audit history for domain")
    parser.add_argument("--max-pages", type=int, default=50, help="Maximum pages to crawl (default: 50)")
    parser.add_argument("--output", help="Custom output path for PDF report")
    parser.add_argument("--no-db", action="store_true", help="Skip Supabase storage")
    # Business context flags for keyword-aware AI analysis
    parser.add_argument("--business-type", metavar="TYPE", help='Industry/business type (e.g. "photo booth rental")')
    parser.add_argument("--location", metavar="LOCATION", action="append", dest="locations",
                        help="Location(s) served — can be repeated for multiple markets")
    parser.add_argument("--keyword", metavar="KEYWORD", action="append", dest="target_keywords",
                        help="Target keyword(s) — can be repeated")
    return parser


def validate_url(url: str) -> str:
    """Validate and normalize URL. Add https:// if no scheme."""
    if not url:
        raise ValueError("URL is required")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")
    return url


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    return urlparse(url).netloc


def audit_page(url: str, html: str, headers: dict | None = None, config: dict | None = None) -> list[dict]:
    """Run all audit tools on a single page. Returns list of AuditResult dicts."""
    full_config = {"headers": headers or {}}
    if config:
        full_config.update(config)
    results = []
    for tool in AUDIT_TOOLS:
        result = tool.audit(url, html, config=full_config)
        results.append(result)
    return results


async def run_audit(
    url: str,
    single_page: bool = False,
    max_pages: int = 50,
    progress_callback: Callable | None = None,
    business_context: dict | None = None,
) -> dict:
    """
    Run the full audit pipeline:
    1. Crawl (or fetch single page)
    2. Run all audit tools on each page
    3. Aggregate results
    Returns dict with 'aggregated', 'pages', and 'business_context' keys.

    progress_callback(n: int) is called after each page is audited.
    Used by web/Trigger.dev mode to report live progress. CLI passes None.

    business_context (optional): dict with keys:
        business_type (str): e.g. "photo booth rental"
        locations (list[str]): e.g. ["San Diego, CA", "Austin, TX"]
        target_keywords (list[str]): e.g. ["photo booth rental San Diego"]
    """
    google_clients = build_google_clients()
    tool_config = {**google_clients, "business_context": business_context or {}}

    if single_page:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            resp = await client.get(url)
            pages = [{"url": url, "status_code": resp.status_code, "html": resp.text, "headers": dict(resp.headers)}]
    else:
        pages = await crawler.crawl(url, config={"max_pages": max_pages})

    # Run audit tools on each page
    all_results: dict[str, list[dict]] = {}
    for page in pages:
        page_results = audit_page(page["url"], page["html"], page.get("headers"), config=tool_config)
        all_results[page["url"]] = page_results
        if progress_callback:
            progress_callback(len(all_results))

    aggregated = aggregate(all_results)
    return {"aggregated": aggregated, "pages": pages, "business_context": business_context or {}}


def save_audit_data(aggregated: dict, analysis_result: dict, domain: str):
    """Save audit data and prompt to .tmp/ files."""
    os.makedirs(TMP_DIR, exist_ok=True)
    with open(AUDIT_DATA_PATH, "w") as f:
        json.dump({"aggregated": aggregated, "analysis": analysis_result}, f, indent=2)


def load_analysis_if_ready() -> dict:
    """Load AI analysis using the best available source — in priority order:

    1. ANTHROPIC_API_KEY is set → call Claude API directly (automated/Trigger.dev mode)
    2. .tmp/ai_analysis.json exists → load it (Claude Code in-session mode:
       Claude Code analyzed the audit data and wrote this file)
    3. Neither → return default analysis (report still generates, no AI summary)

    When running locally through Claude Code: do NOT set ANTHROPIC_API_KEY.
    Claude Code handles the analysis step in-session.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        if os.path.exists(AUDIT_DATA_PATH):
            with open(AUDIT_DATA_PATH) as f:
                data = json.load(f)
            prompt = data.get("analysis", {}).get("prompt", "")
            if prompt:
                print("Running AI analysis via Claude API...")
                return analyze_with_claude(prompt, api_key)
    if os.path.exists(AI_ANALYSIS_PATH):
        with open(AI_ANALYSIS_PATH) as f:
            return json.load(f)
    return _default_analysis()


def _default_analysis() -> dict:
    """Fallback when no AI analysis is provided."""
    return {
        "executive_summary": "AI analysis was not provided. Review the audit data for details.",
        "priority_fixes": [],
        "category_analysis": {},
        "recommendations": [],
    }


def show_history(domain: str):
    """Print audit history for a domain."""
    history = db.get_audit_history(domain)
    if not history:
        print(f"No audit history found for {domain}")
        return
    print(f"\nAudit History for {domain}")
    print("-" * 60)
    for run in history:
        status = run.get("status", "unknown")
        score = run.get("overall_score", "N/A")
        pages = run.get("pages_crawled", "N/A")
        date = run.get("started_at", "unknown")
        print(f"  {date}  |  Score: {score}  |  Pages: {pages}  |  Status: {status}")


def store_results(domain: str, aggregated: dict, pages: list[dict],
                  ai_analysis: dict, report_path: str):
    """Store audit results in Supabase."""
    site = db.upsert_site(domain)
    run = db.create_audit_run(site["id"])

    for page in pages:
        html_hash = hashlib.md5(page["html"].encode()).hexdigest()
        page_result = db.insert_page_result(run["id"], page["url"], page["status_code"], html_hash)
        page_data = aggregated.get("pages", {}).get(page["url"])
        if page_data and page_data.get("tool_results"):
            findings = [
                {"tool": tool, "issues": data.get("issues", []), "data": data.get("data", {})}
                for tool, data in page_data["tool_results"].items()
            ]
            db.insert_findings(page_result["id"], findings)

    report_url = upload_report(report_path, run["id"])
    db.insert_report(
        run["id"],
        ai_analysis.get("executive_summary", ""),
        ai_analysis.get("recommendations", []),
        report_url,
    )
    db.update_audit_run(
        run["id"],
        status="completed",
        pages_crawled=aggregated.get("pages_audited", 0),
        overall_score=aggregated.get("site_score", 0),
        summary={"severity_counts": aggregated.get("severity_counts", {})},
    )
    return report_url


def main(args=None):
    parser = build_parser()
    parsed = parser.parse_args(args)

    # History mode
    if parsed.history:
        show_history(parsed.history)
        return

    # Audit mode — URL is required
    if not parsed.url:
        parser.error("URL is required (or use --history <domain>)")

    url = validate_url(parsed.url)
    domain = extract_domain(url)

    business_context = {}
    if parsed.business_type:
        business_context["business_type"] = parsed.business_type
    if parsed.locations:
        business_context["locations"] = parsed.locations
    if parsed.target_keywords:
        business_context["target_keywords"] = parsed.target_keywords

    print(f"Starting audit of {domain}...")
    if business_context:
        print(f"Business context: {business_context}")

    # Step 1: Crawl + Audit
    result = asyncio.run(run_audit(
        url,
        single_page=parsed.single_page,
        max_pages=parsed.max_pages,
        business_context=business_context or None,
    ))
    aggregated = result["aggregated"]
    pages = result["pages"]

    print(f"Audited {aggregated['pages_audited']} pages. Site score: {aggregated['site_score']}/100")

    # Step 2: Format for AI analysis
    analysis_result = format_for_analysis(aggregated, domain, business_context=business_context or None)
    print("\n" + analysis_result["prompt"])

    # Step 3: Save audit data, load AI analysis from best available source
    save_audit_data(aggregated, analysis_result, domain)
    ai_analysis = load_analysis_if_ready()

    if ai_analysis == _default_analysis():
        print(
            f"\nNo AI analysis available. Report will be generated without AI summary.\n"
            f"  • Automated mode: set ANTHROPIC_API_KEY in your environment\n"
            f"  • Claude Code mode: analyze in-session and write {AI_ANALYSIS_PATH}"
        )

    # Step 4: Generate report
    if parsed.output:
        output_path = parsed.output
    else:
        os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(DEFAULT_OUTPUT_DIR, f"{domain}-audit.pdf")

    generate_report(aggregated, ai_analysis, output_path)
    print(f"\nReport saved to: {output_path}")

    # Step 5: Store in Supabase (unless --no-db)
    if not parsed.no_db:
        try:
            report_url = store_results(domain, aggregated, pages, ai_analysis, output_path)
            print(f"Report uploaded: {report_url}")
        except Exception as e:
            print(f"Warning: Could not store in Supabase: {e}")
            print("Results saved locally. Use --no-db to suppress this warning.")

    print("\nAudit complete!")


if __name__ == "__main__":
    main()
