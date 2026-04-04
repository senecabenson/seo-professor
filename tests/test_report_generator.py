"""Tests for the PDF report generator."""

from unittest.mock import MagicMock, patch

import pytest

from src.report_generator import _render_html, generate_report, upload_report

SAMPLE_AGGREGATED = {
    "site_score": 72,
    "pages_audited": 3,
    "severity_counts": {"critical": 1, "high": 3, "medium": 5, "low": 8},
    "top_issues": [
        {"type": "missing_meta_description", "count": 2, "severity": "high"},
    ],
    "worst_pages": [
        {"url": "https://example.com/old", "score": 45, "issue_count": 8},
    ],
    "tool_summaries": {
        "onpage_auditor": {"avg_score": 70, "issue_count": 5},
        "link_auditor": {"avg_score": 85, "issue_count": 2},
    },
    "pages": {
        "https://example.com/": {
            "score": 72,
            "issue_count": 3,
            "issues": [
                {
                    "severity": "high",
                    "type": "missing_meta_description",
                    "detail": "No meta description",
                }
            ],
            "tool_results": {},
        }
    },
}

SAMPLE_AI_ANALYSIS = {
    "executive_summary": "The site has moderate SEO health with a score of 72/100.",
    "priority_fixes": [
        {
            "issue": "Add meta descriptions",
            "effort": "low",
            "impact": "high",
            "description": "Missing on 2 pages",
        }
    ],
    "category_analysis": {
        "onpage_auditor": {
            "score": 70,
            "assessment": "Needs improvement",
            "key_issues": ["Missing descriptions"],
        }
    },
    "recommendations": [
        {
            "action": "Add meta descriptions to all pages",
            "priority": 1,
            "rationale": "Quick win for CTR improvement",
        }
    ],
}


class TestRenderHtml:
    def test_render_html_returns_string(self):
        html = _render_html(SAMPLE_AGGREGATED, SAMPLE_AI_ANALYSIS)
        assert isinstance(html, str)
        assert "<html" in html
        assert "</html>" in html

    def test_render_html_contains_domain(self):
        html = _render_html(SAMPLE_AGGREGATED, SAMPLE_AI_ANALYSIS)
        assert "example.com" in html

    def test_render_html_contains_score(self):
        html = _render_html(SAMPLE_AGGREGATED, SAMPLE_AI_ANALYSIS)
        assert "72" in html

    def test_render_html_contains_sections(self):
        html = _render_html(SAMPLE_AGGREGATED, SAMPLE_AI_ANALYSIS)
        assert "Executive Summary" in html
        assert "Priority Fixes" in html
        assert "Detailed Findings" in html
        assert "Page-by-Page" in html
        assert "Recommendations" in html
        # Header section is implicit (contains domain/score), so check for
        # a 6th distinct section marker
        assert "SEO Audit Report" in html


class TestGenerateReport:
    def test_generate_report_creates_file(self, tmp_path):
        output = str(tmp_path / "report.pdf")
        result = generate_report(SAMPLE_AGGREGATED, SAMPLE_AI_ANALYSIS, output)
        assert result == output
        assert (tmp_path / "report.pdf").exists()

    def test_generate_report_valid_pdf(self, tmp_path):
        output = str(tmp_path / "report.pdf")
        generate_report(SAMPLE_AGGREGATED, SAMPLE_AI_ANALYSIS, output)
        with open(output, "rb") as f:
            magic = f.read(4)
        assert magic == b"%PDF"

    def test_generate_report_with_empty_ai_analysis(self, tmp_path):
        output = str(tmp_path / "report.pdf")
        result = generate_report(SAMPLE_AGGREGATED, {}, output)
        assert result == output
        assert (tmp_path / "report.pdf").exists()
        with open(output, "rb") as f:
            magic = f.read(4)
        assert magic == b"%PDF"

    def test_generate_report_creates_output_dir(self, tmp_path):
        output = str(tmp_path / "nested" / "dir" / "report.pdf")
        result = generate_report(SAMPLE_AGGREGATED, SAMPLE_AI_ANALYSIS, output)
        assert result == output
        assert (tmp_path / "nested" / "dir" / "report.pdf").exists()


class TestUploadReport:
    @patch("src.report_generator.get_client")
    def test_upload_report_mocked(self, mock_get_client, tmp_path):
        # Create a dummy PDF file
        pdf_path = str(tmp_path / "report.pdf")
        with open(pdf_path, "wb") as f:
            f.write(b"%PDF-1.4 fake content")

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_storage = mock_client.storage.from_.return_value
        mock_storage.upload.return_value = None
        mock_storage.get_public_url.return_value = "https://storage.example.com/reports/abc.pdf"

        url = upload_report(pdf_path, "audit-run-123")

        mock_client.storage.from_.assert_called_with("reports")
        mock_storage.upload.assert_called_once()
        assert url == "https://storage.example.com/reports/abc.pdf"
