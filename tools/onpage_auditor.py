"""On-page SEO auditor — checks HTML structure and meta-level signals."""

from __future__ import annotations

from bs4 import BeautifulSoup

from tools.base import make_result


def audit(url: str, html: str, config: dict | None = None) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    issues: list[dict] = []
    score = 100

    # --- Title ---
    title_tag = soup.find("title")
    title_text = title_tag.string.strip() if title_tag and title_tag.string else ""
    title_length = len(title_text)

    if not title_text:
        issues.append({"severity": "critical", "type": "missing_title", "detail": "No <title> tag found"})
        score -= 20
    elif title_length > 60:
        issues.append({"severity": "medium", "type": "title_too_long", "detail": f"Title is {title_length} chars (recommended 50-60)"})
        score -= 5
    elif title_length < 30:
        issues.append({"severity": "medium", "type": "title_too_short", "detail": f"Title is {title_length} chars (recommended 50-60)"})
        score -= 5

    # --- Meta description ---
    desc_tag = soup.find("meta", attrs={"name": "description"})
    desc_text = desc_tag["content"].strip() if desc_tag and desc_tag.get("content") else ""
    desc_length = len(desc_text)

    if not desc_text:
        issues.append({"severity": "high", "type": "missing_meta_description", "detail": "No meta description found"})
        score -= 15
    elif desc_length > 160:
        issues.append({"severity": "medium", "type": "description_too_long", "detail": f"Meta description is {desc_length} chars (recommended 150-160)"})
        score -= 5
    elif desc_length < 70:
        issues.append({"severity": "medium", "type": "description_too_short", "detail": f"Meta description is {desc_length} chars (recommended 150-160)"})
        score -= 5

    # --- Canonical ---
    canonical = soup.find("link", attrs={"rel": "canonical"})
    has_canonical = canonical is not None

    if not has_canonical:
        issues.append({"severity": "medium", "type": "missing_canonical", "detail": "No canonical link tag found"})
        score -= 10

    # --- H1 ---
    h1_tags = soup.find_all("h1")
    h1_count = len(h1_tags)

    if h1_count == 0:
        issues.append({"severity": "high", "type": "missing_h1", "detail": "No H1 heading found"})
        score -= 15
    elif h1_count > 1:
        issues.append({"severity": "medium", "type": "multiple_h1", "detail": f"Found {h1_count} H1 tags (should be exactly 1)"})
        score -= 10

    # --- Heading hierarchy ---
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    heading_levels = [int(h.name[1]) for h in headings]
    hierarchy_deductions = 0

    for i in range(1, len(heading_levels)):
        if heading_levels[i] > heading_levels[i - 1] + 1:
            issues.append({
                "severity": "low",
                "type": "heading_hierarchy_skip",
                "detail": f"Heading jumps from H{heading_levels[i - 1]} to H{heading_levels[i]}",
            })
            hierarchy_deductions += 5
            if hierarchy_deductions >= 15:
                break

    score -= min(hierarchy_deductions, 15)

    # --- Open Graph ---
    og_required = ["og:title", "og:description", "og:image", "og:url"]
    og_found = [soup.find("meta", attrs={"property": tag}) is not None for tag in og_required]
    has_og_tags = all(og_found)

    if not has_og_tags:
        missing = [tag for tag, found in zip(og_required, og_found) if not found]
        issues.append({"severity": "low", "type": "missing_og_tags", "detail": f"Missing Open Graph tags: {', '.join(missing)}"})
        score -= 5

    # --- Twitter Card ---
    twitter_required = ["twitter:card", "twitter:title"]
    twitter_found = [soup.find("meta", attrs={"name": tag}) is not None for tag in twitter_required]
    has_twitter_tags = all(twitter_found)

    if not has_twitter_tags:
        missing = [tag for tag, found in zip(twitter_required, twitter_found) if not found]
        issues.append({"severity": "low", "type": "missing_twitter_tags", "detail": f"Missing Twitter Card tags: {', '.join(missing)}"})
        score -= 3

    # --- Robots meta ---
    robots_tag = soup.find("meta", attrs={"name": "robots"})
    if robots_tag and robots_tag.get("content"):
        robots_content = robots_tag["content"].lower()
        if "noindex" in robots_content:
            issues.append({"severity": "critical", "type": "noindex_detected", "detail": "Robots meta tag contains noindex"})
        if "nofollow" in robots_content:
            issues.append({"severity": "high", "type": "nofollow_detected", "detail": "Robots meta tag contains nofollow"})

    # --- Word count ---
    body = soup.find("body")
    body_text = body.get_text(separator=" ", strip=True) if body else ""
    word_count = len(body_text.split()) if body_text else 0

    if word_count < 300:
        issues.append({"severity": "low", "type": "low_word_count", "detail": f"Body text is {word_count} words (recommended 300+)"})
        score -= 5

    # --- Heading structure for data ---
    heading_structure = [f"H{level}" for level in heading_levels]

    score = max(score, 0)

    return make_result(
        tool="onpage_auditor",
        url=url,
        score=score,
        issues=issues,
        data={
            "title_length": title_length,
            "description_length": desc_length,
            "h1_count": h1_count,
            "word_count": word_count,
            "has_canonical": has_canonical,
            "has_og_tags": has_og_tags,
            "has_twitter_tags": has_twitter_tags,
            "heading_structure": heading_structure,
        },
    )
