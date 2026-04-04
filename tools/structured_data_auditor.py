"""Structured data and AI bot governance auditor."""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from tools.base import make_result

# Required properties per schema.org type
REQUIRED_PROPS: dict[str, list[str]] = {
    "Article": ["headline", "author", "datePublished"],
    "Organization": ["name", "url"],
    "Product": ["name", "offers"],
    "LocalBusiness": ["name", "address"],
    "BreadcrumbList": ["itemListElement"],
    "FAQPage": ["mainEntity"],
}

AI_BOTS = ["GPTBot", "OAI-SearchBot", "CCBot", "anthropic-ai", "Google-Extended"]


def _parse_robots_txt(robots_txt: str) -> dict[str, str]:
    """Parse robots.txt and return AI bot directives."""
    directives: dict[str, str] = {bot: "not_specified" for bot in AI_BOTS}

    if not robots_txt or not robots_txt.strip():
        return directives

    # Parse user-agent blocks
    current_agents: list[str] = []
    for line in robots_txt.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if line.lower().startswith("user-agent:"):
            agent = line.split(":", 1)[1].strip()
            current_agents = [agent]
        elif line.lower().startswith("disallow:"):
            path = line.split(":", 1)[1].strip()
            for agent in current_agents:
                if agent in directives:
                    if path == "/" or path == "/*":
                        directives[agent] = "blocked"
        elif line.lower().startswith("allow:"):
            for agent in current_agents:
                if agent in directives and directives[agent] == "not_specified":
                    directives[agent] = "allowed"

    return directives


def audit(url: str, html: str, config: dict | None = None) -> dict:
    config = config or {}
    soup = BeautifulSoup(html, "html.parser")
    issues: list[dict] = []
    score = 100

    # --- JSON-LD detection ---
    ld_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    json_ld_count = len(ld_scripts)
    json_ld_types: list[str] = []
    schemas: list[dict] = []

    for script in ld_scripts:
        text = script.string or ""
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            schemas.append({"type": "unknown", "valid": False, "missing_properties": []})
            issues.append({
                "severity": "critical",
                "type": "invalid_json_ld",
                "detail": "JSON-LD block contains invalid JSON",
            })
            score -= 20
            continue

        schema_type = data.get("@type", "unknown")
        json_ld_types.append(schema_type)

        # Check required properties
        required = REQUIRED_PROPS.get(schema_type, [])
        missing = [prop for prop in required if prop not in data]

        schemas.append({
            "type": schema_type,
            "valid": len(missing) == 0,
            "missing_properties": missing,
        })

        if missing:
            for prop in missing:
                issues.append({
                    "severity": "medium",
                    "type": "missing_schema_property",
                    "detail": f"{schema_type} schema missing required property: {prop}",
                })

    # Deduct for missing properties (max -20)
    missing_prop_issues = [i for i in issues if i["type"] == "missing_schema_property"]
    prop_deduction = min(len(missing_prop_issues) * 10, 20)
    score -= prop_deduction

    # No structured data at all
    if json_ld_count == 0:
        issues.append({
            "severity": "high",
            "type": "no_structured_data",
            "detail": "No JSON-LD structured data found on page",
        })
        score -= 25

    # --- Microdata detection ---
    has_microdata = soup.find(attrs={"itemscope": True}) is not None

    # --- AI bot governance ---
    robots_txt = config.get("robots_txt", "")
    ai_bot_directives = _parse_robots_txt(robots_txt)

    has_any_governance = any(v != "not_specified" for v in ai_bot_directives.values())
    if not has_any_governance:
        issues.append({
            "severity": "low",
            "type": "no_ai_bot_governance",
            "detail": "No AI bot directives found in robots.txt",
        })
        score -= 5

    score = max(score, 0)

    return make_result(
        tool="structured_data_auditor",
        url=url,
        score=score,
        issues=issues,
        data={
            "json_ld_count": json_ld_count,
            "json_ld_types": json_ld_types,
            "has_microdata": has_microdata,
            "schemas": schemas,
            "ai_bot_directives": ai_bot_directives,
        },
    )
