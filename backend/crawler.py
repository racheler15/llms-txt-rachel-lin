import hashlib
import time
from collections import deque
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, urlencode
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel

from constants import COMMON_DOC_PATHS


class Page(BaseModel):
    url: str
    title: str
    description: str
    h1: str
    og_type: str
    depth: int
    content_hash: str


MAX_DEPTH = 3
MAX_PAGES = 50
REQUEST_DELAY = 0.1
TIMEOUT = 5


def normalize_url(url: str) -> str:
    """Lowercase host, strip trailing slash, sort and filter query params."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    params = parse_qs(parsed.query)
    filtered_params = {k: v for k, v in params.items() if not k.startswith("utm_")}
    query = urlencode(sorted(filtered_params.items()), doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def url_hash(url: str) -> str:
    """Hash a URL string for dedup."""
    return hashlib.md5(url.encode()).hexdigest()


def content_hash(text: str) -> str:
    """Hash page body text for content dedup."""
    return hashlib.md5(text.strip().encode()).hexdigest()


def _fetch_sitemap(sitemap_url: str) -> list[str]:
    """Fetch a single sitemap file and return its <loc> URLs."""
    try:
        response = requests.get(sitemap_url, timeout=TIMEOUT)
        if not response.ok:
            return []
        soup = BeautifulSoup(response.text, "lxml-xml")
        return [loc.text.strip() for loc in soup.find_all("loc")]
    except Exception:
        return []


def get_sitemap_urls(base_url: str) -> list[str]:
    """Fetch sitemap.xml and extract page URLs. Handles sitemap index files."""
    sitemap_url = urljoin(base_url, "/sitemap.xml")
    try:
        response = requests.get(sitemap_url, timeout=TIMEOUT)
        if not response.ok:
            return []
        soup = BeautifulSoup(response.text, "lxml-xml")

        # Sitemap index — each <loc> points to another sitemap file
        if soup.find("sitemapindex"):
            urls = []
            for loc in soup.find_all("loc"):
                urls.extend(_fetch_sitemap(loc.text.strip()))
            return urls

        # Regular sitemap — direct <loc> URLs
        return [loc.text.strip() for loc in soup.find_all("loc")]
    except Exception:
        return []


def extract_page_data(html: str, page_url: str, base_domain: str) -> dict:
    """Extract title, description, h1, internal links from HTML."""
    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    meta_desc = soup.find("meta", attrs={"name": "description"})
    description = meta_desc.get("content", "").strip() if meta_desc else ""

    robots_tag = soup.find("meta", attrs={"name": "robots"})
    robots = robots_tag.get("content", "").lower() if robots_tag else ""
    noindex = "noindex" in robots

    canonical_tag = soup.find("link", attrs={"rel": "canonical"})
    canonical = canonical_tag.get("href", "").strip() if canonical_tag else ""

    og_type_tag = soup.find("meta", attrs={"property": "og:type"})
    og_type = og_type_tag.get("content", "").strip().lower() if og_type_tag else ""

    h1_tag = soup.find("h1")
    h1 = h1_tag.get_text(strip=True) if h1_tag else ""

    body = soup.find("body")
    body_text = body.get_text(separator=" ", strip=True) if body else ""

    internal_links = []
    for link in soup.find_all("a", href=True):
        href = link.get("href")
        new_url = urljoin(page_url, href)
        parsed = urlparse(new_url)
        if parsed.hostname == base_domain and parsed.scheme in ("http", "https"):
            internal_links.append(new_url)

    return {
        "title": title,
        "description": description,
        "h1": h1,
        "og_type": og_type,
        "noindex": noindex,
        "canonical": canonical,
        "content_hash": content_hash(body_text),
        "internal_links": internal_links,
    }


def _load_robots(base_url: str) -> RobotFileParser:
    """Fetch and parse robots.txt, returning a permissive parser on failure."""
    rp = RobotFileParser()
    rp.set_url(f"{base_url}/robots.txt")
    try:
        rp.read()
    except Exception:
        rp.allow_all = True # No restrictions
    return rp


def crawl_site(start_url: str) -> list[Page]:
    """
    Crawl a site given a start_url to generate an llms.txt that reflects the entire website's structure.

    Returns list of Page objects.
    """
    # Construct a valid base URL
    parsed_start = urlparse(start_url)
    base_domain = parsed_start.hostname
    base_url = f"{parsed_start.scheme}://{base_domain}"

    # Adhere to robots.txt
    robots = _load_robots(base_url)
    crawl_delay = robots.crawl_delay("*")
    delay = crawl_delay if crawl_delay else REQUEST_DELAY

    # Check if sitemap exists
    sitemap_urls = get_sitemap_urls(base_url)

    # Build the initial queue: (url, depth)
    queue = deque([(base_url, 0)])

    if sitemap_urls:
        for url in sitemap_urls[:MAX_PAGES]:
            queue.append((url, 0))

    # Seed common doc paths so developer content isn't missed
    # even if the homepage doesn't link to it directly
    for path in COMMON_DOC_PATHS:
        queue.append((f"{base_url}{path}", 1))

    visited = set()
    results = []

    while queue and len(results) < MAX_PAGES:
        url, depth = queue.popleft()

        if depth > MAX_DEPTH:
            continue

        normalized = normalize_url(url)
        url_id = url_hash(normalized)

        if url_id in visited:
            continue
        visited.add(url_id)

        if not robots.can_fetch("*", normalized):
            continue

        try:
            response = requests.get(normalized, timeout=TIMEOUT)
            if not response.ok:
                continue
        except Exception:
            continue

        # Extract data
        page_data = extract_page_data(response.text, normalized, base_domain)

        # Skip noindex pages 
        if page_data["noindex"]:
            continue

        page_url = page_data["canonical"] or normalized

        results.append(Page(
            url=page_url,
            title=page_data["title"],
            description=page_data["description"],
            h1=page_data["h1"],
            og_type=page_data["og_type"],
            depth=depth,
            content_hash=page_data["content_hash"],
        ))

        # Add internal links to queue (only if we haven't hit max depth)
        if depth < MAX_DEPTH:
            for link in page_data["internal_links"]:
                if url_hash(normalize_url(link)) not in visited:
                    queue.append((link, depth + 1))

        # Be polite
        time.sleep(delay)

    return results
