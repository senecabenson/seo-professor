"""AI Analyzer: formats aggregated audit data into a structured prompt for Claude analysis.

This module does NOT call the Claude API. It prepares the data and prompt
so Claude can analyze it in-session.
"""
import copy
import json
import anthropic


def _build_prompt(data: dict, domain: str) -> str:
    """Build a structured analysis prompt from aggregated audit data."""
    sev = data.get("severity_counts", {})
    total_issues = sum(sev.values())

    lines = [
        "# SEO Audit Analysis Request",
        "",
        "## Site Overview",
        f"- Domain: {domain}",
        f"- Pages Audited: {data.get('pages_audited', 0)}",
        f"- Overall Score: {data.get('site_score', 0)}/100",
        f"- Issues Found: {total_issues} "
        f"({sev.get('critical', 0)} critical, {sev.get('high', 0)} high, "
        f"{sev.get('medium', 0)} medium, {sev.get('low', 0)} low)",
        "",
    ]

    # Top issues
    top_issues = data.get("top_issues", [])
    if top_issues:
        lines.append("## Top Issues (by frequency)")
        for i, issue in enumerate(top_issues, 1):
            lines.append(
                f"{i}. {issue['type']} — found on {issue['count']} pages "
                f"(severity: {issue['severity']})"
            )
        lines.append("")

    # Worst pages
    worst_pages = data.get("worst_pages", [])
    if worst_pages:
        lines.append("## Worst Performing Pages")
        for i, page in enumerate(worst_pages, 1):
            lines.append(
                f"{i}. {page['url']} — Score: {page['score']}/100, "
                f"{page['issue_count']} issues"
            )
        lines.append("")

    # Tool summaries
    tool_summaries = data.get("tool_summaries", {})
    if tool_summaries:
        lines.append("## Tool Performance Summary")
        lines.append("| Tool | Avg Score | Issues |")
        lines.append("|------|-----------|--------|")
        for tool, stats in tool_summaries.items():
            lines.append(f"| {tool} | {stats['avg_score']} | {stats['issue_count']} |")
        lines.append("")

    # Detailed page data (up to 10 worst)
    pages = data.get("pages", {})
    if pages:
        # Sort by score ascending to get worst first
        sorted_urls = sorted(pages, key=lambda u: pages[u]["score"])
        detail_urls = sorted_urls[:10]

        lines.append("## Detailed Page Data")
        for url in detail_urls:
            p = pages[url]
            lines.append(f"\n### {url}")
            lines.append(f"- Score: {p['score']}/100")
            lines.append(f"- Issues: {p['issue_count']}")
            if p.get("issues"):
                for issue in p["issues"]:
                    lines.append(
                        f"  - [{issue['severity'].upper()}] {issue['type']}: "
                        f"{issue['detail']}"
                    )
        lines.append("")

    # Instructions
    lines.extend([
        "## Instructions",
        "Analyze this SEO audit data and provide your response as JSON with these exact keys:",
        '- "executive_summary": 3-5 sentences summarizing the site\'s SEO health',
        '- "priority_fixes": list of {"issue": str, "effort": "low|medium|high", '
        '"impact": "low|medium|high", "description": str}',
        '- "category_analysis": dict of tool_name -> {"score": int, "assessment": str, '
        '"key_issues": [str]}',
        '- "recommendations": list of {"action": str, "priority": int (1=highest), '
        '"rationale": str}',
    ])

    return "\n".join(lines)


def _build_structured_input(data: dict) -> dict:
    """Build a clean, JSON-serializable copy of the aggregated data.

    For large sites (100+ pages), trims pages to the 10 worst.
    """
    result = copy.deepcopy(data)
    pages = result.get("pages", {})

    if result.get("pages_audited", 0) > 100 and len(pages) > 10:
        # Keep only 10 worst pages
        sorted_urls = sorted(pages, key=lambda u: pages[u]["score"])
        worst_10 = sorted_urls[:10]
        result["pages"] = {url: pages[url] for url in worst_10}
        result["pages_trimmed"] = True
        result["pages_included"] = 10

    return result


def format_for_analysis(aggregated_data: dict, domain: str) -> dict:
    """Format aggregated audit data into a prompt and structured input for Claude.

    Args:
        aggregated_data: Output from src.aggregator.aggregate().
        domain: The domain being audited.

    Returns:
        Dict with "prompt" (str) and "structured_input" (dict).
    """
    return {
        "prompt": _build_prompt(aggregated_data, domain),
        "structured_input": _build_structured_input(aggregated_data),
    }


def analyze_with_claude(prompt: str, api_key: str) -> dict:
    """Call the Claude API with the audit prompt and return structured analysis.

    Used in automated mode (e.g. Trigger.dev) when ANTHROPIC_API_KEY is set.
    When running locally through Claude Code, skip this — Claude Code handles
    analysis in-session and writes .tmp/ai_analysis.json directly.

    Args:
        prompt: The formatted audit prompt from _build_prompt().
        api_key: Anthropic API key.

    Returns:
        Dict with keys: executive_summary, priority_fixes, category_analysis, recommendations.
        Falls back to a default analysis dict if the response cannot be parsed.
    """
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text

    # Strip ```json ... ``` fences if present
    if raw.strip().startswith("```"):
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {
            "executive_summary": "AI analysis could not be parsed. Review audit data manually.",
            "priority_fixes": [],
            "category_analysis": {},
            "recommendations": [],
        }
