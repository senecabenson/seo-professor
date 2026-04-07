"""Tests for the CLI orchestrator (src/audit.py)."""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from src.audit import (
    build_parser,
    validate_url,
    extract_domain,
    audit_page,
    run_audit,
    save_audit_data,
    main,
    show_history,
    _default_analysis,
    AUDIT_TOOLS,
)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class TestBuildParser:
    def test_build_parser_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["https://example.com"])
        assert args.url == "https://example.com"
        assert args.single_page is False
        assert args.history is None
        assert args.max_pages == 50
        assert args.output is None
        assert args.no_db is False


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

class TestValidateUrl:
    def test_validate_url_adds_scheme(self):
        assert validate_url("example.com") == "https://example.com"

    def test_validate_url_preserves_https(self):
        assert validate_url("https://example.com") == "https://example.com"

    def test_validate_url_preserves_http(self):
        assert validate_url("http://example.com") == "http://example.com"

    def test_validate_url_rejects_empty(self):
        with pytest.raises(ValueError):
            validate_url("")

    def test_validate_url_rejects_invalid(self):
        with pytest.raises(ValueError):
            validate_url("https://")


class TestExtractDomain:
    def test_extract_domain(self):
        assert extract_domain("https://www.example.com/path") == "www.example.com"


# ---------------------------------------------------------------------------
# audit_page
# ---------------------------------------------------------------------------

class TestAuditPage:
    @patch("src.audit.AUDIT_TOOLS")
    def test_audit_page_runs_all_tools(self, mock_tools):
        tools = [MagicMock() for _ in range(10)]
        for i, t in enumerate(tools):
            t.audit.return_value = {"tool": f"tool_{i}", "url": "u", "score": 80, "issues": [], "data": {}}
        mock_tools.__iter__ = lambda self: iter(tools)

        results = audit_page("https://example.com", "<html></html>")
        assert len(results) == 10
        for t in tools:
            t.audit.assert_called_once()

    @patch("src.audit.AUDIT_TOOLS")
    def test_audit_page_passes_headers_to_config(self, mock_tools):
        tool = MagicMock()
        tool.audit.return_value = {"tool": "t", "url": "u", "score": 80, "issues": [], "data": {}}
        mock_tools.__iter__ = lambda self: iter([tool])

        headers = {"x-frame-options": "DENY"}
        audit_page("https://example.com", "<html></html>", headers=headers)
        _, kwargs = tool.audit.call_args
        assert kwargs["config"]["headers"] == headers


# ---------------------------------------------------------------------------
# run_audit (async)
# ---------------------------------------------------------------------------

class TestRunAudit:
    @pytest.mark.asyncio
    @patch("src.audit.audit_page", return_value=[{"tool": "t", "score": 90, "issues": [], "data": {}}])
    @patch("src.audit.aggregate", return_value={"site_score": 90, "pages_audited": 1})
    async def test_run_audit_single_page(self, mock_agg, mock_ap):
        with patch("src.audit.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "<html></html>"
            mock_resp.headers = {"content-type": "text/html"}

            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_client

            result = await run_audit("https://example.com", single_page=True)
            assert result["aggregated"]["site_score"] == 90
            assert len(result["pages"]) == 1
            mock_client.get.assert_called_once_with("https://example.com")

    @pytest.mark.asyncio
    @patch("src.audit.audit_page", return_value=[{"tool": "t", "score": 85, "issues": [], "data": {}}])
    @patch("src.audit.aggregate", return_value={"site_score": 85, "pages_audited": 3})
    @patch("src.audit.crawler")
    async def test_run_audit_full_crawl(self, mock_crawler, mock_agg, mock_ap):
        mock_crawler.crawl = AsyncMock(return_value=[
            {"url": f"https://example.com/{i}", "status_code": 200, "html": "<html></html>", "headers": {}}
            for i in range(3)
        ])
        result = await run_audit("https://example.com", max_pages=20)
        mock_crawler.crawl.assert_called_once_with("https://example.com", config={"max_pages": 20})
        assert result["aggregated"]["pages_audited"] == 3


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

class TestShowHistory:
    @patch("src.audit.db")
    def test_main_history_mode(self, mock_db, capsys):
        mock_db.get_audit_history.return_value = [
            {"status": "completed", "overall_score": 85, "pages_crawled": 10, "started_at": "2026-01-01"},
        ]
        show_history("example.com")
        output = capsys.readouterr().out
        assert "example.com" in output
        assert "85" in output


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_main_requires_url_without_history(self):
        with pytest.raises(SystemExit):
            main([])

    def test_default_analysis_structure(self):
        result = _default_analysis()
        assert "executive_summary" in result
        assert "priority_fixes" in result
        assert "category_analysis" in result
        assert "recommendations" in result

    def test_save_audit_data_creates_file(self, tmp_path):
        data_path = tmp_path / "audit_data.json"
        with patch("src.audit.AUDIT_DATA_PATH", str(data_path)), \
             patch("src.audit.TMP_DIR", str(tmp_path)):
            save_audit_data({"score": 80}, {"prompt": "test"}, "example.com")
        assert data_path.exists()
        content = json.loads(data_path.read_text())
        assert content["aggregated"]["score"] == 80


# ---------------------------------------------------------------------------
# Full pipeline integration (main)
# ---------------------------------------------------------------------------

class TestMainPipeline:
    def _mock_run_audit_return(self):
        return {
            "aggregated": {
                "site_score": 80,
                "pages_audited": 1,
                "severity_counts": {"high": 1},
                "pages": {
                    "https://example.com": {
                        "tool_results": {
                            "onpage_auditor": {"issues": [], "data": {}}
                        }
                    }
                },
            },
            "pages": [
                {"url": "https://example.com", "status_code": 200, "html": "<html></html>", "headers": {}},
            ],
        }

    @patch("src.audit.generate_report")
    @patch("src.audit.load_analysis_if_ready", return_value=_default_analysis())
    @patch("src.audit.format_for_analysis", return_value={"prompt": "test", "structured_input": {}})
    @patch("src.audit.asyncio")
    def test_main_full_pipeline_no_db(self, mock_asyncio, mock_fmt, mock_wait, mock_gen, tmp_path):
        mock_asyncio.run.return_value = self._mock_run_audit_return()
        out_path = str(tmp_path / "report.pdf")

        main(["https://example.com", "--no-db", "--output", out_path])

        mock_asyncio.run.assert_called_once()
        mock_gen.assert_called_once()
        # Verify db was NOT called — no patch on db means it would fail if called

    @patch("src.audit.upload_report", return_value="https://cdn.example.com/report.pdf")
    @patch("src.audit.db")
    @patch("src.audit.generate_report")
    @patch("src.audit.load_analysis_if_ready", return_value=_default_analysis())
    @patch("src.audit.format_for_analysis", return_value={"prompt": "test", "structured_input": {}})
    @patch("src.audit.asyncio")
    def test_main_full_pipeline_with_db(self, mock_asyncio, mock_fmt, mock_wait,
                                         mock_gen, mock_db, mock_upload, tmp_path):
        mock_asyncio.run.return_value = self._mock_run_audit_return()
        mock_db.upsert_site.return_value = {"id": "site-1"}
        mock_db.create_audit_run.return_value = {"id": "run-1"}
        mock_db.insert_page_result.return_value = {"id": "page-1"}
        mock_db.insert_findings.return_value = []
        mock_db.insert_report.return_value = {"id": "report-1"}
        mock_db.update_audit_run.return_value = {"id": "run-1"}
        out_path = str(tmp_path / "report.pdf")

        main(["https://example.com", "--output", out_path])

        mock_db.upsert_site.assert_called_once_with("example.com")
        mock_db.create_audit_run.assert_called_once_with("site-1")
        mock_db.insert_page_result.assert_called_once()
        mock_upload.assert_called_once()
