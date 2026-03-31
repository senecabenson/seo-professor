from tools.base import make_result


def make_onpage_result(url="https://example.com", score=75, issues=None):
    return make_result(
        tool="onpage_auditor",
        url=url,
        score=score,
        issues=issues or [
            {"severity": "high", "type": "missing_meta_description",
             "detail": "No meta description found"},
        ],
        data={"title_length": 45, "word_count": 350},
    )


def make_perfect_result(tool="onpage_auditor", url="https://example.com"):
    return make_result(tool=tool, url=url, score=100, issues=[], data={})


def make_skipped_result(tool="cwv_auditor", url="https://example.com"):
    return make_result(
        tool=tool,
        url=url,
        score=None,
        issues=[{"severity": "low", "type": "skipped",
                 "detail": "Tool skipped — missing API key"}],
    )
