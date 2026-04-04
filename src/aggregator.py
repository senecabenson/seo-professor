"""Aggregator: merges per-page audit tool results into a unified site-wide dataset."""
from collections import Counter


def score_page(tool_results: list[dict]) -> int:
    """Weighted average of tool scores. Skip tools with score=None. Return 0 if all skipped."""
    scores = [r["score"] for r in tool_results if r["score"] is not None]
    if not scores:
        return 0
    return round(sum(scores) / len(scores))


def count_severities(issues: list[dict]) -> dict:
    """Count issues by severity level."""
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for issue in issues:
        sev = issue.get("severity")
        if sev in counts:
            counts[sev] += 1
    return counts


def rank_issues(all_issues: list[dict]) -> list[dict]:
    """Group issues by type, count occurrences, sort by count desc."""
    type_counts: Counter = Counter()
    type_severity: dict[str, str] = {}
    for issue in all_issues:
        itype = issue["type"]
        type_counts[itype] += 1
        if itype not in type_severity:
            type_severity[itype] = issue["severity"]
    return [
        {"type": itype, "count": count, "severity": type_severity[itype]}
        for itype, count in type_counts.most_common()
    ]


def get_worst_pages(pages: dict, limit: int = 10) -> list[dict]:
    """Return the lowest-scoring pages sorted by score ascending."""
    entries = [
        {"url": url, "score": data["score"], "issue_count": data["issue_count"]}
        for url, data in pages.items()
    ]
    entries.sort(key=lambda x: x["score"])
    return entries[:limit]


def get_tool_summaries(results: dict[str, list[dict]]) -> dict:
    """Per-tool stats: avg score and total issue count across all pages."""
    tool_scores: dict[str, list[int]] = {}
    tool_issues: dict[str, int] = {}

    for url, tool_results in results.items():
        for r in tool_results:
            tool = r["tool"]
            if tool not in tool_scores:
                tool_scores[tool] = []
                tool_issues[tool] = 0
            if r["score"] is not None:
                tool_scores[tool].append(r["score"])
            tool_issues[tool] += len(r["issues"])

    summaries = {}
    for tool in tool_scores:
        scores = tool_scores[tool]
        avg = round(sum(scores) / len(scores)) if scores else 0
        summaries[tool] = {"avg_score": avg, "issue_count": tool_issues[tool]}
    return summaries


def aggregate(results: dict[str, list[dict]]) -> dict:
    """Merge per-page audit results into a unified site-wide dataset.

    Args:
        results: Dict mapping page URLs to lists of AuditResult dicts.

    Returns:
        Aggregated site-wide audit summary.
    """
    if not results:
        return {
            "site_score": 0,
            "pages_audited": 0,
            "severity_counts": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "top_issues": [],
            "worst_pages": [],
            "tool_summaries": {},
            "pages": {},
        }

    # Build per-page detail
    pages: dict[str, dict] = {}
    all_issues: list[dict] = []

    for url, tool_results in results.items():
        page_score = score_page(tool_results)
        page_issues = []
        tool_results_map = {}

        for r in tool_results:
            page_issues.extend(r["issues"])
            tool_results_map[r["tool"]] = {
                "score": r["score"],
                "issues": r["issues"],
                "data": r.get("data", {}),
            }

        pages[url] = {
            "score": page_score,
            "issue_count": len(page_issues),
            "issues": page_issues,
            "tool_results": tool_results_map,
        }
        all_issues.extend(page_issues)

    # Site-wide metrics
    page_scores = [p["score"] for p in pages.values()]
    site_score = round(sum(page_scores) / len(page_scores)) if page_scores else 0

    return {
        "site_score": site_score,
        "pages_audited": len(pages),
        "severity_counts": count_severities(all_issues),
        "top_issues": rank_issues(all_issues),
        "worst_pages": get_worst_pages(pages),
        "tool_summaries": get_tool_summaries(results),
        "pages": pages,
    }
