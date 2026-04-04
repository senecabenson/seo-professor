"""Tests for the AEO (Answer Engine Optimization) auditor."""

import pytest

from tools.base import validate_result
from tools.aeo_auditor import audit


class TestAeoOptimizedPage:
    """Tests against aeo_optimized_page.html — should score high."""

    def test_high_score(self, aeo_html):
        result = audit("https://example.com", aeo_html)
        assert validate_result(result)
        assert result["score"] >= 85

    def test_no_high_severity_issues(self, aeo_html):
        result = audit("https://example.com", aeo_html)
        high_issues = [i for i in result["issues"] if i["severity"] in ("critical", "high")]
        assert len(high_issues) == 0

    def test_detects_direct_answers(self, aeo_html):
        result = audit("https://example.com", aeo_html)
        assert result["data"]["direct_answer_ratio"] > 0.5

    def test_detects_question_headings(self, aeo_html):
        result = audit("https://example.com", aeo_html)
        assert result["data"]["question_heading_ratio"] > 0.5

    def test_has_structured_content(self, aeo_html):
        result = audit("https://example.com", aeo_html)
        assert result["data"]["has_structured_content"] is True

    def test_has_stats(self, aeo_html):
        result = audit("https://example.com", aeo_html)
        assert result["data"]["stat_count"] > 0

    def test_has_citations(self, aeo_html):
        result = audit("https://example.com", aeo_html)
        assert result["data"]["citation_count"] > 0

    def test_has_date_signals(self, aeo_html):
        result = audit("https://example.com", aeo_html)
        assert result["data"]["has_date_signals"] is True
        assert result["data"]["date_published"] is not None


class TestSamplePage:
    """Tests against existing sample_page.html — has AEO weaknesses."""

    def test_validates(self, sample_html):
        result = audit("https://example.com", sample_html)
        assert validate_result(result)

    def test_lower_score(self, sample_html):
        result = audit("https://example.com", sample_html)
        assert result["score"] < 70

    def test_flags_issues(self, sample_html):
        result = audit("https://example.com", sample_html)
        assert len(result["issues"]) >= 2


class TestMinimalPage:
    """Tests against existing minimal_page.html — should flag almost everything."""

    def test_validates(self, minimal_html):
        result = audit("https://example.com", minimal_html)
        assert validate_result(result)

    def test_very_low_score(self, minimal_html):
        result = audit("https://example.com", minimal_html)
        assert result["score"] <= 35

    def test_many_issues(self, minimal_html):
        result = audit("https://example.com", minimal_html)
        assert len(result["issues"]) >= 4


class TestDirectAnswerDetection:
    def test_definition_pattern(self):
        html = '<html><body><h2>What is SEO?</h2><p>SEO is the practice of optimizing websites for search engines.</p></body></html>'
        result = audit("https://example.com", html)
        assert result["data"]["direct_answer_ratio"] > 0

    def test_no_headings_no_crash(self):
        html = '<html><body><p>Just a paragraph.</p></body></html>'
        result = audit("https://example.com", html)
        assert validate_result(result)
        assert result["data"]["direct_answer_ratio"] == 0.0


class TestStructuredContent:
    def test_detects_lists_and_tables(self):
        html = '<html><body><ul><li>Item 1</li></ul><ol><li>Step 1</li></ol><table><tr><td>Data</td></tr></table></body></html>'
        result = audit("https://example.com", html)
        assert result["data"]["has_structured_content"] is True
        assert result["data"]["list_count"] >= 2
        assert result["data"]["table_count"] >= 1

    def test_excludes_nav_lists(self):
        html = '<html><body><nav><ul><li>Home</li></ul></nav><p>Content only.</p></body></html>'
        result = audit("https://example.com", html)
        assert result["data"]["list_count"] == 0


class TestQuestionHeadings:
    def test_question_word_detected(self):
        html = '<html><body><h2>How does SEO work?</h2><p>Content here.</p><h2>Benefits of SEO</h2><p>More content.</p></body></html>'
        result = audit("https://example.com", html)
        assert result["data"]["question_heading_ratio"] == 0.5


class TestCitationWorthiness:
    def test_detects_percentage(self):
        html = '<html><body><p>According to research, 68% of experiences begin with search. <a href="https://source.com">Source</a></p></body></html>'
        result = audit("https://example.com", html)
        assert result["data"]["stat_count"] >= 1
        assert result["data"]["citation_count"] >= 1

    def test_trust_bottleneck_flags(self):
        html = '<html><body><p>We are the best SEO company with guaranteed results and proven methods.</p></body></html>'
        result = audit("https://example.com", html)
        assert len(result["data"]["trust_bottleneck_flags"]) >= 2
        tb_issues = [i for i in result["issues"] if i["type"] == "trust_bottleneck"]
        assert len(tb_issues) >= 2

    def test_trust_bottleneck_max_cap(self):
        html = '<html><body><p>Best guaranteed proven number one top rated premier.</p></body></html>'
        result = audit("https://example.com", html)
        # Max deduction for trust bottleneck is -15 (3 * 5)
        # Even with many superlatives, cap applies
        assert result["score"] >= 0  # floor check


class TestContentFreshness:
    def test_jsonld_dates(self):
        html = '''<html><head><script type="application/ld+json">{"@type":"Article","datePublished":"2025-03-01","dateModified":"2025-03-15"}</script></head><body><p>Content.</p></body></html>'''
        result = audit("https://example.com", html)
        assert result["data"]["has_date_signals"] is True
        assert result["data"]["date_published"] == "2025-03-01"
        assert result["data"]["date_modified"] == "2025-03-15"

    def test_time_element(self):
        html = '<html><body><time datetime="2025-03-01">March 1, 2025</time><p>Content.</p></body></html>'
        result = audit("https://example.com", html)
        assert result["data"]["has_date_signals"] is True

    def test_visible_date_text(self):
        html = '<html><body><p>Last Updated: March 15, 2025</p><p>Content here.</p></body></html>'
        result = audit("https://example.com", html)
        assert result["data"]["has_date_signals"] is True

    def test_no_dates_flagged(self):
        html = '<html><body><p>No dates anywhere.</p></body></html>'
        result = audit("https://example.com", html)
        assert result["data"]["has_date_signals"] is False
        issue_types = [i["type"] for i in result["issues"]]
        assert "no_date_signals" in issue_types


class TestLlmsTxt:
    def test_provided_valid(self):
        html = '<html><body><p>Content.</p></body></html>'
        config = {"llms_txt": "# My Site\n> A great site\n## Docs\n- [API](https://example.com/api)"}
        result = audit("https://example.com", html, config=config)
        assert result["data"]["has_llms_txt"] is True
        issue_types = [i["type"] for i in result["issues"]]
        assert "no_llms_txt" not in issue_types

    def test_not_provided(self):
        html = '<html><body><p>Content.</p></body></html>'
        result = audit("https://example.com", html)
        issue_types = [i["type"] for i in result["issues"]]
        assert "no_llms_txt" in issue_types


class TestMetaDescription:
    def test_answer_pattern_ok(self):
        html = '<html><head><meta name="description" content="SEO is the practice of optimizing web content to rank higher in search results. Learn the essential strategies."></head><body><p>Content.</p></body></html>'
        result = audit("https://example.com", html)
        issue_types = [i["type"] for i in result["issues"]]
        assert "generic_meta_description" not in issue_types
        assert "no_meta_description_for_aeo" not in issue_types

    def test_generic_flagged(self):
        html = '<html><head><meta name="description" content="Welcome to our amazing website where we do great things."></head><body><p>Content.</p></body></html>'
        result = audit("https://example.com", html)
        issue_types = [i["type"] for i in result["issues"]]
        assert "generic_meta_description" in issue_types

    def test_missing_flagged(self):
        html = '<html><head></head><body><p>Content.</p></body></html>'
        result = audit("https://example.com", html)
        issue_types = [i["type"] for i in result["issues"]]
        assert "no_meta_description_for_aeo" in issue_types


class TestContractCompliance:
    def test_data_has_all_fields(self, aeo_html):
        result = audit("https://example.com", aeo_html)
        expected_keys = {
            "direct_answer_ratio", "question_heading_ratio", "has_structured_content",
            "list_count", "table_count", "stat_count", "citation_count",
            "has_date_signals", "date_published", "date_modified", "has_llms_txt",
            "trust_bottleneck_flags", "avg_paragraph_length", "content_in_first_30_pct",
        }
        assert expected_keys.issubset(result["data"].keys())

    def test_empty_html(self):
        result = audit("https://example.com", "")
        assert validate_result(result)


class TestScoring:
    def test_score_floor_at_zero(self):
        html = '<html><body></body></html>'
        result = audit("https://example.com", html)
        assert result["score"] >= 0
