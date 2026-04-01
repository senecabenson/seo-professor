"""Link auditor — checks internal/external links, anchor text quality, and suspicious hrefs."""

from __future__ import annotations

from urllib.parse import urlparse

from bs4 import BeautifulSoup

from tools.base import make_result

POOR_ANCHOR_TEXTS = {"click here", "here", "read more", "learn more"}
SUSPICIOUS_HREFS = {"", "#", "javascript:void(0)", "javascript:;"}


def audit(url: str, html: str, config: dict | None = None) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    issues: list[dict] = []
    score = 100

    parsed_url = urlparse(url)
    site_domain = parsed_url.netloc

    anchors = soup.find_all("a", href=True)

    internal_links: list[str] = []
    external_links: list[str] = []
    broken_links: list[str] = []
    empty_anchors: list[str] = []
    poor_anchors: list[dict] = []
    nofollow_count = 0

    for a in anchors:
        href = a.get("href", "").strip()

        # Check broken/suspicious
        if href in SUSPICIOUS_HREFS:
            broken_links.append(href)
            continue

        # Classify internal vs external
        parsed_href = urlparse(href)
        if parsed_href.netloc and parsed_href.netloc != site_domain:
            external_links.append(href)
        else:
            internal_links.append(href)

        # Check anchor text
        text = a.get_text(strip=True)
        if not text:
            empty_anchors.append(href)
        elif text.lower() in POOR_ANCHOR_TEXTS:
            poor_anchors.append({"href": href, "text": text})

        # Check nofollow
        rel = a.get("rel", [])
        if isinstance(rel, list) and "nofollow" in rel:
            nofollow_count += 1
        elif isinstance(rel, str) and "nofollow" in rel:
            nofollow_count += 1

    total_links = len(anchors)

    # --- Scoring ---
    # Broken/suspicious links
    for i, href in enumerate(broken_links):
        if i >= 4:
            break
        issues.append({"severity": "high", "type": "broken_link", "detail": f"Suspicious/broken href: '{href}'"})
    score -= min(len(broken_links) * 5, 20)

    # Empty anchors
    for i, href in enumerate(empty_anchors):
        if i >= 3:
            break
        issues.append({"severity": "medium", "type": "empty_anchor_text", "detail": f"Link has no anchor text: {href}"})
    score -= min(len(empty_anchors) * 5, 15)

    # Poor anchors
    for i, item in enumerate(poor_anchors):
        if i >= 3:
            break
        issues.append({"severity": "low", "type": "poor_anchor_text", "detail": f"Poor anchor text '{item['text']}' on {item['href']}"})
    score -= min(len(poor_anchors) * 3, 9)

    # Zero internal links
    if total_links > 0 and len(internal_links) == 0:
        issues.append({"severity": "medium", "type": "no_internal_links", "detail": "No internal links found"})
        score -= 15

    # Zero links total
    if total_links == 0:
        issues.append({"severity": "medium", "type": "no_links", "detail": "Page has no links at all"})
        score -= 20

    score = max(score, 0)

    return make_result(
        tool="link_auditor",
        url=url,
        score=score,
        issues=issues,
        data={
            "internal_link_count": len(internal_links),
            "external_link_count": len(external_links),
            "total_links": total_links,
            "broken_links": broken_links,
            "empty_anchors": empty_anchors,
            "poor_anchors": poor_anchors,
            "nofollow_count": nofollow_count,
        },
    )
