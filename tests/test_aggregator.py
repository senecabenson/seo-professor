"""Tests for the audit result aggregator."""
import pytest
from tests.factories import make_onpage_result, make_perfect_result, make_skipped_result
from tools.base import make_result
from src.aggregator import (
    aggregate,
    score_page,
    count_severities,
    rank_issues,
    get_worst_pages,
    get_tool_summaries,
)


URL1 = "https://example.com/"
URL2 = "https://example.com/about"
URL3 = "https://example.com/contact"


def _link_result(url, score=90, issues=None):
    if issues is None:
        issues = [{"severity": "medium", "type": "broken_link", "detail": "404 on /old"}]
    return make_result(tool="link_auditor", url=url, score=score, issues=issues)


def _image_result(url, score=70, issues=None):
    if issues is None:
        issues = [{"severity": "medium", "type": "missing_alt_text", "detail": "img has no alt"}]
    return make_result(tool="image_auditor", url=url, score=score, issues=issues)


class TestSinglePageSingleTool:
    def test_basic_aggregation(self):
        results = {URL1: [make_onpage_result(url=URL1, score=85)]}
        out = aggregate(results)
        assert out["site_score"] == 85
        assert out["pages_audited"] == 1
        assert URL1 in out["pages"]
        assert out["pages"][URL1]["score"] == 85
        assert out["pages"][URL1]["issue_count"] == 1

    def test_severity_counts_present(self):
        results = {URL1: [make_onpage_result(url=URL1, score=85)]}
        out = aggregate(results)
        assert out["severity_counts"]["high"] == 1
        assert out["severity_counts"]["critical"] == 0


class TestSinglePageMultipleTools:
    def test_page_score_is_average(self):
        results = {
            URL1: [
                make_onpage_result(url=URL1, score=80, issues=[]),
                _link_result(URL1, score=90, issues=[]),
                _image_result(URL1, score=70, issues=[]),
            ]
        }
        out = aggregate(results)
        assert out["pages"][URL1]["score"] == 80  # (80+90+70)/3
        assert out["site_score"] == 80


class TestMultiplePages:
    def test_site_score_is_average_of_page_scores(self):
        results = {
            URL1: [make_onpage_result(url=URL1, score=90, issues=[])],
            URL2: [make_onpage_result(url=URL2, score=60, issues=[])],
            URL3: [make_onpage_result(url=URL3, score=30, issues=[])],
        }
        out = aggregate(results)
        assert out["pages_audited"] == 3
        assert out["site_score"] == 60  # (90+60+30)/3

    def test_worst_pages_sorted(self):
        results = {
            URL1: [make_onpage_result(url=URL1, score=90, issues=[])],
            URL2: [make_onpage_result(url=URL2, score=60, issues=[])],
            URL3: [make_onpage_result(url=URL3, score=30, issues=[])],
        }
        out = aggregate(results)
        assert out["worst_pages"][0]["url"] == URL3
        assert out["worst_pages"][0]["score"] == 30
        assert out["worst_pages"][-1]["url"] == URL1


class TestNoneScoreHandling:
    def test_skipped_tool_excluded_from_score(self):
        results = {
            URL1: [
                make_onpage_result(url=URL1, score=80, issues=[]),
                make_skipped_result(tool="cwv_auditor", url=URL1),
            ]
        }
        out = aggregate(results)
        # Score should be 80, not (80+0)/2
        assert out["pages"][URL1]["score"] == 80

    def test_skipped_tool_issues_still_counted(self):
        results = {
            URL1: [
                make_result("onpage_auditor", URL1, 80, []),
                make_skipped_result(tool="cwv_auditor", url=URL1),
            ]
        }
        out = aggregate(results)
        assert out["severity_counts"]["low"] == 1  # the "skipped" issue
        assert out["pages"][URL1]["issue_count"] == 1


class TestSeverityCounting:
    def test_exact_counts(self):
        issues_mix = [
            {"severity": "critical", "type": "a", "detail": "x"},
            {"severity": "critical", "type": "b", "detail": "x"},
            {"severity": "high", "type": "c", "detail": "x"},
            {"severity": "medium", "type": "d", "detail": "x"},
            {"severity": "medium", "type": "e", "detail": "x"},
            {"severity": "medium", "type": "f", "detail": "x"},
            {"severity": "low", "type": "g", "detail": "x"},
        ]
        counts = count_severities(issues_mix)
        assert counts == {"critical": 2, "high": 1, "medium": 3, "low": 1}


class TestTopIssuesRanking:
    def test_ranking_by_frequency(self):
        results = {
            URL1: [
                make_result("onpage_auditor", URL1, 70, [
                    {"severity": "high", "type": "missing_meta_description", "detail": "x"},
                    {"severity": "medium", "type": "missing_alt_text", "detail": "x"},
                ]),
            ],
            URL2: [
                make_result("onpage_auditor", URL2, 70, [
                    {"severity": "high", "type": "missing_meta_description", "detail": "x"},
                    {"severity": "medium", "type": "missing_alt_text", "detail": "x"},
                ]),
            ],
            URL3: [
                make_result("onpage_auditor", URL3, 70, [
                    {"severity": "high", "type": "missing_meta_description", "detail": "x"},
                ]),
            ],
        }
        out = aggregate(results)
        assert out["top_issues"][0]["type"] == "missing_meta_description"
        assert out["top_issues"][0]["count"] == 3
        assert out["top_issues"][1]["type"] == "missing_alt_text"
        assert out["top_issues"][1]["count"] == 2


class TestWorstPagesLimit:
    def test_returns_max_10(self):
        results = {}
        for i in range(15):
            url = f"https://example.com/page-{i}"
            results[url] = [make_onpage_result(url=url, score=i * 6, issues=[])]
        out = aggregate(results)
        assert len(out["worst_pages"]) == 10
        # First should be lowest score
        assert out["worst_pages"][0]["score"] == 0


class TestToolSummaries:
    def test_per_tool_stats(self):
        results = {
            URL1: [
                make_onpage_result(url=URL1, score=80, issues=[
                    {"severity": "high", "type": "a", "detail": "x"},
                ]),
                _link_result(URL1, score=90, issues=[
                    {"severity": "medium", "type": "b", "detail": "x"},
                ]),
            ],
            URL2: [
                make_result("onpage_auditor", URL2, 60, [
                    {"severity": "high", "type": "a", "detail": "x"},
                    {"severity": "low", "type": "c", "detail": "x"},
                ]),
                _link_result(URL2, score=100, issues=[]),
            ],
        }
        out = aggregate(results)
        assert out["tool_summaries"]["onpage_auditor"]["avg_score"] == 70  # (80+60)/2
        assert out["tool_summaries"]["onpage_auditor"]["issue_count"] == 3
        assert out["tool_summaries"]["link_auditor"]["avg_score"] == 95  # (90+100)/2
        assert out["tool_summaries"]["link_auditor"]["issue_count"] == 1


class TestEmptyInput:
    def test_empty_dict(self):
        out = aggregate({})
        assert out["site_score"] == 0
        assert out["pages_audited"] == 0
        assert out["severity_counts"] == {"critical": 0, "high": 0, "medium": 0, "low": 0}
        assert out["top_issues"] == []
        assert out["worst_pages"] == []
        assert out["tool_summaries"] == {}
        assert out["pages"] == {}


class TestAllPerfectScores:
    def test_clean_aggregation(self):
        results = {
            URL1: [
                make_perfect_result("onpage_auditor", URL1),
                make_perfect_result("link_auditor", URL1),
            ],
            URL2: [
                make_perfect_result("onpage_auditor", URL2),
                make_perfect_result("link_auditor", URL2),
            ],
        }
        out = aggregate(results)
        assert out["site_score"] == 100
        assert out["severity_counts"] == {"critical": 0, "high": 0, "medium": 0, "low": 0}
        assert out["top_issues"] == []
        for url in [URL1, URL2]:
            assert out["pages"][url]["score"] == 100
            assert out["pages"][url]["issue_count"] == 0


class TestScorePage:
    def test_weighted_average(self):
        tools = [
            make_result("a", URL1, 80, []),
            make_result("b", URL1, 60, []),
        ]
        assert score_page(tools) == 70

    def test_skips_none(self):
        tools = [
            make_result("a", URL1, 80, []),
            make_result("b", URL1, None, []),
        ]
        assert score_page(tools) == 80

    def test_all_none_returns_zero(self):
        tools = [
            make_result("a", URL1, None, []),
            make_result("b", URL1, None, []),
        ]
        assert score_page(tools) == 0


class TestRankIssues:
    def test_groups_and_sorts(self):
        issues = [
            {"severity": "high", "type": "x", "detail": "a"},
            {"severity": "high", "type": "x", "detail": "b"},
            {"severity": "low", "type": "y", "detail": "c"},
        ]
        ranked = rank_issues(issues)
        assert ranked[0] == {"type": "x", "count": 2, "severity": "high"}
        assert ranked[1] == {"type": "y", "count": 1, "severity": "low"}


class TestGetWorstPages:
    def test_sorted_and_limited(self):
        pages = {
            "https://a.com": {"score": 90, "issue_count": 1, "issues": [], "tool_results": {}},
            "https://b.com": {"score": 30, "issue_count": 5, "issues": [], "tool_results": {}},
            "https://c.com": {"score": 60, "issue_count": 3, "issues": [], "tool_results": {}},
        }
        worst = get_worst_pages(pages, limit=2)
        assert len(worst) == 2
        assert worst[0]["url"] == "https://b.com"
        assert worst[1]["url"] == "https://c.com"


class TestGetToolSummaries:
    def test_computes_averages(self):
        results = {
            URL1: [make_result("t1", URL1, 80, [{"severity": "high", "type": "a", "detail": "x"}])],
            URL2: [make_result("t1", URL2, 60, [])],
        }
        summaries = get_tool_summaries(results)
        assert summaries["t1"]["avg_score"] == 70
        assert summaries["t1"]["issue_count"] == 1
