"""Core Web Vitals auditor — calls Google PageSpeed Insights API."""

from __future__ import annotations

import os

import httpx

from tools.base import make_result


def audit(url: str, html: str, config: dict | None = None) -> dict:
    api_key = os.environ.get("GOOGLE_PAGESPEED_API_KEY")

    if not api_key:
        return make_result(
            tool="cwv_auditor",
            url=url,
            score=None,
            issues=[
                {
                    "severity": "low",
                    "type": "skipped",
                    "detail": "CWV audit skipped — GOOGLE_PAGESPEED_API_KEY not set",
                }
            ],
        )

    api_url = (
        "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        f"?url={url}&key={api_key}&strategy=mobile&category=performance"
    )

    try:
        response = httpx.get(api_url, timeout=30)
        if response.status_code != 200:
            return make_result(
                tool="cwv_auditor",
                url=url,
                score=None,
                issues=[
                    {
                        "severity": "high",
                        "type": "api_error",
                        "detail": f"PageSpeed API returned HTTP {response.status_code}",
                    }
                ],
            )
        data = response.json()
    except (httpx.TimeoutException, httpx.HTTPError) as exc:
        return make_result(
            tool="cwv_auditor",
            url=url,
            score=None,
            issues=[
                {
                    "severity": "high",
                    "type": "api_error",
                    "detail": f"PageSpeed API request failed: {exc}",
                }
            ],
        )

    return _parse_response(url, data)


def _parse_response(url: str, data: dict) -> dict:
    lighthouse = data.get("lighthouseResult", {})
    audits = lighthouse.get("audits", {})
    categories = lighthouse.get("categories", {})

    perf_score_raw = categories.get("performance", {}).get("score", 0)
    performance_score = int(round(perf_score_raw * 100))

    lcp_ms = audits.get("largest-contentful-paint", {}).get("numericValue", 0)
    tbt_ms = audits.get("total-blocking-time", {}).get("numericValue", 0)
    cls = audits.get("cumulative-layout-shift", {}).get("numericValue", 0)
    fcp_ms = audits.get("first-contentful-paint", {}).get("numericValue", 0)
    speed_index_ms = audits.get("speed-index", {}).get("numericValue", 0)

    issues: list[dict] = []

    # LCP thresholds
    if lcp_ms >= 4000:
        issues.append({"severity": "critical", "type": "poor_lcp", "detail": f"LCP is {lcp_ms:.0f}ms (poor, threshold 4000ms)"})
    elif lcp_ms >= 2500:
        issues.append({"severity": "high", "type": "needs_improvement_lcp", "detail": f"LCP is {lcp_ms:.0f}ms (needs improvement, threshold 2500ms)"})

    # TBT thresholds (INP proxy)
    if tbt_ms >= 600:
        issues.append({"severity": "high", "type": "poor_tbt", "detail": f"TBT is {tbt_ms:.0f}ms (poor, threshold 600ms)"})
    elif tbt_ms >= 200:
        issues.append({"severity": "medium", "type": "needs_improvement_tbt", "detail": f"TBT is {tbt_ms:.0f}ms (needs improvement, threshold 200ms)"})

    # CLS thresholds
    if cls >= 0.25:
        issues.append({"severity": "high", "type": "poor_cls", "detail": f"CLS is {cls:.3f} (poor, threshold 0.25)"})
    elif cls >= 0.1:
        issues.append({"severity": "medium", "type": "needs_improvement_cls", "detail": f"CLS is {cls:.3f} (needs improvement, threshold 0.1)"})

    return make_result(
        tool="cwv_auditor",
        url=url,
        score=performance_score,
        issues=issues,
        data={
            "lcp_ms": lcp_ms,
            "tbt_ms": tbt_ms,
            "cls": cls,
            "fcp_ms": fcp_ms,
            "speed_index_ms": speed_index_ms,
            "performance_score": performance_score,
        },
    )
