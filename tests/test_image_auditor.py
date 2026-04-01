from tools.base import validate_result


URL = "https://example.com/blog/seo-guide"


class TestImagePerfectPage:
    def test_perfect_page_high_score(self, perfect_html):
        from tools.image_auditor import audit

        result = audit(URL, perfect_html)
        assert result["score"] >= 90

    def test_perfect_page_no_critical_issues(self, perfect_html):
        from tools.image_auditor import audit

        result = audit(URL, perfect_html)
        critical = [i for i in result["issues"] if i["severity"] in ("critical", "high")]
        assert len(critical) == 0


class TestImageSamplePage:
    def test_detects_missing_alt(self, sample_html):
        from tools.image_auditor import audit

        result = audit(URL, sample_html)
        types = [i["type"] for i in result["issues"]]
        assert "missing_alt" in types

    def test_detects_non_modern_format(self, sample_html):
        from tools.image_auditor import audit

        result = audit(URL, sample_html)
        types = [i["type"] for i in result["issues"]]
        assert "non_modern_format" in types

    def test_sample_score_below_perfect(self, sample_html, perfect_html):
        from tools.image_auditor import audit

        sample = audit(URL, sample_html)
        perfect = audit(URL, perfect_html)
        assert sample["score"] < perfect["score"]


class TestImageMinimalPage:
    def test_no_images_score_100(self, minimal_html):
        from tools.image_auditor import audit

        result = audit(URL, minimal_html)
        assert result["score"] == 100

    def test_no_images_no_issues(self, minimal_html):
        from tools.image_auditor import audit

        result = audit(URL, minimal_html)
        assert len(result["issues"]) == 0
        assert result["data"]["total_images"] == 0


class TestImageEmptyHtml:
    def test_empty_html_does_not_crash(self):
        from tools.image_auditor import audit

        result = audit(URL, "")
        assert result["score"] is not None
        assert isinstance(result["issues"], list)


class TestImageContractCompliance:
    def test_contract_compliance_perfect(self, perfect_html):
        from tools.image_auditor import audit

        result = audit(URL, perfect_html)
        assert validate_result(result) is True

    def test_contract_compliance_sample(self, sample_html):
        from tools.image_auditor import audit

        result = audit(URL, sample_html)
        assert validate_result(result) is True

    def test_contract_compliance_empty(self):
        from tools.image_auditor import audit

        result = audit(URL, "")
        assert validate_result(result) is True


class TestImageEdgeCases:
    def test_filename_as_alt(self):
        from tools.image_auditor import audit

        html = '<html><body><img src="/img/photo.jpg" alt="IMG_1234.jpg" width="100" height="100"></body></html>'
        result = audit(URL, html)
        types = [i["type"] for i in result["issues"]]
        assert "filename_alt" in types

    def test_large_base64_image(self):
        from tools.image_auditor import audit

        data_uri = "data:image/png;base64," + "A" * 6000
        html = f'<html><body><img src="{data_uri}" alt="Inline image" width="100" height="100"></body></html>'
        result = audit(URL, html)
        types = [i["type"] for i in result["issues"]]
        assert "large_base64" in types

    def test_first_image_exempt_from_lazy(self):
        """First image should not be flagged for missing lazy loading."""
        from tools.image_auditor import audit

        html = '<html><body><img src="/hero.webp" alt="Hero" width="100" height="100"><img src="/second.webp" alt="Second" width="100" height="100"></body></html>'
        result = audit(URL, html)
        types = [i["type"] for i in result["issues"]]
        assert "missing_lazy_load" in types
        # Only second image should be flagged
        assert result["data"]["missing_lazy_count"] == 1

    def test_data_fields_present(self, perfect_html):
        from tools.image_auditor import audit

        result = audit(URL, perfect_html)
        data = result["data"]
        for key in ["total_images", "missing_alt_count", "missing_dimensions_count",
                     "non_modern_format_count", "missing_lazy_count", "images"]:
            assert key in data
