import pathlib
import pytest

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_html():
    return (FIXTURES_DIR / "sample_page.html").read_text()


@pytest.fixture
def perfect_html():
    return (FIXTURES_DIR / "perfect_page.html").read_text()


@pytest.fixture
def minimal_html():
    return (FIXTURES_DIR / "minimal_page.html").read_text()
