"""Security auditor — checks HTTPS, mixed content, and security response headers."""

from __future__ import annotations

from bs4 import BeautifulSoup

from tools.base import make_result

SECURITY_HEADERS = {
    "Content-Security-Policy": 10,
    "X-Frame-Options": 5,
    "Strict-Transport-Security": 10,
    "X-Content-Type-Options": 5,
    "Referrer-Policy": 5,
}


def audit(url: str, html: str, config: dict | None = None) -> dict:
    config = config or {}
    soup = BeautifulSoup(html, "html.parser")
    issues: list[dict] = []
    score = 100

    is_https = url.startswith("https://")

    # --- HTTPS check ---
    if not is_https:
        issues.append({"severity": "critical", "type": "http_url", "detail": "Page served over HTTP instead of HTTPS"})
        score -= 25

    # --- Mixed content (only relevant on HTTPS pages) ---
    mixed_content_urls: list[str] = []
    if is_https:
        # Check all elements with src or href attributes
        for tag in soup.find_all(True):
            for attr in ("src", "href"):
                val = tag.get(attr, "")
                if isinstance(val, str) and val.startswith("http://"):
                    mixed_content_urls.append(val)

        mixed_deduction = 0
        for i, mc_url in enumerate(mixed_content_urls):
            if i >= 3:
                break
            issues.append({"severity": "high", "type": "mixed_content", "detail": f"Mixed content resource: {mc_url[:200]}"})
        mixed_deduction = min(len(mixed_content_urls) * 10, 30)
        score -= mixed_deduction

    # --- Security headers ---
    headers = config.get("headers", {})
    # Normalize header keys to be case-insensitive
    headers_lower = {k.lower(): v for k, v in headers.items()}

    security_header_status = {}
    for header_name, deduction in SECURITY_HEADERS.items():
        present = header_name.lower() in headers_lower
        security_header_status[header_name] = present
        if not present:
            severity = "medium" if deduction >= 10 else "low"
            issues.append({
                "severity": severity,
                "type": "missing_security_header",
                "detail": f"Missing security header: {header_name}",
            })
            score -= deduction

    score = max(score, 0)

    return make_result(
        tool="security_auditor",
        url=url,
        score=score,
        issues=issues,
        data={
            "is_https": is_https,
            "mixed_content_urls": mixed_content_urls,
            "security_headers": security_header_status,
        },
    )
