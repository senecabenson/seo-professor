"""Google Search Console auditor — queries real search ranking data per page."""

from __future__ import annotations

import os
from datetime import date, timedelta
from urllib.parse import urlparse

from tools.base import make_result

TOOL = "gsc_auditor"

# CTR benchmarks by average position (industry averages)
_CTR_BENCHMARKS = {
    1: 0.28,   # position 1 → ~28% CTR expected
    2: 0.15,
    3: 0.11,
    4: 0.08,
    5: 0.06,
    6: 0.05,
    7: 0.04,
    8: 0.03,
    9: 0.025,
    10: 0.022,
}


def _expected_ctr(avg_position: float) -> float:
    """Return expected CTR for a given average position."""
    pos = max(1, min(10, round(avg_position)))
    return _CTR_BENCHMARKS.get(pos, 0.02)


def audit(url: str, html: str, config: dict | None = None) -> dict:
    config = config or {}
    service = config.get("gsc_service")

    if service is None:
        return make_result(
            tool=TOOL,
            url=url,
            score=None,
            issues=[{
                "severity": "low",
                "type": "skipped",
                "detail": "GSC audit skipped — GOOGLE_SERVICE_ACCOUNT_JSON not set",
            }],
        )

    domain = urlparse(url).netloc
    site_url = f"https://{domain}/"

    end_date = date.today()
    start_date = end_date - timedelta(days=28)

    try:
        response = service.searchanalytics().query(
            siteUrl=site_url,
            body={
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "dimensions": ["query"],
                "dimensionFilterGroups": [{
                    "filters": [{
                        "dimension": "page",
                        "operator": "equals",
                        "expression": url,
                    }]
                }],
                "rowLimit": 10,
            }
        ).execute()
    except Exception as exc:
        return make_result(
            tool=TOOL,
            url=url,
            score=None,
            issues=[{
                "severity": "high",
                "type": "api_error",
                "detail": f"GSC API error: {exc}",
            }],
        )

    rows = response.get("rows", [])
    if not rows:
        return make_result(
            tool=TOOL,
            url=url,
            score=50,
            issues=[{
                "severity": "medium",
                "type": "no_gsc_data",
                "detail": "No search data found for this page — it may not be indexed or ranking for any queries yet.",
            }],
            data={"impressions": 0, "clicks": 0, "ctr": 0.0, "avg_position": None, "top_queries": []},
        )

    # Aggregate across all queries for this page
    total_impressions = sum(r.get("impressions", 0) for r in rows)
    total_clicks = sum(r.get("clicks", 0) for r in rows)
    ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0.0
    avg_position = (
        sum(r.get("position", 10) * r.get("impressions", 1) for r in rows) /
        max(total_impressions, 1)
    )

    top_queries = [
        {
            "query": r["keys"][0],
            "impressions": r.get("impressions", 0),
            "clicks": r.get("clicks", 0),
            "position": round(r.get("position", 0), 1),
        }
        for r in rows[:5]
    ]

    issues: list[dict] = []
    score = 100

    # Low impressions — ranking but barely visible
    if total_impressions < 50:
        issues.append({
            "severity": "medium",
            "type": "low_impressions",
            "detail": f"Only {total_impressions} impressions in the last 28 days — this page has very low search visibility.",
        })
        score -= 20

    # Poor CTR relative to ranking position
    if total_impressions >= 20:
        ctr_decimal = ctr / 100
        expected = _expected_ctr(avg_position)
        if ctr_decimal < expected * 0.5:
            issues.append({
                "severity": "high",
                "type": "poor_ctr",
                "detail": (
                    f"CTR is {ctr:.1f}% at avg position {avg_position:.1f} — "
                    f"expected ~{expected * 100:.0f}%. "
                    "Your title or description may not be compelling enough to get clicks."
                ),
            })
            score -= 30
        elif ctr_decimal < expected * 0.75:
            issues.append({
                "severity": "medium",
                "type": "below_average_ctr",
                "detail": (
                    f"CTR is {ctr:.1f}% at avg position {avg_position:.1f} "
                    f"(below average of ~{expected * 100:.0f}% for this ranking)."
                ),
            })
            score -= 15

    # Check if location-specific queries are represented (uses business context)
    locations = config.get("business_context", {}).get("locations", [])
    if locations:
        query_texts = [q["query"].lower() for q in top_queries]
        any_local = any(
            any(loc.lower().split(",")[0] in q for q in query_texts)
            for loc in locations
        )
        if not any_local and total_impressions > 0:
            location_names = ", ".join(loc.split(",")[0] for loc in locations)
            issues.append({
                "severity": "medium",
                "type": "missing_local_queries",
                "detail": (
                    f"None of your top ranking queries include location terms ({location_names}). "
                    "Local keyword optimization may be missing on this page."
                ),
            })
            score -= 10

    score = max(0, min(100, score))

    return make_result(
        tool=TOOL,
        url=url,
        score=score,
        issues=issues,
        data={
            "impressions": total_impressions,
            "clicks": total_clicks,
            "ctr": round(ctr, 2),
            "avg_position": round(avg_position, 1),
            "top_queries": top_queries,
        },
    )
