from tools.base import validate_result


URL = "https://example.com/blog/seo-guide"


class TestIndexationPerfectPage:
    def test_perfect_page_high_score(self, perfect_html):
        from tools.indexation_auditor import audit

        result = audit(URL, perfect_html)
        assert result["score"] >= 95

    def test_perfect_page_no_critical_issues(self, perfect_html):
        from tools.indexation_auditor import audit

        result = audit(URL, perfect_html)
        critical = [i for i in result["issues"] if i["severity"] in ("critical", "high")]
        assert len(critical) == 0


class TestIndexationSamplePage:
    def test_detects_noindex(self, sample_html):
        from tools.indexation_auditor import audit

        result = audit(URL, sample_html)
        types = [i["type"] for i in result["issues"]]
        assert "noindex_meta" in types

    def test_noindex_is_critical(self, sample_html):
        from tools.indexation_auditor import audit

        result = audit(URL, sample_html)
        noindex_issues = [i for i in result["issues"] if i["type"] == "noindex_meta"]
        assert len(noindex_issues) > 0
        assert noindex_issues[0]["severity"] == "critical"

    def test_sample_score_penalized(self, sample_html):
        from tools.indexation_auditor import audit

        result = audit(URL, sample_html)
        assert result["score"] <= 70


class TestIndexationMinimalPage:
    def test_minimal_page_no_crash(self, minimal_html):
        from tools.indexation_auditor import audit

        result = audit(URL, minimal_html)
        assert isinstance(result["issues"], list)

    def test_minimal_reasonable_score(self, minimal_html):
        from tools.indexation_auditor import audit

        result = audit(URL, minimal_html)
        # Minimal page has no noindex, no canonical conflict, etc.
        # Should be fairly high since there's nothing wrong indexation-wise.
        assert result["score"] >= 80


class TestIndexationEmptyHtml:
    def test_empty_html_does_not_crash(self):
        from tools.indexation_auditor import audit

        result = audit(URL, "")
        assert result["score"] is not None
        assert isinstance(result["issues"], list)


class TestIndexationContractCompliance:
    def test_contract_compliance(self, perfect_html):
        from tools.indexation_auditor import audit

        result = audit(URL, perfect_html)
        assert validate_result(result) is True

    def test_contract_compliance_sample(self, sample_html):
        from tools.indexation_auditor import audit

        result = audit(URL, sample_html)
        assert validate_result(result) is True

    def test_contract_compliance_empty(self):
        from tools.indexation_auditor import audit

        result = audit(URL, "")
        assert validate_result(result) is True


class TestIndexationXRobotsTag:
    def test_x_robots_noindex_detected(self, perfect_html):
        from tools.indexation_auditor import audit

        config = {"headers": {"X-Robots-Tag": "noindex"}}
        result = audit(URL, perfect_html, config=config)
        types = [i["type"] for i in result["issues"]]
        assert "x_robots_noindex" in types

    def test_x_robots_noindex_is_critical(self, perfect_html):
        from tools.indexation_auditor import audit

        config = {"headers": {"X-Robots-Tag": "noindex"}}
        result = audit(URL, perfect_html, config=config)
        issue = [i for i in result["issues"] if i["type"] == "x_robots_noindex"][0]
        assert issue["severity"] == "critical"


class TestIndexationRedirects:
    def test_302_redirect_flagged(self, perfect_html):
        from tools.indexation_auditor import audit

        config = {"status_code": 302, "redirect_url": "https://example.com/new-page"}
        result = audit(URL, perfect_html, config=config)
        types = [i["type"] for i in result["issues"]]
        assert "redirect_302" in types

    def test_301_redirect_flagged(self, perfect_html):
        from tools.indexation_auditor import audit

        config = {"status_code": 301, "redirect_url": "https://example.com/new-page"}
        result = audit(URL, perfect_html, config=config)
        types = [i["type"] for i in result["issues"]]
        assert "redirect_301" in types


class TestIndexationCanonicalConflict:
    def test_canonical_pointing_elsewhere(self, perfect_html):
        from tools.indexation_auditor import audit

        # perfect_html canonical is https://example.com/blog/seo-guide
        # but we pass a different URL
        result = audit("https://example.com/different-page", perfect_html)
        types = [i["type"] for i in result["issues"]]
        assert "canonical_mismatch" in types

    def test_canonical_self_referencing_no_issue(self, perfect_html):
        from tools.indexation_auditor import audit

        result = audit("https://example.com/blog/seo-guide", perfect_html)
        types = [i["type"] for i in result["issues"]]
        assert "canonical_mismatch" not in types


class TestIndexationMetaRefresh:
    def test_meta_refresh_detected(self):
        from tools.indexation_auditor import audit

        html = '<html><head><meta http-equiv="refresh" content="5;url=https://example.com/other"></head><body></body></html>'
        result = audit(URL, html)
        types = [i["type"] for i in result["issues"]]
        assert "meta_refresh_redirect" in types


class TestIndexationHreflang:
    def test_missing_self_referencing_hreflang(self):
        from tools.indexation_auditor import audit

        html = '''<html><head>
        <link rel="alternate" hreflang="es" href="https://example.com/es/page">
        </head><body></body></html>'''
        result = audit(URL, html)
        types = [i["type"] for i in result["issues"]]
        assert "missing_self_hreflang" in types

    def test_perfect_page_hreflang_ok(self, perfect_html):
        from tools.indexation_auditor import audit

        result = audit(URL, perfect_html)
        types = [i["type"] for i in result["issues"]]
        assert "missing_self_hreflang" not in types
