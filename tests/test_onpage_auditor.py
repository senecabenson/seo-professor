from tools.base import validate_result


URL = "https://example.com/blog/seo-guide"


class TestOnpagePerfectPage:
    def test_perfect_page_high_score(self, perfect_html):
        from tools.onpage_auditor import audit

        result = audit(URL, perfect_html)
        assert result["score"] >= 95

    def test_perfect_page_no_critical_issues(self, perfect_html):
        from tools.onpage_auditor import audit

        result = audit(URL, perfect_html)
        critical = [i for i in result["issues"] if i["severity"] in ("critical", "high")]
        assert len(critical) == 0


class TestOnpageSamplePage:
    def test_detects_missing_meta_description(self, sample_html):
        from tools.onpage_auditor import audit

        result = audit(URL, sample_html)
        types = [i["type"] for i in result["issues"]]
        assert "missing_meta_description" in types

    def test_detects_multiple_h1(self, sample_html):
        from tools.onpage_auditor import audit

        result = audit(URL, sample_html)
        types = [i["type"] for i in result["issues"]]
        assert "multiple_h1" in types

    def test_detects_title_too_long(self, sample_html):
        from tools.onpage_auditor import audit

        result = audit(URL, sample_html)
        types = [i["type"] for i in result["issues"]]
        assert "title_too_long" in types

    def test_detects_missing_og_tags(self, sample_html):
        from tools.onpage_auditor import audit

        result = audit(URL, sample_html)
        types = [i["type"] for i in result["issues"]]
        assert "missing_og_tags" in types

    def test_detects_missing_twitter_tags(self, sample_html):
        from tools.onpage_auditor import audit

        result = audit(URL, sample_html)
        types = [i["type"] for i in result["issues"]]
        assert "missing_twitter_tags" in types

    def test_detects_missing_canonical(self, sample_html):
        from tools.onpage_auditor import audit

        result = audit(URL, sample_html)
        types = [i["type"] for i in result["issues"]]
        assert "missing_canonical" in types

    def test_sample_score_below_perfect(self, sample_html):
        from tools.onpage_auditor import audit

        result = audit(URL, sample_html)
        assert result["score"] < 70


class TestOnpageMinimalPage:
    def test_flags_missing_elements(self, minimal_html):
        from tools.onpage_auditor import audit

        result = audit(URL, minimal_html)
        types = [i["type"] for i in result["issues"]]
        assert "missing_meta_description" in types
        assert "missing_h1" in types
        assert "missing_canonical" in types
        assert "low_word_count" in types

    def test_minimal_score_low(self, minimal_html):
        from tools.onpage_auditor import audit

        result = audit(URL, minimal_html)
        assert result["score"] < 50


class TestOnpageEmptyHtml:
    def test_empty_html_does_not_crash(self):
        from tools.onpage_auditor import audit

        result = audit(URL, "")
        assert result["score"] is not None
        assert isinstance(result["issues"], list)

    def test_completely_empty_page(self):
        from tools.onpage_auditor import audit

        result = audit(URL, "<html><head></head><body></body></html>")
        assert result["score"] < 30


class TestOnpageContractCompliance:
    def test_contract_compliance(self, perfect_html):
        from tools.onpage_auditor import audit

        result = audit(URL, perfect_html)
        assert validate_result(result) is True

    def test_contract_compliance_sample(self, sample_html):
        from tools.onpage_auditor import audit

        result = audit(URL, sample_html)
        assert validate_result(result) is True

    def test_contract_compliance_empty(self):
        from tools.onpage_auditor import audit

        result = audit(URL, "")
        assert validate_result(result) is True


class TestOnpageDataFields:
    def test_data_has_required_fields(self, perfect_html):
        from tools.onpage_auditor import audit

        result = audit(URL, perfect_html)
        data = result["data"]
        assert "title_length" in data
        assert "description_length" in data
        assert "h1_count" in data
        assert "word_count" in data
        assert "has_canonical" in data
        assert "has_og_tags" in data
        assert "has_twitter_tags" in data
        assert "heading_structure" in data

    def test_perfect_page_data_values(self, perfect_html):
        from tools.onpage_auditor import audit

        result = audit(URL, perfect_html)
        data = result["data"]
        assert data["h1_count"] == 1
        assert data["has_canonical"] is True
        assert data["has_og_tags"] is True
        assert data["has_twitter_tags"] is True
        assert data["word_count"] > 300


class TestOnpageEdgeCases:
    def test_heading_hierarchy_skip(self):
        """H1 directly to H3 should flag hierarchy issue."""
        from tools.onpage_auditor import audit

        html = "<html><head><title>Test Page Title Here</title></head><body><h1>Title</h1><h3>Skipped H2</h3><p>" + " word" * 300 + "</p></body></html>"
        result = audit(URL, html)
        types = [i["type"] for i in result["issues"]]
        assert "heading_hierarchy_skip" in types

    def test_short_title_warning(self):
        from tools.onpage_auditor import audit

        html = '<html><head><title>Hi</title><meta name="description" content="A decent description that is long enough to pass."></head><body><h1>Title</h1><p>' + " word" * 300 + "</p></body></html>"
        result = audit(URL, html)
        types = [i["type"] for i in result["issues"]]
        assert "title_too_short" in types
