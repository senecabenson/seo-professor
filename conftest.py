import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "tests" / "fixtures"


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def sample_html(fixtures_dir):
    return (fixtures_dir / "sample_page.html").read_text()


@pytest.fixture
def perfect_html(fixtures_dir):
    return (fixtures_dir / "perfect_page.html").read_text()


@pytest.fixture
def minimal_html(fixtures_dir):
    return (fixtures_dir / "minimal_page.html").read_text()
