"""Tests for structured_data_auditor tool."""

from tools.base import validate_result

URL = "https://example.com/test"


class TestStructuredDataPerfectPage:
    def test_perfect_page_detects_article_schema(self, perfect_html):
        from tools.structured_data_auditor import audit

        result = audit(URL, perfect_html)
        assert result["data"]["json_ld_count"] >= 1
        assert "Article" in result["data"]["json_ld_types"]

    def test_perfect_page_high_score(self, perfect_html):
        from tools.structured_data_auditor import audit

        result = audit(URL, perfect_html)
        # No robots_txt provided, so -5 for no AI governance, but otherwise perfect
        assert result["score"] >= 90

    def test_perfect_page_article_has_required_props(self, perfect_html):
        from tools.structured_data_auditor import audit

        result = audit(URL, perfect_html)
        article_schemas = [s for s in result["data"]["schemas"] if s["type"] == "Article"]
        assert len(article_schemas) == 1
        assert article_schemas[0]["valid"] is True
        assert article_schemas[0]["missing_properties"] == []


class TestStructuredDataSchemaPage:
    def test_detects_product_schema(self, schema_html):
        from tools.structured_data_auditor import audit

        result = audit(URL, schema_html)
        assert "Product" in result["data"]["json_ld_types"]

    def test_detects_breadcrumb_schema(self, schema_html):
        from tools.structured_data_auditor import audit

        result = audit(URL, schema_html)
        assert "BreadcrumbList" in result["data"]["json_ld_types"]

    def test_detects_microdata(self, schema_html):
        from tools.structured_data_auditor import audit

        result = audit(URL, schema_html)
        assert result["data"]["has_microdata"] is True

    def test_json_ld_count(self, schema_html):
        from tools.structured_data_auditor import audit

        result = audit(URL, schema_html)
        assert result["data"]["json_ld_count"] == 2

    def test_high_score(self, schema_html):
        from tools.structured_data_auditor import audit

        result = audit(URL, schema_html)
        assert result["score"] >= 90


class TestStructuredDataSamplePage:
    def test_no_structured_data(self, sample_html):
        from tools.structured_data_auditor import audit

        result = audit(URL, sample_html)
        assert result["data"]["json_ld_count"] == 0
        assert result["data"]["json_ld_types"] == []

    def test_flags_missing_structured_data(self, sample_html):
        from tools.structured_data_auditor import audit

        result = audit(URL, sample_html)
        types = [i["type"] for i in result["issues"]]
        assert "no_structured_data" in types

    def test_lower_score(self, sample_html):
        from tools.structured_data_auditor import audit

        result = audit(URL, sample_html)
        assert result["score"] <= 75


class TestStructuredDataMinimalPage:
    def test_handles_minimal_html(self, minimal_html):
        from tools.structured_data_auditor import audit

        result = audit(URL, minimal_html)
        assert result["score"] is not None
        assert result["data"]["json_ld_count"] == 0


class TestStructuredDataEmptyHtml:
    def test_does_not_crash(self):
        from tools.structured_data_auditor import audit

        result = audit(URL, "")
        assert result["score"] is not None
        assert isinstance(result["issues"], list)

    def test_empty_html_string(self):
        from tools.structured_data_auditor import audit

        result = audit(URL, "<html></html>")
        assert result["score"] is not None


class TestStructuredDataContractCompliance:
    def test_validate_result(self, perfect_html):
        from tools.structured_data_auditor import audit

        result = audit(URL, perfect_html)
        assert validate_result(result) is True

    def test_validate_result_sample(self, sample_html):
        from tools.structured_data_auditor import audit

        result = audit(URL, sample_html)
        assert validate_result(result) is True

    def test_validate_result_empty(self):
        from tools.structured_data_auditor import audit

        result = audit(URL, "")
        assert validate_result(result) is True


class TestStructuredDataInvalidJson:
    def test_invalid_json_ld(self):
        from tools.structured_data_auditor import audit

        html = """
        <html><head>
        <script type="application/ld+json">
        { this is not valid json }
        </script>
        </head><body></body></html>
        """
        result = audit(URL, html)
        types = [i["type"] for i in result["issues"]]
        assert "invalid_json_ld" in types
        assert result["score"] <= 80

    def test_mixed_valid_invalid_json_ld(self):
        from tools.structured_data_auditor import audit

        html = """
        <html><head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Article", "headline": "Test", "author": "Me", "datePublished": "2025-01-01"}
        </script>
        <script type="application/ld+json">
        { broken json here }
        </script>
        </head><body></body></html>
        """
        result = audit(URL, html)
        assert result["data"]["json_ld_count"] == 2
        types = [i["type"] for i in result["issues"]]
        assert "invalid_json_ld" in types


class TestStructuredDataMissingProperties:
    def test_article_missing_author(self):
        from tools.structured_data_auditor import audit

        html = """
        <html><head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Article", "headline": "Test"}
        </script>
        </head><body></body></html>
        """
        result = audit(URL, html)
        article = [s for s in result["data"]["schemas"] if s["type"] == "Article"][0]
        assert "author" in article["missing_properties"]
        assert "datePublished" in article["missing_properties"]


class TestStructuredDataAiBotDirectives:
    def test_robots_txt_with_blocks(self):
        from tools.structured_data_auditor import audit

        robots_txt = """
User-agent: GPTBot
Disallow: /

User-agent: anthropic-ai
Disallow: /

User-agent: *
Allow: /
        """
        result = audit(URL, "<html><body></body></html>", config={"robots_txt": robots_txt})
        directives = result["data"]["ai_bot_directives"]
        assert directives["GPTBot"] == "blocked"
        assert directives["anthropic-ai"] == "blocked"

    def test_no_robots_txt(self):
        from tools.structured_data_auditor import audit

        result = audit(URL, "<html><body></body></html>")
        directives = result["data"]["ai_bot_directives"]
        # All should be not_specified
        for bot in directives:
            assert directives[bot] == "not_specified"

    def test_robots_txt_allows_some_bots(self):
        from tools.structured_data_auditor import audit

        robots_txt = """
User-agent: GPTBot
Allow: /

User-agent: CCBot
Disallow: /
        """
        result = audit(URL, "<html><body></body></html>", config={"robots_txt": robots_txt})
        directives = result["data"]["ai_bot_directives"]
        assert directives["GPTBot"] == "allowed"
        assert directives["CCBot"] == "blocked"

    def test_ai_governance_present_no_deduction(self, schema_html):
        from tools.structured_data_auditor import audit

        robots_txt = "User-agent: GPTBot\nDisallow: /\n"
        result = audit(URL, schema_html, config={"robots_txt": robots_txt})
        types = [i["type"] for i in result["issues"]]
        assert "no_ai_bot_governance" not in types
