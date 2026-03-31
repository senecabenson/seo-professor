"""Site crawler with sitemap discovery and spider fallback."""

import asyncio
from collections import deque
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

DEFAULT_CONFIG = {
    "max_pages": 50,
    "delay_seconds": 1.0,
    "user_agent": "SEOProfessor/1.0",
    "follow_external": False,
}

SKIP_SCHEMES = {"mailto", "tel", "javascript", "data"}


def normalize_url(url: str) -> str:
    """Remove fragments, trailing slashes, normalize to lowercase domain."""
    parsed = urlparse(url)
    # Lowercase the scheme and netloc only, preserve path case
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        fragment="",
    )
    path = normalized.path.rstrip("/") if normalized.path != "/" else "/"
    normalized = normalized._replace(path=path)
    return urlunparse(normalized)


def is_same_domain(url: str, base_url: str) -> bool:
    """Check if url belongs to same domain as base_url."""
    url_host = urlparse(url).netloc.lower()
    base_host = urlparse(base_url).netloc.lower()
    return url_host == base_host


def parse_sitemap(xml_content: str) -> list[str]:
    """Parse sitemap XML, return list of URLs from <loc> tags."""
    soup = BeautifulSoup(xml_content, "lxml-xml")
    urls = []
    for loc in soup.find_all("loc"):
        text = loc.get_text(strip=True)
        if text:
            urls.append(text)
    return urls


def parse_sitemap_index(xml_content: str) -> list[str]:
    """Parse sitemap index XML, return list of sitemap URLs."""
    soup = BeautifulSoup(xml_content, "lxml-xml")
    sitemap_urls = []
    for sitemap in soup.find_all("sitemap"):
        loc = sitemap.find("loc")
        if loc:
            text = loc.get_text(strip=True)
            if text:
                sitemap_urls.append(text)
    return sitemap_urls


def extract_internal_links(html: str, base_url: str) -> set[str]:
    """Extract internal links from HTML. Normalize URLs. Skip fragments, mailto, tel, javascript."""
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href:
            continue
        # Skip non-http schemes
        parsed = urlparse(href)
        if parsed.scheme and parsed.scheme.lower() in SKIP_SCHEMES:
            continue
        # Skip fragment-only links
        if href.startswith("#"):
            continue
        # Resolve relative URLs
        full_url = urljoin(base_url + "/", href)
        normalized = normalize_url(full_url)
        # Only keep internal links
        if is_same_domain(normalized, base_url):
            links.add(normalized)
    return links


def _build_robot_parser(robots_txt: str, base_url: str) -> RobotFileParser:
    """Build a RobotFileParser from robots.txt content."""
    rp = RobotFileParser()
    rp.parse(robots_txt.splitlines())
    return rp


async def crawl(start_url: str, config: dict | None = None) -> list[dict]:
    """
    Crawl a site starting from start_url.

    Config options:
        max_pages: int (default 50)
        delay_seconds: float (default 1.0)
        user_agent: str (default "SEOProfessor/1.0")
        follow_external: bool (default False)

    Returns list of:
        {"url": str, "status_code": int, "html": str, "headers": dict}
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    max_pages = cfg["max_pages"]
    delay = cfg["delay_seconds"]
    user_agent = cfg["user_agent"]

    # Normalize the start URL
    parsed_start = urlparse(start_url)
    base_url = f"{parsed_start.scheme}://{parsed_start.netloc}"

    headers = {"User-Agent": user_agent}
    results: list[dict] = []
    visited: set[str] = set()

    async with httpx.AsyncClient(
        headers=headers, follow_redirects=True, timeout=30.0
    ) as client:
        # Step 1: Fetch and parse robots.txt
        robot_parser = RobotFileParser()
        try:
            resp = await client.get(f"{base_url}/robots.txt")
            if resp.status_code == 200:
                robot_parser = _build_robot_parser(resp.text, base_url)
            else:
                # No robots.txt means everything is allowed
                robot_parser.parse([])
        except httpx.HTTPError:
            # Can't fetch robots.txt — assume everything is allowed
            robot_parser.parse([])

        # Step 2: Try sitemap discovery
        discovered_urls: list[str] = []
        try:
            resp = await client.get(f"{base_url}/sitemap.xml")
            if resp.status_code == 200:
                # Check if it's a sitemap index
                index_urls = parse_sitemap_index(resp.text)
                if index_urls:
                    # Fetch each sub-sitemap
                    for sitemap_url in index_urls:
                        try:
                            sub_resp = await client.get(sitemap_url)
                            if sub_resp.status_code == 200:
                                discovered_urls.extend(
                                    parse_sitemap(sub_resp.text)
                                )
                        except httpx.HTTPError:
                            continue
                else:
                    discovered_urls = parse_sitemap(resp.text)
        except httpx.HTTPError:
            pass

        # Step 3: If no sitemap URLs found, start with the start_url for spidering
        use_spider = len(discovered_urls) == 0
        if use_spider:
            # Normalize start_url: ensure it ends properly
            norm_start = normalize_url(start_url)
            # If start_url has no path, add /
            parsed_norm = urlparse(norm_start)
            if not parsed_norm.path or parsed_norm.path == "":
                norm_start = norm_start + "/"
            discovered_urls = [norm_start]

        # BFS queue for spidering (used when no sitemap, or to find additional links)
        queue: deque[str] = deque()
        for url in discovered_urls:
            norm = normalize_url(url)
            if norm not in visited:
                queue.append(norm)
                visited.add(norm)

        # Step 4: Fetch pages
        while queue and len(results) < max_pages:
            url = queue.popleft()

            # Check robots.txt
            if not robot_parser.can_fetch(user_agent, url):
                continue

            try:
                if delay > 0 and len(results) > 0:
                    await asyncio.sleep(delay)

                resp = await client.get(url)
                results.append(
                    {
                        "url": url,
                        "status_code": resp.status_code,
                        "html": resp.text,
                        "headers": dict(resp.headers),
                    }
                )

                # Spider: extract internal links from fetched pages
                if use_spider and resp.status_code == 200:
                    new_links = extract_internal_links(resp.text, base_url)
                    for link in new_links:
                        norm_link = normalize_url(link)
                        if norm_link not in visited:
                            visited.add(norm_link)
                            queue.append(norm_link)

            except (httpx.HTTPError, httpx.StreamError):
                # Skip failed pages, don't crash
                continue

    return results
