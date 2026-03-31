from typing import TypedDict, Literal


VALID_SEVERITIES = {"critical", "high", "medium", "low"}


class AuditIssue(TypedDict):
    severity: Literal["critical", "high", "medium", "low"]
    type: str
    detail: str


class AuditResult(TypedDict):
    tool: str
    url: str
    score: int | None
    issues: list[AuditIssue]
    data: dict


def validate_result(result: dict) -> bool:
    if not isinstance(result, dict):
        return False
    required_keys = {"tool", "url", "score", "issues", "data"}
    if not required_keys.issubset(result.keys()):
        return False
    if not result["tool"] or not result["url"]:
        return False
    if result["score"] is not None:
        if not isinstance(result["score"], int) or not (0 <= result["score"] <= 100):
            return False
    if not isinstance(result["issues"], list):
        return False
    for issue in result["issues"]:
        if not isinstance(issue, dict):
            return False
        if not {"severity", "type", "detail"}.issubset(issue.keys()):
            return False
        if issue["severity"] not in VALID_SEVERITIES:
            return False
    return True


def make_result(
    tool: str,
    url: str,
    score: int | None,
    issues: list[dict],
    data: dict | None = None,
) -> AuditResult:
    return {
        "tool": tool,
        "url": url,
        "score": score,
        "issues": issues,
        "data": data or {},
    }
