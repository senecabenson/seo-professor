"""Indexation auditor — checks signals that affect search-engine indexing."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from tools.base import make_result

# ISO 639-1 codes (common subset) for basic hreflang validation
_VALID_LANG_PATTERN = re.compile(r"^[a-z]{2}(-[a-zA-Z]{2,})?$|^x-default$")


def audit(url: str, html: str, config: dict | None = None) -> dict:
    config = config or {}
    soup = BeautifulSoup(html, "html.parser")
    issues: list[dict] = []
    score = 100

    # --- Robots meta noindex ---
    robots_tag = soup.find("meta", attrs={"name": "robots"})
    has_noindex = False
    if robots_tag and robots_tag.get("content"):
        robots_content = robots_tag["content"].lower()
        if "noindex" in robots_content:
            has_noindex = True
            issues.append({
                "severity": "critical",
                "type": "noindex_meta",
                "detail": "Robots meta tag contains noindex — page will not be indexed",
            })
            score -= 30

    # --- Canonical conflicts ---
    canonical = soup.find("link", attrs={"rel": "canonical"})
    if canonical and canonical.get("href"):
        canonical_url = canonical["href"].strip().rstrip("/")
        page_url = url.strip().rstrip("/")
        if canonical_url != page_url:
            issues.append({
                "severity": "high",
                "type": "canonical_mismatch",
                "detail": f"Canonical points to {canonical['href']} instead of page URL {url}",
            })
            score -= 20

    # --- X-Robots-Tag header ---
    headers = config.get("headers", {})
    x_robots = headers.get("X-Robots-Tag", "")
    if x_robots and "noindex" in x_robots.lower():
        issues.append({
            "severity": "critical",
            "type": "x_robots_noindex",
            "detail": "X-Robots-Tag HTTP header contains noindex",
        })
        score -= 25

    # --- Redirect detection ---
    status_code = config.get("status_code")
    if status_code in (301, 302):
        redirect_url = config.get("redirect_url", "unknown")
        if status_code == 302:
            issues.append({
                "severity": "medium",
                "type": "redirect_302",
                "detail": f"302 temporary redirect to {redirect_url} — consider 301 if permanent",
            })
            score -= 10
        else:
            issues.append({
                "severity": "low",
                "type": "redirect_301",
                "detail": f"301 permanent redirect to {redirect_url}",
            })

    # --- Meta refresh redirect ---
    meta_refresh = soup.find("meta", attrs={"http-equiv": re.compile(r"refresh", re.I)})
    if meta_refresh:
        issues.append({
            "severity": "high",
            "type": "meta_refresh_redirect",
            "detail": "Meta refresh redirect detected — use server-side redirects instead",
        })
        score -= 15

    # --- Hreflang validation ---
    hreflang_tags = soup.find_all("link", attrs={"rel": "alternate", "hreflang": True})
    if hreflang_tags:
        hreflang_urls = {tag.get("hreflang", "").lower(): tag.get("href", "") for tag in hreflang_tags}

        # Check for self-referencing hreflang
        page_url_normalized = url.strip().rstrip("/")
        has_self_ref = False
        for lang, href in hreflang_urls.items():
            if href.strip().rstrip("/") == page_url_normalized:
                has_self_ref = True
                break

        if not has_self_ref:
            issues.append({
                "severity": "low",
                "type": "missing_self_hreflang",
                "detail": "Hreflang tags present but no self-referencing hreflang for this URL",
            })
            score -= 5

        # Validate lang codes
        for lang in hreflang_urls:
            if not _VALID_LANG_PATTERN.match(lang):
                issues.append({
                    "severity": "low",
                    "type": "invalid_hreflang_code",
                    "detail": f"Invalid hreflang language code: {lang}",
                })

    score = max(score, 0)

    return make_result(
        tool="indexation_auditor",
        url=url,
        score=score,
        issues=issues,
        data={
            "has_noindex": has_noindex,
            "has_canonical": canonical is not None,
            "canonical_url": canonical["href"].strip() if canonical and canonical.get("href") else None,
            "status_code": status_code,
            "hreflang_count": len(hreflang_tags) if hreflang_tags else 0,
            "has_meta_refresh": meta_refresh is not None,
        },
    )
