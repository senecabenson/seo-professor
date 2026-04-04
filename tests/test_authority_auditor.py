"""Tests for authority_auditor tool."""

from tools.base import validate_result

URL = "https://example.com/test"


class TestAuthorityPerfectPage:
    def test_detects_author(self, perfect_html):
        from tools.authority_auditor import audit

        result = audit(URL, perfect_html)
        assert result["data"]["has_author"] is True

    def test_detects_about_link(self, perfect_html):
        from tools.authority_auditor import audit

        result = audit(URL, perfect_html)
        assert result["data"]["has_about_link"] is True

    def test_detects_contact_link(self, perfect_html):
        from tools.authority_auditor import audit

        result = audit(URL, perfect_html)
        assert result["data"]["has_contact_link"] is True

    def test_detects_privacy_link(self, perfect_html):
        from tools.authority_auditor import audit

        result = audit(URL, perfect_html)
        assert result["data"]["has_privacy_link"] is True

    def test_high_score(self, perfect_html):
        from tools.authority_auditor import audit

        result = audit(URL, perfect_html)
        assert result["score"] >= 80


class TestAuthorityEeatPage:
    def test_detects_author(self, eeat_html):
        from tools.authority_auditor import audit

        result = audit(URL, eeat_html)
        assert result["data"]["has_author"] is True
        assert result["data"]["author_name"] == "John Doe"

    def test_detects_about_link(self, eeat_html):
        from tools.authority_auditor import audit

        result = audit(URL, eeat_html)
        assert result["data"]["has_about_link"] is True

    def test_detects_contact_link(self, eeat_html):
        from tools.authority_auditor import audit

        result = audit(URL, eeat_html)
        assert result["data"]["has_contact_link"] is True

    def test_detects_privacy_and_terms(self, eeat_html):
        from tools.authority_auditor import audit

        result = audit(URL, eeat_html)
        assert result["data"]["has_privacy_link"] is True

    def test_detects_social_links(self, eeat_html):
        from tools.authority_auditor import audit

        result = audit(URL, eeat_html)
        assert len(result["data"]["social_links"]) >= 2

    def test_detects_testimonials(self, eeat_html):
        from tools.authority_auditor import audit

        result = audit(URL, eeat_html)
        assert result["data"]["has_reviews"] is True

    def test_detects_credentials(self, eeat_html):
        from tools.authority_auditor import audit

        result = audit(URL, eeat_html)
        creds = result["data"]["credentials_found"]
        assert any("certified" in c.lower() for c in creds)
        assert any("years of experience" in c.lower() for c in creds)

    def test_high_score(self, eeat_html):
        from tools.authority_auditor import audit

        result = audit(URL, eeat_html)
        assert result["score"] >= 95

    def test_eeat_score_breakdown(self, eeat_html):
        from tools.authority_auditor import audit

        result = audit(URL, eeat_html)
        breakdown = result["data"]["eeat_score_breakdown"]
        assert breakdown["author"] is True
        assert breakdown["about_link"] is True
        assert breakdown["contact_link"] is True
        assert breakdown["privacy_link"] is True
        assert breakdown["social_links"] is True


class TestAuthoritySamplePage:
    def test_no_author(self, sample_html):
        from tools.authority_auditor import audit

        result = audit(URL, sample_html)
        assert result["data"]["has_author"] is False

    def test_no_about_link(self, sample_html):
        from tools.authority_auditor import audit

        result = audit(URL, sample_html)
        assert result["data"]["has_about_link"] is False

    def test_no_contact_link(self, sample_html):
        from tools.authority_auditor import audit

        result = audit(URL, sample_html)
        assert result["data"]["has_contact_link"] is False

    def test_flags_missing_signals(self, sample_html):
        from tools.authority_auditor import audit

        result = audit(URL, sample_html)
        types = [i["type"] for i in result["issues"]]
        assert "no_author_attribution" in types
        assert "no_about_link" in types
        assert "no_contact_link" in types

    def test_lower_score(self, sample_html):
        from tools.authority_auditor import audit

        result = audit(URL, sample_html)
        assert result["score"] <= 50


class TestAuthorityMinimalPage:
    def test_handles_minimal_html(self, minimal_html):
        from tools.authority_auditor import audit

        result = audit(URL, minimal_html)
        assert result["score"] is not None
        assert result["data"]["has_author"] is False


class TestAuthorityEmptyHtml:
    def test_does_not_crash(self):
        from tools.authority_auditor import audit

        result = audit(URL, "")
        assert result["score"] is not None
        assert isinstance(result["issues"], list)

    def test_empty_html_tag(self):
        from tools.authority_auditor import audit

        result = audit(URL, "<html></html>")
        assert result["score"] is not None


class TestAuthorityContractCompliance:
    def test_validate_result_perfect(self, perfect_html):
        from tools.authority_auditor import audit

        result = audit(URL, perfect_html)
        assert validate_result(result) is True

    def test_validate_result_sample(self, sample_html):
        from tools.authority_auditor import audit

        result = audit(URL, sample_html)
        assert validate_result(result) is True

    def test_validate_result_empty(self):
        from tools.authority_auditor import audit

        result = audit(URL, "")
        assert validate_result(result) is True


class TestAuthorityMetaAuthor:
    def test_meta_author_detection(self):
        from tools.authority_auditor import audit

        html = '<html><head><meta name="author" content="Jane Smith"></head><body></body></html>'
        result = audit(URL, html)
        assert result["data"]["has_author"] is True
        assert result["data"]["author_name"] == "Jane Smith"


class TestAuthoritySocialLinks:
    def test_detects_various_social_platforms(self):
        from tools.authority_auditor import audit

        html = """
        <html><body>
        <a href="https://twitter.com/test">Twitter</a>
        <a href="https://linkedin.com/in/test">LinkedIn</a>
        <a href="https://facebook.com/test">Facebook</a>
        <a href="https://instagram.com/test">Instagram</a>
        <a href="https://youtube.com/test">YouTube</a>
        </body></html>
        """
        result = audit(URL, html)
        assert len(result["data"]["social_links"]) == 5

    def test_no_social_deduction(self):
        from tools.authority_auditor import audit

        html = "<html><body><p>No social links here</p></body></html>"
        result = audit(URL, html)
        types = [i["type"] for i in result["issues"]]
        assert "no_social_links" in types
