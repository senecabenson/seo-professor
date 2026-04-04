"""Tests for the AI analysis data formatter."""
import json

import pytest

from tests.factories import make_onpage_result, make_perfect_result
from tools.base import make_result
from src.aggregator import aggregate
from src.ai_analyzer import format_for_analysis


DOMAIN = "example.com"
URL1 = "https://example.com/"
URL2 = "https://example.com/about"


def _build_aggregated(num_pages=2):
    """Build aggregated data with a given number of pages."""
    results = {}
    for i in range(num_pages):
        url = f"https://example.com/page-{i}"
        results[url] = [
            make_onpage_result(url=url, score=max(10, 90 - i * 5)),
            make_result(
                tool="link_auditor",
                url=url,
                score=max(10, 80 - i * 3),
                issues=[
                    {"severity": "medium", "type": "broken_link", "detail": "404 on /old"},
                ],
            ),
        ]
    return aggregate(results)


class TestOutputStructure:
    def test_output_has_required_keys(self):
        agg = _build_aggregated(2)
        out = format_for_analysis(agg, DOMAIN)
        assert "prompt" in out
        assert "structured_input" in out

    def test_structured_input_is_json_serializable(self):
        agg = _build_aggregated(3)
        out = format_for_analysis(agg, DOMAIN)
        # Should not raise
        serialized = json.dumps(out["structured_input"])
        assert isinstance(serialized, str)


class TestPromptContents:
    def test_prompt_contains_domain(self):
        agg = _build_aggregated(2)
        out = format_for_analysis(agg, DOMAIN)
        assert DOMAIN in out["prompt"]

    def test_prompt_contains_score(self):
        agg = _build_aggregated(2)
        out = format_for_analysis(agg, DOMAIN)
        assert str(agg["site_score"]) in out["prompt"]

    def test_prompt_contains_severity_counts(self):
        agg = _build_aggregated(3)
        out = format_for_analysis(agg, DOMAIN)
        prompt = out["prompt"]
        for level in ("critical", "high", "medium", "low"):
            assert level in prompt

    def test_prompt_contains_top_issues(self):
        agg = _build_aggregated(3)
        out = format_for_analysis(agg, DOMAIN)
        prompt = out["prompt"]
        for issue in agg["top_issues"]:
            assert issue["type"] in prompt

    def test_prompt_contains_worst_pages(self):
        agg = _build_aggregated(3)
        out = format_for_analysis(agg, DOMAIN)
        prompt = out["prompt"]
        for page in agg["worst_pages"]:
            assert page["url"] in prompt

    def test_prompt_contains_instructions(self):
        agg = _build_aggregated(2)
        out = format_for_analysis(agg, DOMAIN)
        prompt = out["prompt"]
        assert "executive_summary" in prompt
        assert "priority_fixes" in prompt
        assert "category_analysis" in prompt
        assert "recommendations" in prompt


class TestLargeSiteTruncation:
    def test_large_site_truncation(self):
        agg = _build_aggregated(150)
        out = format_for_analysis(agg, DOMAIN)
        si = out["structured_input"]
        assert len(si["pages"]) == 10
        assert si["pages_trimmed"] is True
        assert si["pages_included"] == 10
        # Prompt should still have full summary stats
        assert str(agg["pages_audited"]) in out["prompt"]

    def test_small_site_no_truncation(self):
        agg = _build_aggregated(5)
        out = format_for_analysis(agg, DOMAIN)
        si = out["structured_input"]
        assert len(si["pages"]) == 5
        assert "pages_trimmed" not in si


class TestEdgeCases:
    def test_empty_audit_data(self):
        agg = aggregate({})
        out = format_for_analysis(agg, DOMAIN)
        assert "prompt" in out
        assert "structured_input" in out
        assert isinstance(out["prompt"], str)
        assert len(out["prompt"]) > 0
