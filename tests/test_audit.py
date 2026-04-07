"""Tests for src/audit.py"""

import json
import os
import pytest
from unittest.mock import MagicMock, patch


class TestLoadAnalysisIfReady:
    def test_returns_file_contents_when_file_exists(self, tmp_path, monkeypatch):
        """Returns the JSON from .tmp/ai_analysis.json if the file exists."""
        analysis = {
            "executive_summary": "Site looks good.",
            "priority_fixes": [],
            "category_analysis": {},
            "recommendations": [],
        }
        analysis_path = tmp_path / "ai_analysis.json"
        analysis_path.write_text(json.dumps(analysis))
        monkeypatch.setattr("src.audit.AI_ANALYSIS_PATH", str(analysis_path))

        from src.audit import load_analysis_if_ready
        result = load_analysis_if_ready()
        assert result["executive_summary"] == "Site looks good."

    def test_returns_default_when_file_missing(self, tmp_path, monkeypatch):
        """Returns default analysis dict when no ai_analysis.json exists."""
        monkeypatch.setattr("src.audit.AI_ANALYSIS_PATH", str(tmp_path / "nonexistent.json"))

        from src.audit import load_analysis_if_ready
        result = load_analysis_if_ready()
        assert "executive_summary" in result
        assert isinstance(result["priority_fixes"], list)
        assert isinstance(result["recommendations"], list)

    def test_calls_claude_api_when_key_is_set(self, tmp_path, monkeypatch):
        """Calls analyze_with_claude() when ANTHROPIC_API_KEY is set."""
        # Write audit data with a prompt
        audit_data = {"analysis": {"prompt": "test prompt"}}
        audit_path = tmp_path / "audit_data.json"
        audit_path.write_text(json.dumps(audit_data))
        monkeypatch.setattr("src.audit.AUDIT_DATA_PATH", str(audit_path))
        monkeypatch.setattr("src.audit.AI_ANALYSIS_PATH", str(tmp_path / "nonexistent.json"))
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")

        fake_analysis = {
            "executive_summary": "API analysis",
            "priority_fixes": [],
            "category_analysis": {},
            "recommendations": [],
        }

        with patch("src.audit.analyze_with_claude", return_value=fake_analysis) as mock_api:
            from src.audit import load_analysis_if_ready
            result = load_analysis_if_ready()

        mock_api.assert_called_once_with("test prompt", "sk-ant-fake")
        assert result["executive_summary"] == "API analysis"
