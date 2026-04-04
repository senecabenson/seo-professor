"""E-E-A-T authority signals auditor."""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from tools.base import make_result

SOCIAL_DOMAINS = [
    "twitter.com",
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
]

CREDENTIAL_PATTERNS = [
    r"\bcertified\b",
    r"\blicensed\b",
    r"\baccredited\b",
    r"\byears of experience\b",
]


def audit(url: str, html: str, config: dict | None = None) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    issues: list[dict] = []
    score = 100

    # --- Author attribution ---
    has_author = False
    author_name: str | None = None

    # Check meta author tag
    meta_author = soup.find("meta", attrs={"name": "author"})
    if meta_author and meta_author.get("content", "").strip():
        has_author = True
        author_name = meta_author["content"].strip()

    # Check for links with "author" in href
    author_links = soup.find_all("a", href=re.compile(r"author", re.IGNORECASE))
    if author_links:
        has_author = True
        # Try to get author name from link text if not already found
        if not author_name:
            for link in author_links:
                text = link.get_text(strip=True)
                if text:
                    # Strip trailing credentials like ", CPA, JD"
                    author_name = text.split(",")[0].strip()
                    break

    # Check for elements with class/id containing "author"
    author_elements = soup.find_all(
        attrs={"class": re.compile(r"author", re.IGNORECASE)}
    )
    author_elements += soup.find_all(
        attrs={"id": re.compile(r"author", re.IGNORECASE)}
    )
    for el in author_elements:
        text = el.get_text(strip=True)
        if text:
            has_author = True
            break

    if not has_author:
        issues.append({
            "severity": "high",
            "type": "no_author_attribution",
            "detail": "No author attribution found on page",
        })
        score -= 20

    # --- About page link ---
    about_links = soup.find_all("a", href=re.compile(r"/about", re.IGNORECASE))
    has_about_link = len(about_links) > 0

    if not has_about_link:
        issues.append({
            "severity": "high",
            "type": "no_about_link",
            "detail": "No link to an about page found",
        })
        score -= 15

    # --- Contact page link ---
    contact_links = soup.find_all("a", href=re.compile(r"/contact", re.IGNORECASE))
    has_contact_link = len(contact_links) > 0

    if not has_contact_link:
        issues.append({
            "severity": "high",
            "type": "no_contact_link",
            "detail": "No link to a contact page found",
        })
        score -= 15

    # --- Privacy/TOS links ---
    privacy_links = soup.find_all(
        "a", href=re.compile(r"/(privacy|terms|tos)", re.IGNORECASE)
    )
    has_privacy_link = len(privacy_links) > 0

    if not has_privacy_link:
        issues.append({
            "severity": "medium",
            "type": "no_privacy_link",
            "detail": "No privacy policy or terms of service link found",
        })
        score -= 10

    # --- Social media links ---
    social_links: list[str] = []
    all_links = soup.find_all("a", href=True)
    for link in all_links:
        href = link["href"]
        for domain in SOCIAL_DOMAINS:
            if domain in href and href not in social_links:
                social_links.append(href)

    if not social_links:
        issues.append({
            "severity": "low",
            "type": "no_social_links",
            "detail": "No social media links found",
        })
        score -= 5

    # --- Review/testimonial signals ---
    has_reviews = False

    # Check JSON-LD for Review type
    ld_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    for script in ld_scripts:
        try:
            data = json.loads(script.string or "")
            if data.get("@type") == "Review":
                has_reviews = True
                break
        except (json.JSONDecodeError, ValueError):
            pass

    # Check for elements with review/testimonial classes
    if not has_reviews:
        review_elements = soup.find_all(
            attrs={"class": re.compile(r"(review|testimonial)", re.IGNORECASE)}
        )
        if review_elements:
            has_reviews = True

    # --- Professional credentials ---
    body = soup.find("body")
    body_text = body.get_text(separator=" ", strip=True) if body else ""
    credentials_found: list[str] = []

    for pattern in CREDENTIAL_PATTERNS:
        matches = re.findall(pattern, body_text, re.IGNORECASE)
        credentials_found.extend(matches)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_creds: list[str] = []
    for cred in credentials_found:
        lower = cred.lower()
        if lower not in seen:
            seen.add(lower)
            unique_creds.append(cred)
    credentials_found = unique_creds

    score = max(score, 0)

    return make_result(
        tool="authority_auditor",
        url=url,
        score=score,
        issues=issues,
        data={
            "has_author": has_author,
            "author_name": author_name,
            "has_about_link": has_about_link,
            "has_contact_link": has_contact_link,
            "has_privacy_link": has_privacy_link,
            "social_links": social_links,
            "has_reviews": has_reviews,
            "credentials_found": credentials_found,
            "eeat_score_breakdown": {
                "author": has_author,
                "about_link": has_about_link,
                "contact_link": has_contact_link,
                "privacy_link": has_privacy_link,
                "social_links": len(social_links) > 0,
            },
        },
    )
