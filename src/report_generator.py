"""PDF report generator using Jinja2 templates and WeasyPrint."""

import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import jinja2
import weasyprint

from src.db import get_client

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _extract_domain(aggregated_data: dict) -> str:
    """Extract domain from worst_pages or pages keys."""
    worst = aggregated_data.get("worst_pages", [])
    if worst:
        parsed = urlparse(worst[0].get("url", ""))
        if parsed.netloc:
            return parsed.netloc

    pages = aggregated_data.get("pages", {})
    if pages:
        first_url = next(iter(pages))
        parsed = urlparse(first_url)
        if parsed.netloc:
            return parsed.netloc

    return "Unknown Domain"


def _score_color(score: int) -> str:
    """Return hex color for a given score."""
    if score >= 90:
        return "#16a34a"
    if score >= 70:
        return "#ca8a04"
    if score >= 50:
        return "#ea580c"
    return "#dc2626"


def _render_html(aggregated_data: dict, ai_analysis: dict) -> str:
    """Render the Jinja2 template to an HTML string."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    env.filters["score_color"] = _score_color
    template = env.get_template("report.html")

    domain = _extract_domain(aggregated_data)
    context = {
        "domain": domain,
        "date": datetime.now().strftime("%B %d, %Y"),
        "site_score": aggregated_data.get("site_score", 0),
        "score_color": _score_color(aggregated_data.get("site_score", 0)),
        "pages_audited": aggregated_data.get("pages_audited", 0),
        "severity_counts": aggregated_data.get("severity_counts", {}),
        "executive_summary": ai_analysis.get("executive_summary", ""),
        "priority_fixes": ai_analysis.get("priority_fixes", []),
        "category_analysis": ai_analysis.get("category_analysis", {}),
        "recommendations": ai_analysis.get("recommendations", []),
        "top_issues": aggregated_data.get("top_issues", []),
        "worst_pages": aggregated_data.get("worst_pages", []),
        "tool_summaries": aggregated_data.get("tool_summaries", {}),
        "pages": aggregated_data.get("pages", {}),
    }
    return template.render(**context)


def generate_report(
    aggregated_data: dict, ai_analysis: dict, output_path: str
) -> str:
    """
    Render audit report as PDF.

    Args:
        aggregated_data: Output from src/aggregator.py
        ai_analysis: AI analysis dict with keys: executive_summary,
                     priority_fixes, category_analysis, recommendations
        output_path: Where to save the PDF

    Returns:
        The output_path where PDF was saved.
    """
    html_string = _render_html(aggregated_data, ai_analysis)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    weasyprint.HTML(
        string=html_string, base_url=str(TEMPLATES_DIR)
    ).write_pdf(output_path)
    return output_path


def upload_report(pdf_path: str, audit_run_id: str) -> str:
    """Upload PDF to Supabase Storage. Returns the public URL."""
    client = get_client()
    storage_path = f"{audit_run_id}/report.pdf"

    with open(pdf_path, "rb") as f:
        client.storage.from_("reports").upload(
            storage_path,
            f,
            {"content-type": "application/pdf"},
        )

    url = client.storage.from_("reports").get_public_url(storage_path)
    return url
