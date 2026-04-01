"""Tests for the CWV (Core Web Vitals) auditor."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from tools.base import validate_result
from tools.cwv_auditor import audit

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def pagespeed_response() -> dict:
    return json.loads((FIXTURES / "pagespeed_response.json").read_text())


# ---- 1. Missing API key ----

def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_PAGESPEED_API_KEY", raising=False)
    result = audit("https://example.com", "<html></html>")
    assert result["score"] is None
    assert len(result["issues"]) == 1
    assert result["issues"][0]["type"] == "skipped"
    assert result["issues"][0]["severity"] == "low"


# ---- 2. Good scores ----

@respx.mock
def test_good_scores(monkeypatch):
    monkeypatch.setenv("GOOGLE_PAGESPEED_API_KEY", "test-key")
    good_response = {
        "lighthouseResult": {
            "categories": {"performance": {"score": 0.95}},
            "audits": {
                "largest-contentful-paint": {"numericValue": 1800},
                "total-blocking-time": {"numericValue": 100},
                "cumulative-layout-shift": {"numericValue": 0.05},
                "first-contentful-paint": {"numericValue": 1200},
                "speed-index": {"numericValue": 2000},
            },
        }
    }
    respx.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed").mock(
        return_value=httpx.Response(200, json=good_response)
    )
    result = audit("https://example.com", "<html></html>")
    assert result["score"] == 95
    assert len(result["issues"]) == 0
    assert result["data"]["lcp_ms"] == 1800
    assert result["data"]["cls"] == 0.05


# ---- 3. Poor LCP ----

@respx.mock
def test_poor_lcp(monkeypatch):
    monkeypatch.setenv("GOOGLE_PAGESPEED_API_KEY", "test-key")
    poor_response = {
        "lighthouseResult": {
            "categories": {"performance": {"score": 0.35}},
            "audits": {
                "largest-contentful-paint": {"numericValue": 5000},
                "total-blocking-time": {"numericValue": 100},
                "cumulative-layout-shift": {"numericValue": 0.05},
                "first-contentful-paint": {"numericValue": 1200},
                "speed-index": {"numericValue": 2000},
            },
        }
    }
    respx.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed").mock(
        return_value=httpx.Response(200, json=poor_response)
    )
    result = audit("https://example.com", "<html></html>")
    assert result["score"] == 35
    critical_issues = [i for i in result["issues"] if i["severity"] == "critical"]
    assert len(critical_issues) >= 1
    assert any("LCP" in i["detail"] for i in critical_issues)


# ---- 4. Needs improvement ----

@respx.mock
def test_needs_improvement(monkeypatch, pagespeed_response):
    monkeypatch.setenv("GOOGLE_PAGESPEED_API_KEY", "test-key")
    respx.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed").mock(
        return_value=httpx.Response(200, json=pagespeed_response)
    )
    result = audit("https://example.com", "<html></html>")
    assert result["score"] == 72
    # LCP=3200 (needs-improvement), TBT=450 (needs-improvement), CLS=0.15 (needs-improvement)
    assert len(result["issues"]) >= 3
    severities = {i["severity"] for i in result["issues"]}
    assert "high" in severities  # LCP needs-improvement => high


# ---- 5. API error handling ----

@respx.mock
def test_api_error_handling(monkeypatch):
    monkeypatch.setenv("GOOGLE_PAGESPEED_API_KEY", "test-key")
    respx.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed").mock(
        return_value=httpx.Response(500, json={"error": {"message": "Internal error"}})
    )
    result = audit("https://example.com", "<html></html>")
    assert result["score"] is None
    assert any(i["type"] == "api_error" for i in result["issues"])


@respx.mock
def test_api_timeout(monkeypatch):
    monkeypatch.setenv("GOOGLE_PAGESPEED_API_KEY", "test-key")
    respx.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed").mock(
        side_effect=httpx.TimeoutException("Connection timed out")
    )
    result = audit("https://example.com", "<html></html>")
    assert result["score"] is None
    assert any(i["type"] == "api_error" for i in result["issues"])


# ---- 6. Contract compliance ----

@respx.mock
def test_contract_compliance(monkeypatch, pagespeed_response):
    monkeypatch.setenv("GOOGLE_PAGESPEED_API_KEY", "test-key")
    respx.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed").mock(
        return_value=httpx.Response(200, json=pagespeed_response)
    )
    result = audit("https://example.com", "<html></html>")
    assert validate_result(result)
    assert result["tool"] == "cwv_auditor"
    assert result["url"] == "https://example.com"


def test_contract_compliance_no_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_PAGESPEED_API_KEY", raising=False)
    result = audit("https://example.com", "<html></html>")
    assert validate_result(result)
