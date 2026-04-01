"""Image auditor — checks alt text, format, lazy loading, dimensions, and base64 usage."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from tools.base import make_result

MODERN_FORMATS = {".webp", ".avif"}
FILENAME_PATTERN = re.compile(r"^[\w\-]+\.\w{2,4}$", re.IGNORECASE)


def _get_format(src: str) -> str:
    """Extract file extension from src, handling query strings."""
    if not src or src.startswith("data:"):
        return "base64"
    clean = src.split("?")[0].split("#")[0]
    dot_pos = clean.rfind(".")
    if dot_pos == -1:
        return "unknown"
    return clean[dot_pos:].lower()


def audit(url: str, html: str, config: dict | None = None) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    issues: list[dict] = []
    score = 100

    images = soup.find_all("img")
    total_images = len(images)

    if total_images == 0:
        return make_result(
            tool="image_auditor",
            url=url,
            score=100,
            issues=[],
            data={
                "total_images": 0,
                "missing_alt_count": 0,
                "missing_dimensions_count": 0,
                "non_modern_format_count": 0,
                "missing_lazy_count": 0,
                "images": [],
            },
        )

    missing_alt_count = 0
    filename_alt_count = 0
    non_modern_count = 0
    missing_lazy_count = 0
    missing_dimensions_count = 0
    image_data: list[dict] = []

    for idx, img in enumerate(images):
        src = img.get("src", "")
        alt = img.get("alt")
        has_alt = alt is not None and alt.strip() != ""
        has_width = img.get("width") is not None
        has_height = img.get("height") is not None
        has_dimensions = has_width and has_height
        has_lazy = img.get("loading") == "lazy"
        fmt = _get_format(src)

        image_data.append({
            "src": src[:200],  # truncate very long data URIs
            "has_alt": has_alt,
            "has_dimensions": has_dimensions,
            "format": fmt,
            "has_lazy": has_lazy,
        })

        # Missing alt
        if not has_alt:
            missing_alt_count += 1
            if missing_alt_count <= 3:
                issues.append({"severity": "high", "type": "missing_alt", "detail": f"Image missing alt text: {src[:100]}"})

        # Filename as alt
        if has_alt and FILENAME_PATTERN.match(alt.strip()):
            filename_alt_count += 1
            if filename_alt_count <= 3:
                issues.append({"severity": "medium", "type": "filename_alt", "detail": f"Alt text appears to be a filename: '{alt.strip()}'"})

        # Non-modern format (skip first image for this check — actually spec says all images)
        if fmt not in MODERN_FORMATS and fmt not in ("base64", "unknown"):
            non_modern_count += 1
            if non_modern_count <= 3:
                issues.append({"severity": "low", "type": "non_modern_format", "detail": f"Image uses {fmt} format (consider .webp or .avif): {src[:100]}"})

        # Lazy loading — first image exempt
        if idx > 0 and not has_lazy:
            missing_lazy_count += 1
            if missing_lazy_count <= 3:
                issues.append({"severity": "low", "type": "missing_lazy_load", "detail": f"Image missing loading='lazy': {src[:100]}"})

        # Missing dimensions
        if not has_dimensions:
            missing_dimensions_count += 1
            if missing_dimensions_count <= 3:
                issues.append({"severity": "medium", "type": "missing_dimensions", "detail": f"Image missing width/height attributes: {src[:100]}"})

        # Large base64
        if src.startswith("data:image/") and len(src) > 5000:
            issues.append({"severity": "high", "type": "large_base64", "detail": f"Large inline base64 image ({len(src)} chars)"})
            score -= 10

    # --- Scoring ---
    score -= min(missing_alt_count * 10, 30)
    score -= min(filename_alt_count * 3, 9)
    score -= min(non_modern_count * 3, 9)
    score -= min(missing_lazy_count * 3, 9)
    score -= min(missing_dimensions_count * 5, 15)
    # base64 already deducted above

    score = max(score, 0)

    return make_result(
        tool="image_auditor",
        url=url,
        score=score,
        issues=issues,
        data={
            "total_images": total_images,
            "missing_alt_count": missing_alt_count,
            "missing_dimensions_count": missing_dimensions_count,
            "non_modern_format_count": non_modern_count,
            "missing_lazy_count": missing_lazy_count,
            "images": image_data,
        },
    )
