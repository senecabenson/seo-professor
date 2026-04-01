from tools.base import validate_result


URL = "https://example.com/blog/seo-guide"


class TestLinkPerfectPage:
    def test_perfect_page_high_score(self, perfect_html):
        from tools.link_auditor import audit

        result = audit(URL, perfect_html)
        assert result["score"] >= 90

    def test_perfect_page_no_critical_issues(self, perfect_html):
        from tools.link_auditor import audit

        result = audit(URL, perfect_html)
        critical = [i for i in result["issues"] if i["severity"] in ("critical", "high")]
        assert len(critical) == 0


class TestLinkSamplePage:
    def test_detects_empty_anchor(self, sample_html):
        from tools.link_auditor import audit

        result = audit(URL, sample_html)
        types = [i["type"] for i in result["issues"]]
        assert "empty_anchor_text" in types

    def test_detects_poor_anchor(self, sample_html):
        from tools.link_auditor import audit

        result = audit(URL, sample_html)
        types = [i["type"] for i in result["issues"]]
        assert "poor_anchor_text" in types

    def test_sample_has_internal_links(self, sample_html):
        from tools.link_auditor import audit

        result = audit(URL, sample_html)
        assert result["data"]["internal_link_count"] > 0

    def test_sample_score_below_perfect(self, sample_html, perfect_html):
        from tools.link_auditor import audit

        sample = audit(URL, sample_html)
        perfect = audit(URL, perfect_html)
        assert sample["score"] < perfect["score"]


class TestLinkMinimalPage:
    def test_minimal_page_zero_links(self, minimal_html):
        from tools.link_auditor import audit

        result = audit(URL, minimal_html)
        assert result["data"]["total_links"] == 0

    def test_minimal_page_deduction_for_no_links(self, minimal_html):
        from tools.link_auditor import audit

        result = audit(URL, minimal_html)
        assert result["score"] <= 80


class TestLinkEmptyHtml:
    def test_empty_html_does_not_crash(self):
        from tools.link_auditor import audit

        result = audit(URL, "")
        assert result["score"] is not None
        assert isinstance(result["issues"], list)


class TestLinkContractCompliance:
    def test_contract_compliance_perfect(self, perfect_html):
        from tools.link_auditor import audit

        result = audit(URL, perfect_html)
        assert validate_result(result) is True

    def test_contract_compliance_sample(self, sample_html):
        from tools.link_auditor import audit

        result = audit(URL, sample_html)
        assert validate_result(result) is True

    def test_contract_compliance_empty(self):
        from tools.link_auditor import audit

        result = audit(URL, "")
        assert validate_result(result) is True


class TestLinkEdgeCases:
    def test_javascript_void_link(self):
        from tools.link_auditor import audit

        html = '<html><body><a href="javascript:void(0)">Bad Link</a></body></html>'
        result = audit(URL, html)
        types = [i["type"] for i in result["issues"]]
        assert "broken_link" in types

    def test_hash_only_link(self):
        from tools.link_auditor import audit

        html = '<html><body><a href="#">Top</a></body></html>'
        result = audit(URL, html)
        types = [i["type"] for i in result["issues"]]
        assert "broken_link" in types

    def test_nofollow_counted(self):
        from tools.link_auditor import audit

        html = '<html><body><a href="https://other.com" rel="nofollow">External</a></body></html>'
        result = audit(URL, html)
        assert result["data"]["nofollow_count"] == 1

    def test_external_link_counted(self):
        from tools.link_auditor import audit

        html = '<html><body><a href="https://other.com/page">Other Site</a></body></html>'
        result = audit(URL, html)
        assert result["data"]["external_link_count"] == 1

    def test_data_fields_present(self, perfect_html):
        from tools.link_auditor import audit

        result = audit(URL, perfect_html)
        data = result["data"]
        for key in ["internal_link_count", "external_link_count", "total_links",
                     "broken_links", "empty_anchors", "poor_anchors", "nofollow_count"]:
            assert key in data
