from tools.base import validate_result


def test_valid_result_passes():
    result = {
        "tool": "test_tool",
        "url": "https://example.com",
        "score": 85,
        "issues": [
            {"severity": "high", "type": "test_issue", "detail": "A test issue"}
        ],
        "data": {"key": "value"},
    }
    assert validate_result(result) is True


def test_score_out_of_range_fails():
    result = {
        "tool": "test_tool",
        "url": "https://example.com",
        "score": 150,
        "issues": [],
        "data": {},
    }
    assert validate_result(result) is False


def test_invalid_severity_fails():
    result = {
        "tool": "test_tool",
        "url": "https://example.com",
        "score": 50,
        "issues": [
            {"severity": "urgent", "type": "test", "detail": "bad severity"}
        ],
        "data": {},
    }
    assert validate_result(result) is False


def test_missing_tool_name_fails():
    result = {
        "tool": "",
        "url": "https://example.com",
        "score": 50,
        "issues": [],
        "data": {},
    }
    assert validate_result(result) is False


def test_missing_issue_fields_fails():
    result = {
        "tool": "test_tool",
        "url": "https://example.com",
        "score": 50,
        "issues": [{"severity": "high"}],
        "data": {},
    }
    assert validate_result(result) is False


def test_none_score_allowed_for_skipped_tools():
    result = {
        "tool": "cwv_auditor",
        "url": "https://example.com",
        "score": None,
        "issues": [
            {"severity": "low", "type": "skipped", "detail": "No API key"}
        ],
        "data": {},
    }
    assert validate_result(result) is True
