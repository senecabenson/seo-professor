"""Google Analytics 4 auditor — queries real traffic and engagement data per page."""

from __future__ import annotations

from urllib.parse import urlparse

from tools.base import make_result

TOOL = "ga_auditor"


def audit(url: str, html: str, config: dict | None = None) -> dict:
    config = config or {}
    ga_client = config.get("ga_client")
    property_id = config.get("ga4_property_id")

    if ga_client is None or not property_id:
        return make_result(
            tool=TOOL,
            url=url,
            score=None,
            issues=[{
                "severity": "low",
                "type": "skipped",
                "detail": "GA4 audit skipped — GOOGLE_SERVICE_ACCOUNT_JSON or GA4_PROPERTY_ID not set",
            }],
        )

    # GA4 uses the page path, not the full URL
    path = urlparse(url).path or "/"

    try:
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            DimensionFilter,
            Filter,
            FilterExpression,
            Metric,
            RunReportRequest,
        )

        request = RunReportRequest(
            property=property_id,
            dimensions=[Dimension(name="pagePath")],
            metrics=[
                Metric(name="screenPageViews"),
                Metric(name="sessions"),
                Metric(name="bounceRate"),
                Metric(name="averageSessionDuration"),
                Metric(name="organicGoogleSearchSessions"),
            ],
            date_ranges=[DateRange(start_date="28daysAgo", end_date="today")],
            dimension_filter=FilterExpression(
                filter=DimensionFilter(
                    field_name="pagePath",
                    string_filter=Filter.StringFilter(
                        match_type=Filter.StringFilter.MatchType.EXACT,
                        value=path,
                    ),
                )
            ),
        )
        response = ga_client.run_report(request)
    except Exception as exc:
        return make_result(
            tool=TOOL,
            url=url,
            score=None,
            issues=[{
                "severity": "high",
                "type": "api_error",
                "detail": f"GA4 API error: {exc}",
            }],
        )

    if not response.rows:
        return make_result(
            tool=TOOL,
            url=url,
            score=50,
            issues=[{
                "severity": "medium",
                "type": "no_ga_data",
                "detail": "No GA4 data found for this page in the last 28 days — it may have no traffic.",
            }],
            data={
                "pageviews": 0,
                "sessions": 0,
                "bounce_rate": None,
                "avg_session_duration_seconds": None,
                "organic_sessions": 0,
            },
        )

    row = response.rows[0]
    values = [v.value for v in row.metric_values]

    pageviews = int(values[0]) if values[0] else 0
    sessions = int(values[1]) if values[1] else 0
    bounce_rate = float(values[2]) * 100 if values[2] else 0.0   # GA4 returns 0-1
    avg_duration = float(values[3]) if values[3] else 0.0
    organic_sessions = int(values[4]) if len(values) > 4 and values[4] else 0

    issues: list[dict] = []
    score = 100

    # Bounce rate thresholds
    if bounce_rate >= 75:
        issues.append({
            "severity": "high",
            "type": "high_bounce_rate",
            "detail": (
                f"Bounce rate is {bounce_rate:.0f}% — most visitors leave immediately. "
                "This signals that the page isn't matching what visitors expected to find."
            ),
        })
        score -= 30
    elif bounce_rate >= 55:
        issues.append({
            "severity": "medium",
            "type": "elevated_bounce_rate",
            "detail": (
                f"Bounce rate is {bounce_rate:.0f}% (above the 55% benchmark for this content type). "
                "Consider improving the page headline, loading speed, or content match."
            ),
        })
        score -= 15

    # Engagement time thresholds
    if avg_duration < 20:
        issues.append({
            "severity": "high",
            "type": "very_low_engagement_time",
            "detail": (
                f"Average session duration is {avg_duration:.0f}s — visitors are barely reading. "
                "Thin content or a mismatch between headline and body text is a likely cause."
            ),
        })
        score -= 25
    elif avg_duration < 45:
        issues.append({
            "severity": "medium",
            "type": "low_engagement_time",
            "detail": (
                f"Average session duration is {avg_duration:.0f}s. "
                "For a service or product page, aim for at least 45–60 seconds of engagement."
            ),
        })
        score -= 10

    # Very low traffic
    if sessions < 10:
        issues.append({
            "severity": "medium",
            "type": "low_traffic",
            "detail": f"This page had only {sessions} sessions in the last 28 days — very limited traffic.",
        })
        score -= 10

    score = max(0, min(100, score))

    return make_result(
        tool=TOOL,
        url=url,
        score=score,
        issues=issues,
        data={
            "pageviews": pageviews,
            "sessions": sessions,
            "bounce_rate": round(bounce_rate, 1),
            "avg_session_duration_seconds": round(avg_duration, 1),
            "organic_sessions": organic_sessions,
        },
    )
