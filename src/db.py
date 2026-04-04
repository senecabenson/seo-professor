import os
from supabase import create_client, Client

_client: Client | None = None


def get_client() -> Client:
    """Get or create singleton Supabase client."""
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        _client = create_client(url, key)
    return _client


def reset_client():
    """Reset the singleton client (for testing)."""
    global _client
    _client = None


def upsert_site(domain: str, name: str | None = None, metadata: dict | None = None) -> dict:
    """Insert or update a site by domain. Returns the site record."""
    client = get_client()
    data = {"domain": domain}
    if name:
        data["name"] = name
    if metadata:
        data["metadata"] = metadata
    result = client.table("sites").upsert(data, on_conflict="domain").execute()
    return result.data[0]


def get_site_by_domain(domain: str) -> dict | None:
    """Get a site by domain. Returns None if not found."""
    client = get_client()
    result = client.table("sites").select("*").eq("domain", domain).execute()
    return result.data[0] if result.data else None


def create_audit_run(site_id: str) -> dict:
    """Create a new audit run. Returns the audit_run record."""
    client = get_client()
    result = client.table("audit_runs").insert({"site_id": site_id, "status": "running"}).execute()
    return result.data[0]


def update_audit_run(run_id: str, status: str, pages_crawled: int | None = None,
                     overall_score: int | None = None, summary: dict | None = None) -> dict:
    """Update an audit run's status and results."""
    client = get_client()
    data = {"status": status}
    if pages_crawled is not None:
        data["pages_crawled"] = pages_crawled
    if overall_score is not None:
        data["overall_score"] = overall_score
    if summary is not None:
        data["summary"] = summary
    if status in ("completed", "failed"):
        from datetime import datetime, timezone
        data["completed_at"] = datetime.now(timezone.utc).isoformat()
    result = client.table("audit_runs").update(data).eq("id", run_id).execute()
    return result.data[0]


def insert_page_result(audit_run_id: str, url: str, status_code: int,
                       html_hash: str | None = None) -> dict:
    """Insert a page result. Returns the page_result record."""
    client = get_client()
    data = {"audit_run_id": audit_run_id, "url": url, "status_code": status_code}
    if html_hash:
        data["html_hash"] = html_hash
    result = client.table("page_results").insert(data).execute()
    return result.data[0]


def insert_findings(page_result_id: str, findings: list[dict]) -> list[dict]:
    """Bulk insert audit findings for a page. Each finding is an AuditResult's issue."""
    client = get_client()
    rows = []
    for finding in findings:
        for issue in finding.get("issues", []):
            rows.append({
                "page_result_id": page_result_id,
                "tool": finding["tool"],
                "severity": issue["severity"],
                "issue_type": issue["type"],
                "detail": issue.get("detail", ""),
                "data": finding.get("data", {}),
            })
    if not rows:
        return []
    result = client.table("audit_findings").insert(rows).execute()
    return result.data


def insert_report(audit_run_id: str, ai_analysis: str, recommendations: list[dict],
                  report_url: str) -> dict:
    """Insert a report record. Returns the report record."""
    client = get_client()
    result = client.table("reports").insert({
        "audit_run_id": audit_run_id,
        "ai_analysis": ai_analysis,
        "recommendations": recommendations,
        "report_url": report_url,
    }).execute()
    return result.data[0]


def get_audit_history(domain: str) -> list[dict]:
    """Get audit history for a domain, sorted by date desc."""
    client = get_client()
    site = get_site_by_domain(domain)
    if not site:
        return []
    result = (client.table("audit_runs")
              .select("*")
              .eq("site_id", site["id"])
              .order("started_at", desc=True)
              .execute())
    return result.data
