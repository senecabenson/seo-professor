"""Tests for Supabase database layer (src/db.py). All tests mock the Supabase client."""

from unittest.mock import patch, MagicMock
import pytest
from src import db


def setup_function():
    """Reset singleton client between tests."""
    db.reset_client()


# ---------------------------------------------------------------------------
# get_client
# ---------------------------------------------------------------------------

def test_get_client_missing_env():
    """Raises ValueError when SUPABASE_URL/KEY not set."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="SUPABASE_URL and SUPABASE_KEY must be set"):
            db.get_client()


@patch("src.db.create_client")
def test_get_client_creates_client(mock_create_client):
    """With env vars set, creates and caches a client."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    with patch.dict("os.environ", {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test-key"}):
        result = db.get_client()
    assert result is mock_client
    mock_create_client.assert_called_once_with("https://test.supabase.co", "test-key")


# ---------------------------------------------------------------------------
# upsert_site
# ---------------------------------------------------------------------------

@patch.dict("os.environ", {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test-key"})
@patch("src.db.create_client")
def test_upsert_site(mock_create_client):
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.table.return_value.upsert.return_value.execute.return_value.data = [
        {"id": "uuid-1", "domain": "example.com", "name": "Example"}
    ]

    result = db.upsert_site("example.com", name="Example")

    assert result["domain"] == "example.com"
    assert result["name"] == "Example"
    mock_client.table.assert_called_with("sites")
    mock_client.table.return_value.upsert.assert_called_once_with(
        {"domain": "example.com", "name": "Example"}, on_conflict="domain"
    )


# ---------------------------------------------------------------------------
# get_site_by_domain
# ---------------------------------------------------------------------------

@patch.dict("os.environ", {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test-key"})
@patch("src.db.create_client")
def test_get_site_by_domain_found(mock_create_client):
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "uuid-1", "domain": "example.com"}
    ]

    result = db.get_site_by_domain("example.com")

    assert result is not None
    assert result["domain"] == "example.com"
    mock_client.table.assert_called_with("sites")


@patch.dict("os.environ", {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test-key"})
@patch("src.db.create_client")
def test_get_site_by_domain_not_found(mock_create_client):
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    result = db.get_site_by_domain("unknown.com")

    assert result is None


# ---------------------------------------------------------------------------
# create_audit_run
# ---------------------------------------------------------------------------

@patch.dict("os.environ", {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test-key"})
@patch("src.db.create_client")
def test_create_audit_run(mock_create_client):
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "run-1", "site_id": "site-1", "status": "running"}
    ]

    result = db.create_audit_run("site-1")

    assert result["status"] == "running"
    assert result["site_id"] == "site-1"
    mock_client.table.assert_called_with("audit_runs")
    mock_client.table.return_value.insert.assert_called_once_with(
        {"site_id": "site-1", "status": "running"}
    )


# ---------------------------------------------------------------------------
# update_audit_run
# ---------------------------------------------------------------------------

@patch.dict("os.environ", {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test-key"})
@patch("src.db.create_client")
def test_update_audit_run_completed(mock_create_client):
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {"id": "run-1", "status": "completed", "pages_crawled": 10, "completed_at": "2026-01-01T00:00:00+00:00"}
    ]

    result = db.update_audit_run("run-1", status="completed", pages_crawled=10)

    assert result["status"] == "completed"
    assert result["completed_at"] is not None
    # Verify the update data includes completed_at
    call_args = mock_client.table.return_value.update.call_args[0][0]
    assert "completed_at" in call_args
    assert call_args["status"] == "completed"
    assert call_args["pages_crawled"] == 10


# ---------------------------------------------------------------------------
# insert_page_result
# ---------------------------------------------------------------------------

@patch.dict("os.environ", {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test-key"})
@patch("src.db.create_client")
def test_insert_page_result(mock_create_client):
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "page-1", "audit_run_id": "run-1", "url": "https://example.com/", "status_code": 200}
    ]

    result = db.insert_page_result("run-1", "https://example.com/", 200, html_hash="abc123")

    assert result["url"] == "https://example.com/"
    assert result["status_code"] == 200
    mock_client.table.assert_called_with("page_results")
    mock_client.table.return_value.insert.assert_called_once_with(
        {"audit_run_id": "run-1", "url": "https://example.com/", "status_code": 200, "html_hash": "abc123"}
    )


# ---------------------------------------------------------------------------
# insert_findings
# ---------------------------------------------------------------------------

@patch.dict("os.environ", {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test-key"})
@patch("src.db.create_client")
def test_insert_findings_flattens_issues(mock_create_client):
    """Issues from multiple tools are flattened into individual rows."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "f1"}, {"id": "f2"}, {"id": "f3"}
    ]

    findings = [
        {
            "tool": "on_page_auditor",
            "issues": [
                {"severity": "high", "type": "missing_title", "detail": "No title tag"},
                {"severity": "medium", "type": "short_description", "detail": "Meta too short"},
            ],
            "data": {"score": 40},
        },
        {
            "tool": "link_auditor",
            "issues": [
                {"severity": "low", "type": "broken_link", "detail": "404 on /about"},
            ],
            "data": {},
        },
    ]

    result = db.insert_findings("page-1", findings)

    assert len(result) == 3
    # Verify 3 rows were inserted
    inserted_rows = mock_client.table.return_value.insert.call_args[0][0]
    assert len(inserted_rows) == 3
    assert inserted_rows[0]["tool"] == "on_page_auditor"
    assert inserted_rows[0]["severity"] == "high"
    assert inserted_rows[1]["tool"] == "on_page_auditor"
    assert inserted_rows[2]["tool"] == "link_auditor"


@patch.dict("os.environ", {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test-key"})
@patch("src.db.create_client")
def test_insert_findings_empty(mock_create_client):
    """No issues means no insert call, returns empty list."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client

    result = db.insert_findings("page-1", [{"tool": "on_page_auditor", "issues": []}])

    assert result == []
    mock_client.table.return_value.insert.assert_not_called()


# ---------------------------------------------------------------------------
# insert_report
# ---------------------------------------------------------------------------

@patch.dict("os.environ", {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test-key"})
@patch("src.db.create_client")
def test_insert_report(mock_create_client):
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "rpt-1", "audit_run_id": "run-1", "ai_analysis": "Good site", "report_url": "https://storage/report.pdf"}
    ]

    result = db.insert_report("run-1", "Good site", [{"action": "fix titles"}], "https://storage/report.pdf")

    assert result["ai_analysis"] == "Good site"
    mock_client.table.assert_called_with("reports")
    mock_client.table.return_value.insert.assert_called_once_with({
        "audit_run_id": "run-1",
        "ai_analysis": "Good site",
        "recommendations": [{"action": "fix titles"}],
        "report_url": "https://storage/report.pdf",
    })


# ---------------------------------------------------------------------------
# get_audit_history
# ---------------------------------------------------------------------------

@patch.dict("os.environ", {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test-key"})
@patch("src.db.create_client")
def test_get_audit_history(mock_create_client):
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    # First call: get_site_by_domain
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "site-1", "domain": "example.com"}
    ]
    # Second call: audit_runs query (chained select -> eq -> order -> execute)
    mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"id": "run-2", "status": "completed"},
        {"id": "run-1", "status": "completed"},
    ]

    result = db.get_audit_history("example.com")

    assert len(result) == 2


@patch.dict("os.environ", {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test-key"})
@patch("src.db.create_client")
def test_get_audit_history_unknown_domain(mock_create_client):
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    result = db.get_audit_history("unknown.com")

    assert result == []
