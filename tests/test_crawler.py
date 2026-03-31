import pytest
import respx
import httpx
from tools.crawler import (
    parse_sitemap,
    parse_sitemap_index,
    extract_internal_links,
    is_same_domain,
    normalize_url,
    crawl,
)


# --- Unit tests (no network) ---


def test_parse_sitemap(fixtures_dir):
    """Parse fixture sitemap.xml, expect 5 URLs."""
    xml = (fixtures_dir / "sitemap.xml").read_text()
    urls = parse_sitemap(xml)
    assert len(urls) == 5
    assert "https://example.com/" in urls
    assert "https://example.com/about" in urls


def test_parse_sitemap_index(fixtures_dir):
    """Parse fixture sitemap_index.xml, expect 2 sitemap URLs."""
    xml = (fixtures_dir / "sitemap_index.xml").read_text()
    sitemap_urls = parse_sitemap_index(xml)
    assert len(sitemap_urls) == 2


def test_extract_internal_links():
    """Extract links from HTML, only internal ones."""
    html = """
    <html><body>
        <a href="/about">About</a>
        <a href="https://example.com/blog">Blog</a>
        <a href="https://external.com/page">External</a>
        <a href="mailto:test@example.com">Email</a>
        <a href="javascript:void(0)">JS</a>
        <a href="#section">Fragment</a>
        <a href="">Empty</a>
    </body></html>
    """
    links = extract_internal_links(html, "https://example.com")
    assert "https://example.com/about" in links
    assert "https://example.com/blog" in links
    assert "https://external.com/page" not in links
    assert len([l for l in links if "mailto" in l]) == 0
    assert len([l for l in links if "javascript" in l]) == 0


def test_normalize_url():
    """Normalize URLs: remove fragments, trailing slashes."""
    assert normalize_url("https://example.com/page#section") == "https://example.com/page"
    assert normalize_url("https://example.com/page/") == "https://example.com/page"
    assert normalize_url("https://Example.COM/Page") == "https://example.com/Page"


def test_is_same_domain():
    assert is_same_domain("https://example.com/page", "https://example.com") is True
    assert is_same_domain("https://sub.example.com/page", "https://example.com") is False
    assert is_same_domain("https://other.com/page", "https://example.com") is False


# --- Integration tests (mocked network) ---


@pytest.mark.asyncio
@respx.mock
async def test_crawl_with_sitemap():
    """Crawl discovers pages via sitemap."""
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )
    respx.get("https://example.com/sitemap.xml").mock(
        return_value=httpx.Response(
            200,
            text="""<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://example.com/</loc></url>
        <url><loc>https://example.com/about</loc></url>
    </urlset>""",
        )
    )
    respx.get("https://example.com/").mock(
        return_value=httpx.Response(200, text="<html><body>Home</body></html>")
    )
    respx.get("https://example.com/about").mock(
        return_value=httpx.Response(200, text="<html><body>About</body></html>")
    )

    results = await crawl("https://example.com", config={"delay_seconds": 0})
    assert len(results) == 2
    assert results[0]["url"] == "https://example.com/"
    assert results[0]["status_code"] == 200
    assert "Home" in results[0]["html"]


@pytest.mark.asyncio
@respx.mock
async def test_crawl_spider_fallback():
    """When no sitemap, spider discovers pages via links."""
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://example.com/sitemap.xml").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://example.com/").mock(
        return_value=httpx.Response(
            200,
            text='<html><body><a href="/about">About</a><a href="/blog">Blog</a></body></html>',
        )
    )
    respx.get("https://example.com/about").mock(
        return_value=httpx.Response(200, text="<html><body>About</body></html>")
    )
    respx.get("https://example.com/blog").mock(
        return_value=httpx.Response(200, text="<html><body>Blog</body></html>")
    )

    results = await crawl("https://example.com", config={"delay_seconds": 0})
    assert len(results) == 3
    urls = {r["url"] for r in results}
    assert "https://example.com/about" in urls


@pytest.mark.asyncio
@respx.mock
async def test_crawl_respects_max_pages():
    """Crawl stops after max_pages."""
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://example.com/sitemap.xml").mock(
        return_value=httpx.Response(
            200,
            text="""<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://example.com/1</loc></url>
        <url><loc>https://example.com/2</loc></url>
        <url><loc>https://example.com/3</loc></url>
        <url><loc>https://example.com/4</loc></url>
        <url><loc>https://example.com/5</loc></url>
    </urlset>""",
        )
    )
    for i in range(1, 6):
        respx.get(f"https://example.com/{i}").mock(
            return_value=httpx.Response(
                200, text=f"<html><body>Page {i}</body></html>"
            )
        )

    results = await crawl(
        "https://example.com", config={"max_pages": 3, "delay_seconds": 0}
    )
    assert len(results) == 3


@pytest.mark.asyncio
@respx.mock
async def test_crawl_handles_errors_gracefully():
    """Crawl skips pages that error, doesn't crash."""
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://example.com/sitemap.xml").mock(
        return_value=httpx.Response(
            200,
            text="""<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://example.com/good</loc></url>
        <url><loc>https://example.com/bad</loc></url>
    </urlset>""",
        )
    )
    respx.get("https://example.com/good").mock(
        return_value=httpx.Response(200, text="<html><body>Good</body></html>")
    )
    respx.get("https://example.com/bad").mock(
        side_effect=httpx.ConnectTimeout("timeout")
    )

    results = await crawl("https://example.com", config={"delay_seconds": 0})
    assert len(results) == 1
    assert results[0]["url"] == "https://example.com/good"


@pytest.mark.asyncio
@respx.mock
async def test_crawl_respects_robots_txt():
    """Crawl skips pages disallowed by robots.txt."""
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(
            200, text="User-agent: *\nDisallow: /private/"
        )
    )
    respx.get("https://example.com/sitemap.xml").mock(
        return_value=httpx.Response(
            200,
            text="""<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://example.com/public</loc></url>
        <url><loc>https://example.com/private/secret</loc></url>
    </urlset>""",
        )
    )
    respx.get("https://example.com/public").mock(
        return_value=httpx.Response(200, text="<html><body>Public</body></html>")
    )

    results = await crawl("https://example.com", config={"delay_seconds": 0})
    assert len(results) == 1
    assert results[0]["url"] == "https://example.com/public"


@pytest.mark.asyncio
@respx.mock
async def test_crawl_deduplicates_urls():
    """Same URL from sitemap and spider should be fetched only once."""
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://example.com/sitemap.xml").mock(
        return_value=httpx.Response(
            200,
            text="""<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://example.com/</loc></url>
        <url><loc>https://example.com/about</loc></url>
    </urlset>""",
        )
    )
    # Home page links to /about too (duplicate)
    respx.get("https://example.com/").mock(
        return_value=httpx.Response(
            200,
            text='<html><body><a href="/about">About</a></body></html>',
        )
    )
    respx.get("https://example.com/about").mock(
        return_value=httpx.Response(200, text="<html><body>About</body></html>")
    )

    results = await crawl("https://example.com", config={"delay_seconds": 0})
    urls = [r["url"] for r in results]
    assert urls.count("https://example.com/about") == 1
