from tools.base import validate_result


URL = "https://example.com/blog/seo-guide"
HTTP_URL = "http://example.com/blog/seo-guide"

ALL_HEADERS = {
    "Content-Security-Policy": "default-src 'self'",
    "X-Frame-Options": "DENY",
    "Strict-Transport-Security": "max-age=31536000",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


class TestSecurityPerfectPage:
    def test_perfect_page_high_score(self, perfect_html):
        from tools.security_auditor import audit

        result = audit(URL, perfect_html, config={"headers": ALL_HEADERS})
        assert result["score"] >= 95

    def test_perfect_page_no_critical_issues(self, perfect_html):
        from tools.security_auditor import audit

        result = audit(URL, perfect_html, config={"headers": ALL_HEADERS})
        critical = [i for i in result["issues"] if i["severity"] in ("critical", "high")]
        assert len(critical) == 0


class TestSecuritySamplePage:
    def test_detects_mixed_content(self, sample_html):
        from tools.security_auditor import audit

        result = audit(URL, sample_html)
        types = [i["type"] for i in result["issues"]]
        assert "mixed_content" in types

    def test_detects_missing_headers(self, sample_html):
        from tools.security_auditor import audit

        result = audit(URL, sample_html)
        types = [i["type"] for i in result["issues"]]
        assert "missing_security_header" in types

    def test_sample_score_below_perfect(self, sample_html, perfect_html):
        from tools.security_auditor import audit

        sample = audit(URL, sample_html)
        perfect = audit(URL, perfect_html, config={"headers": ALL_HEADERS})
        assert sample["score"] < perfect["score"]


class TestSecurityMinimalPage:
    def test_minimal_page_no_mixed_content(self, minimal_html):
        from tools.security_auditor import audit

        result = audit(URL, minimal_html)
        assert len(result["data"]["mixed_content_urls"]) == 0

    def test_minimal_page_is_https(self, minimal_html):
        from tools.security_auditor import audit

        result = audit(URL, minimal_html)
        assert result["data"]["is_https"] is True


class TestSecurityEmptyHtml:
    def test_empty_html_does_not_crash(self):
        from tools.security_auditor import audit

        result = audit(URL, "")
        assert result["score"] is not None
        assert isinstance(result["issues"], list)


class TestSecurityContractCompliance:
    def test_contract_compliance_perfect(self, perfect_html):
        from tools.security_auditor import audit

        result = audit(URL, perfect_html, config={"headers": ALL_HEADERS})
        assert validate_result(result) is True

    def test_contract_compliance_sample(self, sample_html):
        from tools.security_auditor import audit

        result = audit(URL, sample_html)
        assert validate_result(result) is True

    def test_contract_compliance_empty(self):
        from tools.security_auditor import audit

        result = audit(URL, "")
        assert validate_result(result) is True


class TestSecurityEdgeCases:
    def test_http_url_critical(self):
        from tools.security_auditor import audit

        html = "<html><body><p>Hello</p></body></html>"
        result = audit(HTTP_URL, html)
        types = [i["type"] for i in result["issues"]]
        severities = {i["type"]: i["severity"] for i in result["issues"]}
        assert "http_url" in types
        assert severities["http_url"] == "critical"
        assert result["data"]["is_https"] is False

    def test_no_mixed_content_on_http_page(self):
        """http:// refs on an http:// page are NOT mixed content."""
        from tools.security_auditor import audit

        html = '<html><body><img src="http://example.com/img.jpg"></body></html>'
        result = audit(HTTP_URL, html)
        assert len(result["data"]["mixed_content_urls"]) == 0

    def test_partial_headers(self):
        from tools.security_auditor import audit

        html = "<html><body><p>Test</p></body></html>"
        partial = {"Content-Security-Policy": "default-src 'self'"}
        result = audit(URL, html, config={"headers": partial})
        # Should still flag the missing ones
        missing_types = [i["type"] for i in result["issues"] if i["type"] == "missing_security_header"]
        assert len(missing_types) == 4  # 4 missing out of 5

    def test_data_fields_present(self, perfect_html):
        from tools.security_auditor import audit

        result = audit(URL, perfect_html, config={"headers": ALL_HEADERS})
        data = result["data"]
        for key in ["is_https", "mixed_content_urls", "security_headers"]:
            assert key in data
        # security_headers should have all 5 headers
        assert len(data["security_headers"]) == 5
