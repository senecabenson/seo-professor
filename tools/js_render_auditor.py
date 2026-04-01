"""JS render auditor — heuristic checks for JavaScript rendering issues."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from tools.base import make_result


def audit(url: str, html: str, config: dict | None = None) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    issues: list[dict] = []
    score = 100

    body = soup.find("body")

    # --- SPA root detection ---
    has_spa_root = False
    spa_root_empty = False
    for root_id in ("root", "app"):
        root_div = soup.find("div", attrs={"id": root_id})
        if root_div:
            has_spa_root = True
            # Check if root div has no meaningful child content
            child_text = root_div.get_text(strip=True)
            child_elements = [c for c in root_div.children if getattr(c, "name", None) is not None]
            if not child_text and not child_elements:
                spa_root_empty = True
                break

    # --- Empty body detection ---
    body_has_content = False
    if body:
        # Get text excluding script/noscript tags
        body_clone = BeautifulSoup(str(body), "html.parser")
        for tag in body_clone.find_all(["script", "noscript"]):
            tag.decompose()
        body_text_only = body_clone.get_text(strip=True)
        body_has_content = bool(body_text_only)

    if spa_root_empty or (body and not body_has_content):
        issues.append({
            "severity": "critical",
            "type": "empty_body_or_spa_root",
            "detail": "Page body contains no visible content — likely rendered by JavaScript",
        })
        score -= 30

    # --- Noscript detection ---
    has_noscript = soup.find("noscript") is not None

    # --- Script counting ---
    all_scripts = soup.find_all("script")
    external_scripts = [s for s in all_scripts if s.get("src")]
    inline_scripts = [s for s in all_scripts if not s.get("src") and s.string]
    external_script_count = len(external_scripts)
    inline_script_count = len(inline_scripts)

    if external_script_count > 20:
        issues.append({
            "severity": "high",
            "type": "very_heavy_scripts",
            "detail": f"Page loads {external_script_count} external scripts (>20 is excessive)",
        })
        score -= 20
    elif external_script_count > 10:
        issues.append({
            "severity": "medium",
            "type": "heavy_scripts",
            "detail": f"Page loads {external_script_count} external scripts (>10 is heavy)",
        })
        score -= 10

    # --- Deprecated AJAX crawling fragment meta ---
    fragment_meta = soup.find("meta", attrs={"name": "fragment", "content": "!"})
    has_fragment_meta = fragment_meta is not None

    if has_fragment_meta:
        issues.append({
            "severity": "high",
            "type": "deprecated_fragment_meta",
            "detail": 'Deprecated <meta name="fragment" content="!"> detected — AJAX crawling scheme is obsolete',
        })
        score -= 15

    # --- No noscript fallback ---
    has_any_scripts = len(all_scripts) > 0
    if not has_noscript and has_any_scripts:
        issues.append({
            "severity": "low",
            "type": "no_noscript_fallback",
            "detail": "Page has scripts but no <noscript> fallback",
        })
        score -= 5

    # --- Content-to-script ratio ---
    body_text_length = 0
    script_text_length = 0

    if body:
        body_for_text = BeautifulSoup(str(body), "html.parser")
        for tag in body_for_text.find_all(["script", "style", "noscript"]):
            tag.decompose()
        body_text_length = len(body_for_text.get_text(strip=True))

    for s in all_scripts:
        if s.string:
            script_text_length += len(s.string.strip())

    if script_text_length > 0 and body_text_length < script_text_length * 0.5:
        # More script than content
        if body_text_length > 0:  # Only flag if there IS some content (empty body already caught)
            issues.append({
                "severity": "medium",
                "type": "low_content_to_script_ratio",
                "detail": f"Content-to-script ratio is low ({body_text_length}/{script_text_length})",
            })
            score -= 10

    score = max(score, 0)

    return make_result(
        tool="js_render_auditor",
        url=url,
        score=score,
        issues=issues,
        data={
            "has_spa_root": has_spa_root,
            "spa_root_empty": spa_root_empty,
            "has_noscript": has_noscript,
            "external_script_count": external_script_count,
            "inline_script_count": inline_script_count,
            "body_text_length": body_text_length,
            "script_text_length": script_text_length,
            "has_fragment_meta": has_fragment_meta,
        },
    )
