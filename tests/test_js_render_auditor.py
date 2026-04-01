"""Tests for the JS render auditor."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.base import validate_result
from tools.js_render_auditor import audit

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


# ---- 1. SPA page ----

def test_spa_page():
    html = _load("spa_page.html")
    result = audit("https://example.com", html)
    assert result["data"]["has_spa_root"] is True
    assert result["data"]["spa_root_empty"] is True
    # Empty SPA root => critical issue, -30
    critical = [i for i in result["issues"] if i["severity"] == "critical"]
    assert len(critical) >= 1
    assert result["score"] <= 70


# ---- 2. Perfect page (server-rendered) ----

def test_perfect_page():
    html = _load("perfect_page.html")
    result = audit("https://example.com", html)
    assert result["data"]["has_spa_root"] is False
    assert result["data"]["spa_root_empty"] is False
    assert result["score"] >= 80


# ---- 3. Sample page ----

def test_sample_page():
    html = _load("sample_page.html")
    result = audit("https://example.com", html)
    assert result["data"]["has_noscript"] is True
    assert result["score"] >= 70


# ---- 4. Minimal page ----

def test_minimal_page():
    html = _load("minimal_page.html")
    result = audit("https://example.com", html)
    assert result["score"] >= 90


# ---- 5. Empty HTML ----

def test_empty_html():
    result = audit("https://example.com", "")
    assert validate_result(result)
    # Should handle gracefully without crashing
    assert isinstance(result["score"], int)


# ---- 6. Heavy scripts ----

def test_heavy_scripts():
    scripts = "\n".join(f'<script src="/js/chunk{i}.js"></script>' for i in range(16))
    html = f"<html><head></head><body><p>Some content</p>{scripts}</body></html>"
    result = audit("https://example.com", html)
    assert result["data"]["external_script_count"] == 16
    medium_or_higher = [i for i in result["issues"] if i["severity"] in ("medium", "high")]
    assert len(medium_or_higher) >= 1
    assert result["score"] < 100


def test_very_heavy_scripts():
    scripts = "\n".join(f'<script src="/js/chunk{i}.js"></script>' for i in range(25))
    html = f"<html><head></head><body><p>Some content</p>{scripts}</body></html>"
    result = audit("https://example.com", html)
    assert result["data"]["external_script_count"] == 25
    high_issues = [i for i in result["issues"] if i["severity"] == "high"]
    assert len(high_issues) >= 1


# ---- 7. Fragment meta ----

def test_fragment_meta():
    html = '<html><head><meta name="fragment" content="!"></head><body><p>Content</p></body></html>'
    result = audit("https://example.com", html)
    assert result["data"]["has_fragment_meta"] is True
    assert any(i["type"] == "deprecated_fragment_meta" for i in result["issues"])
    assert result["score"] <= 85


# ---- 8. Contract compliance ----

def test_contract_compliance():
    html = _load("spa_page.html")
    result = audit("https://example.com", html)
    assert validate_result(result)
    assert result["tool"] == "js_render_auditor"
    assert result["url"] == "https://example.com"
