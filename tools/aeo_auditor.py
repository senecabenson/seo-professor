"""AEO (Answer Engine Optimization) auditor — checks content for AI search engine optimization."""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup, Tag

from tools.base import make_result


DEDUCTIONS = {
    "no_direct_answers": 20,
    "no_structured_content": 15,
    "no_question_headings": 10,
    "no_citation_signals": 20,
    "no_date_signals": 15,
    "no_llms_txt": 5,
    "generic_meta_description": 10,
    "no_meta_description_for_aeo": 10,
}

QUESTION_WORDS = {"who", "what", "where", "when", "why", "how", "can", "does", "is", "are", "should", "will"}

DEFINITION_RE = re.compile(
    r"\b\w[\w\s]*?\b\s+(?:is|refers?\s+to|means?|defined\s+as)\b",
    re.IGNORECASE,
)

STAT_RE = re.compile(r"\d+%|\$[\d,.]+|\d+\s+out\s+of\s+\d+|\d+x\b")

SUPERLATIVE_RE = re.compile(
    r"\b(?:best|guaranteed|proven|#1|number\s+one)\b",
    re.IGNORECASE,
)

GENERIC_META_RE = re.compile(r"^(?:welcome\s+to|we\s+are\s+a|our\s+company|home\b)", re.IGNORECASE)

DATE_TEXT_RE = re.compile(
    r"(?:last\s+updated|published\s+on|updated:|modified:)",
    re.IGNORECASE,
)


def _is_inside_excluded(tag: Tag) -> bool:
    """Check if a tag is inside nav, header, or footer."""
    for parent in tag.parents:
        if parent.name in ("nav", "header", "footer"):
            return True
    return False


def _get_first_words(text: str, n: int) -> str:
    """Return the first n words of text."""
    words = text.split()
    return " ".join(words[:n])


def _check_direct_answers(soup: BeautifulSoup) -> tuple[float, list[dict]]:
    """Check for direct answer patterns after H2/H3 headings."""
    headings = soup.find_all(["h2", "h3"])
    if not headings:
        return 0.0, []

    direct_count = 0
    for heading in headings:
        # Find the next sibling <p> element
        sibling = heading.find_next_sibling("p")
        if not sibling:
            continue
        first_words = _get_first_words(sibling.get_text(strip=True), 60)
        if DEFINITION_RE.search(first_words):
            direct_count += 1

    ratio = direct_count / len(headings)
    issues = []
    if ratio == 0:
        issues.append({
            "severity": "high",
            "type": "no_direct_answers",
            "detail": "No headings are followed by direct answer patterns (e.g., 'X is...', 'X refers to...')",
        })
    return ratio, issues


def _check_structured_content(soup: BeautifulSoup) -> tuple[bool, int, int, float, list[dict]]:
    """Check for structured content elements (lists, tables) and paragraph density."""
    # Count lists excluding nav/header/footer
    list_count = 0
    for tag in soup.find_all(["ul", "ol", "dl"]):
        if not _is_inside_excluded(tag):
            list_count += 1

    table_count = len(soup.find_all("table"))
    has_structured = (list_count + table_count) > 0

    # Paragraph density
    paragraphs = soup.find_all("p")
    word_counts = []
    for p in paragraphs:
        text = p.get_text(strip=True)
        if text:
            word_counts.append(len(text.split()))

    avg_para_length = sum(word_counts) / len(word_counts) if word_counts else 0.0

    issues = []
    if not has_structured:
        issues.append({
            "severity": "medium",
            "type": "no_structured_content",
            "detail": "No structured content found (lists, tables, definition lists). AI engines prefer extractable formats.",
        })

    return has_structured, list_count, table_count, avg_para_length, issues


def _check_question_headings(soup: BeautifulSoup) -> tuple[float, list[dict]]:
    """Check for question-format headings."""
    headings = soup.find_all(["h2", "h3"])
    if not headings:
        return 0.0, []

    question_count = 0
    for heading in headings:
        text = heading.get_text(strip=True)
        if not text:
            continue
        first_word = text.split()[0].lower().rstrip("?")
        if first_word in QUESTION_WORDS or text.endswith("?"):
            question_count += 1

    ratio = question_count / len(headings)
    issues = []
    if ratio == 0:
        issues.append({
            "severity": "medium",
            "type": "no_question_headings",
            "detail": "No question-format headings found. AI engines favor Q&A-style content structure.",
        })
    return ratio, issues


def _check_citation_worthiness(soup: BeautifulSoup) -> tuple[int, int, list[str], list[dict]]:
    """Check for statistics, citations, and trust bottleneck superlatives."""
    content_tags = soup.find_all(["p", "li", "td", "blockquote"])

    stat_count = 0
    citation_count = 0
    trust_bottleneck_flags = []

    for tag in content_tags:
        text = tag.get_text(strip=True)
        # Count stats
        stats_in_tag = STAT_RE.findall(text)
        stat_count += len(stats_in_tag)

        # Check for citations: stat + <a> in same parent element
        if stats_in_tag and tag.find("a"):
            citation_count += len(stats_in_tag)

        # Trust bottleneck: superlatives without nearby data
        superlatives = SUPERLATIVE_RE.findall(text)
        for sup in superlatives:
            # Check if there's a number/stat in the same sentence
            if not STAT_RE.search(text):
                trust_bottleneck_flags.append(sup.lower())

    issues = []
    if stat_count == 0 and citation_count == 0:
        issues.append({
            "severity": "high",
            "type": "no_citation_signals",
            "detail": "No statistics or citations found. AI engines prioritize content with verifiable data.",
        })

    for flag in trust_bottleneck_flags:
        issues.append({
            "severity": "low",
            "type": "trust_bottleneck",
            "detail": f"Superlative '{flag}' used without supporting data — may reduce AI citation trust.",
        })

    return stat_count, citation_count, trust_bottleneck_flags, issues


def _check_content_freshness(soup: BeautifulSoup) -> tuple[bool, str | None, str | None, list[dict]]:
    """Check for content freshness signals."""
    date_published = None
    date_modified = None
    has_date_signals = False

    # Check JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict):
                if "datePublished" in data:
                    date_published = data["datePublished"]
                    has_date_signals = True
                if "dateModified" in data:
                    date_modified = data["dateModified"]
                    has_date_signals = True
        except (json.JSONDecodeError, TypeError):
            pass

    # Check <time> elements
    for time_tag in soup.find_all("time"):
        if time_tag.get("datetime"):
            has_date_signals = True
            break

    # Check visible text for date patterns
    body_text = soup.get_text()
    if DATE_TEXT_RE.search(body_text):
        has_date_signals = True

    issues = []
    if not has_date_signals:
        issues.append({
            "severity": "medium",
            "type": "no_date_signals",
            "detail": "No content freshness signals found (dates, timestamps). AI engines favor recently updated content.",
        })

    return has_date_signals, date_published, date_modified, issues


def _check_llms_txt(config: dict) -> tuple[bool, list[dict]]:
    """Check for llms.txt awareness."""
    llms_txt = config.get("llms_txt")
    issues = []

    if llms_txt:
        # Validate basic structure: must have a line starting with "# "
        has_h1 = any(line.startswith("# ") for line in llms_txt.splitlines())
        return has_h1, issues

    issues.append({
        "severity": "low",
        "type": "no_llms_txt",
        "detail": "No llms.txt file detected. Consider adding one to guide AI crawlers.",
    })
    return False, issues


def _check_meta_description(soup: BeautifulSoup) -> list[dict]:
    """Check meta description for AEO optimization."""
    desc_tag = soup.find("meta", attrs={"name": "description"})
    desc_text = desc_tag["content"].strip() if desc_tag and desc_tag.get("content") else ""

    issues = []
    if not desc_text:
        issues.append({
            "severity": "medium",
            "type": "no_meta_description_for_aeo",
            "detail": "No meta description found. AI engines use this for content summarization.",
        })
    elif GENERIC_META_RE.match(desc_text):
        issues.append({
            "severity": "medium",
            "type": "generic_meta_description",
            "detail": "Meta description uses a generic pattern. Use a direct answer or concise summary instead.",
        })

    return issues


def _get_content_preview(soup: BeautifulSoup) -> str:
    """Get the first ~30% of body text, truncated to 200 chars."""
    body = soup.find("body")
    if not body:
        return ""
    text = body.get_text(separator=" ", strip=True)
    cutoff = max(1, int(len(text) * 0.3))
    preview = text[:cutoff]
    return preview[:200]


def audit(url: str, html: str, config: dict | None = None) -> dict:
    """Run AEO audit on the given HTML content."""
    config = config or {}
    soup = BeautifulSoup(html, "html.parser")
    issues: list[dict] = []
    score = 100

    # 1. Direct Answer Patterns
    direct_answer_ratio, da_issues = _check_direct_answers(soup)
    issues.extend(da_issues)

    # 2. Content Structure
    has_structured, list_count, table_count, avg_para_length, sc_issues = _check_structured_content(soup)
    issues.extend(sc_issues)

    # 3. Question Headings
    question_heading_ratio, qh_issues = _check_question_headings(soup)
    issues.extend(qh_issues)

    # 4. Citation Worthiness
    stat_count, citation_count, trust_bottleneck_flags, cw_issues = _check_citation_worthiness(soup)
    issues.extend(cw_issues)

    # 5. Content Freshness
    has_date_signals, date_published, date_modified, cf_issues = _check_content_freshness(soup)
    issues.extend(cf_issues)

    # 6. llms.txt
    has_llms_txt, lt_issues = _check_llms_txt(config)
    issues.extend(lt_issues)

    # 7. Meta Description
    md_issues = _check_meta_description(soup)
    issues.extend(md_issues)

    # --- Scoring ---
    for issue in issues:
        issue_type = issue["type"]
        if issue_type in DEDUCTIONS:
            score -= DEDUCTIONS[issue_type]

    # Trust bottleneck: -5 each, max -15
    tb_count = sum(1 for i in issues if i["type"] == "trust_bottleneck")
    score -= min(tb_count * 5, 15)

    # Floor at 0
    score = max(score, 0)

    # --- Data ---
    data = {
        "direct_answer_ratio": direct_answer_ratio,
        "question_heading_ratio": question_heading_ratio,
        "has_structured_content": has_structured,
        "list_count": list_count,
        "table_count": table_count,
        "stat_count": stat_count,
        "citation_count": citation_count,
        "has_date_signals": has_date_signals,
        "date_published": date_published,
        "date_modified": date_modified,
        "has_llms_txt": has_llms_txt,
        "trust_bottleneck_flags": trust_bottleneck_flags,
        "avg_paragraph_length": avg_para_length,
        "content_in_first_30_pct": _get_content_preview(soup),
    }

    return make_result(tool="aeo_auditor", url=url, score=score, issues=issues, data=data)
