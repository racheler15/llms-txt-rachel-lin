import asyncio
import logging
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, urlencode
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from constants import (
    COMMON_DOC_PATHS,
    COMMON_OPTIONAL_PATHS,
    DOC_PATH_BOOST,
    HOMEPAGE_BOOST,
    MAX_DEPTH,
    MAX_NESTED_SITEMAPS,
    MAX_SITEMAP_DEPTH,
    MAX_SITEMAP_URLS,
    SITEMAP_BULK_MARKERS,
    SITEMAP_PRIORITY_MARKERS,
    DOC_PATH_GUESS_THRESHOLD,
    SITEMAP_SEED_LIMIT,
    OPTIONAL_CRAWL_RESERVE,
)
from models import Page
from progress import (
    STAGE_CHECKING_ACCESS,
    STAGE_CRAWLING,
    STAGE_DISCOVERING_PAGES,
    ProgressCallback,
    emit_progress,
    emit_stage,
)
from scoring import (
    precrawl_url_score,
    top_optional_sitemap_urls,
    prioritize_sitemap_urls,
    should_exclude_crawl_candidate,
    should_exclude_sitemap_entry,
)
from url_utils import (
    content_hash,
    is_internal_link,
    normalize_url,
    page_quality,
    registrable_domain,
    should_skip_url,
    url_hash,
)

logger = logging.getLogger(__name__)


@dataclass
class HomepageSignals:
    has_json_ld: bool
    has_og_title: bool
    has_og_description: bool


@dataclass
class CrawlFetchStats:
    http_errors: int = 0


@dataclass
class CrawlResult:
    pages: list[Page]
    base_url: str
    sitemap_exists: bool
    robots_text: str | None
    robots_status: int | None
    homepage_signals: HomepageSignals | None
    llms_txt_exists: bool
    http_errors: int = 0
    robots_blocked: bool = False
    homepage_timed_out: bool = False


MAX_PAGES = 200
MAIN_CRAWL_BUDGET = MAX_PAGES - OPTIONAL_CRAWL_RESERVE
MAX_CONCURRENCY = 20
TIMEOUT = 5.0
MAX_FETCH_RETRIES = 2
DESCRIPTION_MAX_LENGTH = 320

_TIMEOUT_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
)


async def _fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    timeout: float = TIMEOUT,
    follow_redirects: bool = True,
    max_retries: int = MAX_FETCH_RETRIES,
) -> httpx.Response | None:
    for attempt in range(max_retries + 1):
        try:
            response = await client.get(
                url, timeout=timeout, follow_redirects=follow_redirects
            )
            if response.status_code == 429:
                if attempt < max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
                return response
            return response
        except _TIMEOUT_EXCEPTIONS:
            if attempt < max_retries:
                await asyncio.sleep(1)
                continue
            return None
        except Exception:
            return None
    return None


def _is_html_response(response: httpx.Response) -> bool:
    content_type = response.headers.get("content-type", "").lower()
    return "text/html" in content_type or "application/xhtml+xml" in content_type


def _meta_content(
    soup: BeautifulSoup,
    *,
    name: str | None = None,
    og_property: str | None = None,
) -> str:
    attrs: dict[str, str] = {}
    if name:
        attrs["name"] = name
    if og_property:
        attrs["property"] = og_property
    # find first matching meta tag with the given attribute
    tag = soup.find("meta", attrs=attrs)
    return tag.get("content", "").strip() if tag else ""


def _truncate_at_boundary(text: str, max_len: int = DESCRIPTION_MAX_LENGTH) -> str:
    """Truncate long text at a sentence or word boundary, adding ellipsis when clipped."""
    text = text.strip()
    if len(text) <= max_len:
        return text

    window = text[:max_len]
    min_break = max_len // 2

    for sep in (". ", "! ", "? "):
        idx = window.rfind(sep)
        if idx >= min_break:
            return text[: idx + 1].strip()

    last_space = window.rfind(" ")
    if last_space > 0:
        return text[:last_space].rstrip() + "..."

    return window.rstrip() + "..."


def _first_meaningful_paragraph(soup: BeautifulSoup) -> str:
    for paragraph in soup.find_all("p"):
        text = paragraph.get_text(separator=" ", strip=True)
        if len(text) >= 40:
            return _truncate_at_boundary(text)
    return ""


def _build_title(soup: BeautifulSoup) -> str:
    title_tag = soup.find("title")
    raw_title = title_tag.get_text(separator=" ", strip=True) if title_tag else ""
    og_title = _meta_content(soup, og_property="og:title")
    h1_tag = soup.find("h1")
    h1 = h1_tag.get_text(separator=" ", strip=True) if h1_tag else ""

    # Many sites reuse one global <title>; og:title is usually page-specific.
    if og_title and og_title != raw_title:
        return og_title
    if raw_title:
        return raw_title
    if og_title:
        return og_title
    return h1


def _build_description(soup: BeautifulSoup, h1: str) -> str:
    description = _meta_content(soup, name="description")
    if description:
        return _truncate_at_boundary(description)
    og_description = _meta_content(soup, og_property="og:description")
    if og_description:
        return _truncate_at_boundary(og_description)
    paragraph = _first_meaningful_paragraph(soup)
    if paragraph:
        return paragraph
    if h1:
        return h1
    headings = soup.find_all(["h2", "h3"])
    for heading in headings:
        text = heading.get_text(separator=" ", strip=True)
        if text:
            return text
    return ""


def _extract_homepage_signals(soup: BeautifulSoup) -> HomepageSignals:
    return HomepageSignals(
        has_json_ld=soup.find("script", attrs={"type": "application/ld+json"}) is not None,
        has_og_title=bool(_meta_content(soup, og_property="og:title")),
        has_og_description=bool(_meta_content(soup, og_property="og:description")),
    )


def _extract_page_data(html: str, page_url: str, base_domain: str) -> dict:
    """Extract title, description, headings, and internal links from HTML."""
    soup = BeautifulSoup(html, "lxml")

    robots = _meta_content(soup, name="robots").lower()
    if "noindex" in robots:
        # break out early, page is not indexable
        return {"noindex": True}

    canonical_tag = soup.find("link", attrs={"rel": "canonical"})
    canonical = canonical_tag.get("href", "").strip() if canonical_tag else ""

    og_type = _meta_content(soup, og_property="og:type").lower()

    h1_tag = soup.find("h1")
    h1 = h1_tag.get_text(separator=" ", strip=True) if h1_tag else ""

    title = _build_title(soup)
    description = _build_description(soup, h1)
    meta_description = _meta_content(soup, name="description")

    body = soup.find("body")
    body_text = body.get_text(separator=" ", strip=True) if body else ""
    word_count = len(body_text.split()) if body_text else 0

    internal_links = []
    for link in soup.find_all("a", href=True):
        href = link.get("href")
        if not href or href.startswith("#"):
            # no destination, or fragment, skip
            continue
        new_url = urljoin(page_url, href)
        parsed = urlparse(new_url)
        if parsed.scheme in ("http", "https") and is_internal_link(new_url, base_domain):
            internal_links.append(normalize_url(new_url))

    return {
        "title": title,
        "description": description,
        "h1": h1,
        "og_type": og_type,
        "noindex": False,
        "canonical": canonical,
        "content_hash": content_hash(body_text),
        "meta_description": meta_description,
        "word_count": word_count,
        "homepage_signals": _extract_homepage_signals(soup),
        "internal_links": internal_links,
    }


async def _probe_homepage_timeout(client: httpx.AsyncClient, base_url: str) -> bool:
    """Return True if the homepage request timed out."""
    try:
        await client.get(base_url, timeout=TIMEOUT, follow_redirects=True)
        return False
    except (
        httpx.TimeoutException,
        httpx.ReadTimeout,
        httpx.ConnectTimeout,
        httpx.WriteTimeout,
        httpx.PoolTimeout,
    ):
        return True
    except Exception:
        return False


async def _load_robots(
    client: httpx.AsyncClient, base_url: str
) -> tuple[RobotFileParser, list[str], str | None, int | None]:
    """Fetch and parse robots.txt, returning a permissive parser on failure."""
    rp = RobotFileParser()
    robots_url = f"{base_url}/robots.txt"
    rp.set_url(robots_url)
    sitemap_urls: list[str] = []
    robots_text: str | None = None
    robots_status: int | None = None
    try:
        response = await client.get(robots_url, timeout=TIMEOUT, follow_redirects=True)
        robots_status = response.status_code
        if response.is_success:
            robots_text = response.text
            lines = response.text.splitlines()
            rp.parse(lines) # parse for disallowed paths and user-agent restrictions
            for line in lines:
                # extract sitemap urls from robots.txt 
                if line.lower().startswith("sitemap:"):
                    sitemap_url = line.split(":", 1)[1].strip()
                    if sitemap_url:
                        sitemap_urls.append(sitemap_url)
        else:
            rp.allow_all = True
    except Exception:
        rp.allow_all = True
    return rp, sitemap_urls, robots_text, robots_status


async def _check_llms_txt(client: httpx.AsyncClient, base_url: str) -> bool:
    try:
        response = await client.get(
            urljoin(base_url, "/llms.txt"),
            timeout=TIMEOUT,
            follow_redirects=True,
        )
        return response.status_code == 200
    except Exception:
        return False


def _default_sitemap_candidates(base_url: str) -> list[str]:
    return [
        urljoin(base_url, "/sitemap.xml"),
        urljoin(base_url, "/sitemap_index.xml"),
    ]


def _sitemap_candidate_urls(base_url: str, robots_sitemaps: list[str]) -> list[str]:
    """Build a deduped list of sitemap URLs to try, preferring robots.txt declarations."""
    if robots_sitemaps:
        seen: set[str] = set()
        candidates: list[str] = []
        for url in robots_sitemaps:
            if url not in seen:
                seen.add(url)
                candidates.append(url)
        return candidates
    return _default_sitemap_candidates(base_url)


@dataclass
class SitemapBudget:
    max_urls: int = MAX_SITEMAP_URLS
    max_nested: int = MAX_NESTED_SITEMAPS
    url_count: int = 0
    nested_fetched: int = 0
    capped: bool = False

    def urls_remaining(self) -> int:
        return max(0, self.max_urls - self.url_count)

    def can_fetch_nested(self) -> bool:
        return self.nested_fetched < self.max_nested and self.url_count < self.max_urls

    def mark_capped(self, reason: str) -> None:
        if not self.capped:
            self.capped = True
            logger.info("Sitemap enumeration capped: %s", reason)


def _is_bulk_sitemap(url: str) -> bool:
    lower = url.lower()
    return any(marker in lower for marker in SITEMAP_BULK_MARKERS)


def _nested_sitemap_sort_key(url: str) -> tuple[int, str]:
    lower = url.lower()
    if _is_bulk_sitemap(url):
        return (2, url)
    if any(marker in lower for marker in SITEMAP_PRIORITY_MARKERS):
        return (0, url)
    return (1, url)


def _prioritize_nested_sitemaps(urls: list[str]) -> list[str]:
    """Return nested sitemap URLs with structural pages fetched before bulk content."""
    return sorted(urls, key=_nested_sitemap_sort_key)


def _nested_sitemaps_to_fetch(urls: list[str]) -> list[str]:
    """Prioritize nested sitemaps and drop bulk content indexes entirely."""
    return [url for url in _prioritize_nested_sitemaps(urls) if not _is_bulk_sitemap(url)]


def _merge_sitemap_priorities(
    accumulated: dict[str, float | None],
    incoming: dict[str, float | None],
    budget: SitemapBudget | None = None,
) -> dict[str, float | None]:
    """Merge two dicts of normalized URLs to optional priorities, prioritizing incoming values."""
    merged = dict(accumulated)
    for url, priority in incoming.items():
        if budget is not None and len(merged) >= budget.max_urls:
            budget.mark_capped(f"{budget.max_urls} URL limit reached")
            break
        if url not in merged:
            merged[url] = priority
            continue
        existing = merged[url]
        if priority is None:
            continue
        if existing is None or priority > existing:
            merged[url] = priority
    if budget is not None:
        budget.url_count = len(merged)
    return merged


def _parse_sitemap_priorities(
    soup: BeautifulSoup,
    *,
    max_entries: int | None = None,
) -> dict[str, float | None]:
    """Given a BeautifulSoup object for a sitemap, return a dict of normalized URLs to their optional priorities."""
    entries: dict[str, float | None] = {}

    for url_tag in soup.find_all("url"):
        if max_entries is not None and len(entries) >= max_entries:
            break
        loc = url_tag.find("loc")
        if not loc or not loc.text.strip():
            continue
        priority_tag = url_tag.find("priority")
        priority: float | None = None
        if priority_tag and priority_tag.text.strip():
            try:
                priority = float(priority_tag.text.strip())
            except ValueError:
                priority = None
        page_url = normalize_url(loc.text.strip())
        if should_exclude_sitemap_entry(page_url):
            continue
        entries[page_url] = priority

    if entries:
        return entries

    # fallback if sitemap is flat list of locations
    for loc in soup.find_all("loc"):
        if max_entries is not None and len(entries) >= max_entries:
            break
        if loc.text.strip():
            page_url = normalize_url(loc.text.strip())
            if should_exclude_sitemap_entry(page_url):
                continue
            entries[page_url] = None

    return entries


async def _get_sitemap_priorities(
    client: httpx.AsyncClient,
    sitemap_url: str,
    semaphore: asyncio.Semaphore,
    visited: set[str] | None = None,
    *,
    depth: int = 0,
    budget: SitemapBudget | None = None,
) -> tuple[dict[str, float | None], bool]:
    """Fetch a sitemap and extract page URLs with optional priorities."""
    if visited is None:
        visited = set()
    if budget is None:
        budget = SitemapBudget()

    if sitemap_url in visited:
        return {}, False
    visited.add(sitemap_url)

    try:
        async with semaphore:
            response = await _fetch_with_retry(client, sitemap_url)
        if response is None:
            logger.warning("Failed to fetch sitemap %s", sitemap_url)
            return {}, False
        if not response.is_success:
            logger.info("Sitemap fetch failed (%s): %s", response.status_code, sitemap_url)
            return {}, False
        soup = BeautifulSoup(response.text, "lxml-xml")

        if soup.find("sitemapindex"):
            if depth + 1 >= MAX_SITEMAP_DEPTH:
                logger.info(
                    "Sitemap index at %s: max depth %d reached, skipping nested sitemaps",
                    sitemap_url,
                    MAX_SITEMAP_DEPTH,
                )
                return {}, True

            all_nested = [loc.text.strip() for loc in soup.find_all("loc") if loc.text.strip()]
            nested_sitemaps = _nested_sitemaps_to_fetch(all_nested)
            skipped_bulk = len(all_nested) - len(nested_sitemaps)
            if skipped_bulk:
                logger.info("Skipping %d bulk nested sitemaps", skipped_bulk)
            remaining_nested = max(0, budget.max_nested - budget.nested_fetched)
            logger.info(
                "Sitemap index at %s: following up to %d nested sitemaps (of %d eligible, %d total)",
                sitemap_url,
                min(len(nested_sitemaps), remaining_nested),
                len(nested_sitemaps),
                len(all_nested),
            )

            merged: dict[str, float | None] = {}
            for url in nested_sitemaps:
                if budget.nested_fetched >= budget.max_nested:
                    budget.mark_capped(f"{budget.max_nested} nested sitemap limit reached")
                    break
                if budget.url_count >= budget.max_urls:
                    break

                budget.nested_fetched += 1
                batch_entries, _ = await _get_sitemap_priorities(
                    client,
                    url,
                    semaphore,
                    visited,
                    depth=depth + 1,
                    budget=budget,
                )
                if batch_entries:
                    merged = _merge_sitemap_priorities(merged, batch_entries, budget)
                if budget.url_count >= budget.max_urls:
                    break

            logger.info("Sitemap index at %s: resolved to %d URLs", sitemap_url, len(merged))
            return merged, True

        remaining_urls = budget.urls_remaining()
        if remaining_urls <= 0:
            budget.mark_capped(f"{budget.max_urls} URL limit reached")
            return {}, True

        entries = _parse_sitemap_priorities(soup, max_entries=remaining_urls)
        if len(entries) >= remaining_urls:
            budget.mark_capped(f"{budget.max_urls} URL limit reached")
        logger.info("Sitemap at %s: parsed %d URLs", sitemap_url, len(entries))
        return entries, True
    except Exception:
        logger.warning("Failed to fetch sitemap %s", sitemap_url, exc_info=True)
        return {}, False


async def _collect_sitemap_priorities(
    client: httpx.AsyncClient,
    candidate_urls: list[str],
    semaphore: asyncio.Semaphore,
    budget: SitemapBudget | None = None,
) -> tuple[dict[str, float | None], bool]:
    """Fetch and merge entries from one or more sitemap URLs."""
    if budget is None:
        budget = SitemapBudget()
    merged: dict[str, float | None] = {}
    sitemap_exists = False
    for sitemap_url in candidate_urls:
        if budget.url_count >= budget.max_urls:
            break
        entries, found = await _get_sitemap_priorities(
            client, sitemap_url, semaphore, budget=budget
        )
        if found:
            sitemap_exists = True
        if entries:
            merged = _merge_sitemap_priorities(merged, entries, budget)
            logger.info(
                "Merged sitemap source %s (%d URLs); running total %d URLs",
                sitemap_url,
                len(entries),
                len(merged),
            )
    if budget.capped:
        logger.info(
            "Sitemap enumeration finished with cap (%d URLs, %d nested sitemaps fetched)",
            budget.url_count,
            budget.nested_fetched,
        )
    return merged, sitemap_exists


def _enrich_crawled_pages(
    pages: list[Page],
    inbound_counts: dict[str, int],
    sitemap_priorities: dict[str, float | None],
) -> None:
    """Set inbound counts and sitemap flags on crawled pages."""
    for page in pages:
        key = normalize_url(page.url)
        page.inbound_count = inbound_counts.get(key, 0)
        if key in sitemap_priorities:
            page.in_sitemap = True
            page.sitemap_priority = sitemap_priorities[key]


async def _fetch_page(
    client: httpx.AsyncClient,
    url: str,
    depth: int,
    base_domain: str,
    robots: RobotFileParser,
    semaphore: asyncio.Semaphore,
    fetch_stats: CrawlFetchStats | None = None,
) -> dict | None:
    """Fetch and extract data for a single page given a normalized url."""
    if not robots.can_fetch("*", url):
        # break out early, page is not indexable
        return None

    async with semaphore:
        try:
            response = await _fetch_with_retry(client, url)
            if response is None:
                return None
            if not response.is_success:
                if fetch_stats is not None:
                    fetch_stats.http_errors += 1
                return None
            final_parsed = urlparse(str(response.url))
            if should_skip_url(final_parsed.path.lower(), final_parsed.query):
                return None
            if not _is_html_response(response):
                return None
            html = response.text
        except Exception:
            return None

    try:
        page_data = _extract_page_data(html, url, base_domain)
    except Exception:
        logger.debug("Failed to parse HTML for %s", url, exc_info=True)
        return None
    if page_data["noindex"]:
        return None

    page_url = page_data["canonical"] or url
    result: dict = {
        "page": Page(
            url=page_url,
            title=page_data["title"],
            description=page_data["description"],
            h1=page_data["h1"],
            og_type=page_data["og_type"],
            depth=depth,
            content_hash=page_data["content_hash"],
            meta_description=page_data["meta_description"],
            word_count=page_data["word_count"],
        ),
        "internal_links": page_data["internal_links"],
    }
    if depth == 0:
        result["homepage_signals"] = page_data["homepage_signals"]
    return result


def _add_crawl_candidate(
    crawl_queue: dict[str, tuple[float, str, int]],
    url: str,
    depth: int,
    sitemap_priorities: dict[str, float | None],
    *,
    score_boost: float = 0.0,
    allow_excluded: bool = False,
    base_domain: str,
) -> None:
    """Add or update a URL in the crawl queue with a score."""
    if depth > MAX_DEPTH:
        return
    if not is_internal_link(url, base_domain):
        return
    if not allow_excluded and should_exclude_crawl_candidate(url):
        return

    parsed = urlparse(url)
    if should_skip_url(parsed.path.lower(), parsed.query):
        return

    key = normalize_url(url)
    priority = sitemap_priorities.get(key)
    score = precrawl_url_score(url, priority) + score_boost
    existing = crawl_queue.get(key)
    if existing is None or score > existing[0]:
        crawl_queue[key] = (score, url, depth)


def _store_crawled_page(
    page: Page,
    internal_links: list[str],
    pages: list[Page],
    page_index_by_url: dict[str, int],
    inbound_counts: dict[str, int],
) -> None:
    """Add a page to the crawl list, or replace the existing entry if quality improved."""
    for link in internal_links:
        target = normalize_url(link)
        inbound_counts[target] = inbound_counts.get(target, 0) + 1

    page_key = normalize_url(page.url)
    existing_idx = page_index_by_url.get(page_key)
    if existing_idx is None:
        page_index_by_url[page_key] = len(pages)
        pages.append(page)
    elif page_quality(page) > page_quality(pages[existing_idx]):
        pages[existing_idx] = page


def _sorted_crawl_queue(
    crawl_queue: dict[str, tuple[float, str, int]],
) -> list[tuple[float, str, int]]:
    """Return crawl queue entries sorted by score, depth, then URL."""

    def sort_key(entry: tuple[float, str, int]) -> tuple[float, int, str]:
        score, url, depth = entry
        return (-score, depth, url)

    return sorted(crawl_queue.values(), key=sort_key)


def _seed_crawl_queue(
    crawl_queue: dict[str, tuple[float, str, int]],
    base_url: str,
    base_domain: str,
    sitemap_priorities: dict[str, float | None],
) -> None:
    """Seed crawl queue with homepage, common doc paths, and top sitemap URLs."""
    # first add homepage with highest priority
    _add_crawl_candidate(
        crawl_queue,
        base_url,
        0,
        sitemap_priorities,
        score_boost=HOMEPAGE_BOOST,
        allow_excluded=True,
        base_domain=base_domain,
    )
    # Guess common doc paths only when the sitemap is sparse — avoids wasting
    # crawl budget on speculative 404s when we already have plenty to fetch.
    if len(sitemap_priorities) < DOC_PATH_GUESS_THRESHOLD:
        for path in COMMON_DOC_PATHS:
            _add_crawl_candidate(
                crawl_queue,
                f"{base_url}{path}",
                1,
                sitemap_priorities,
                score_boost=DOC_PATH_BOOST,
                allow_excluded=True,
                base_domain=base_domain,
            )
    else:
        logger.info(
            "Skipping common doc path guesses (%d sitemap URLs >= threshold %d)",
            len(sitemap_priorities),
            DOC_PATH_GUESS_THRESHOLD,
        )
    # return top sitemap urls to crawl first
    sitemap_seed_urls = prioritize_sitemap_urls(
        sitemap_priorities,
        base_domain,
        is_internal=is_internal_link,
        should_skip=should_skip_url,
        limit=SITEMAP_SEED_LIMIT,
    )
    for url in sitemap_seed_urls:
        _add_crawl_candidate(
            crawl_queue,
            url,
            0,
            sitemap_priorities,
            base_domain=base_domain,
        )


def _optional_reserve_urls(
    base_url: str,
    sitemap_priorities: dict[str, float | None],
    base_domain: str,
) -> list[str]:
    """Return optional-pattern URLs to fetch in the post-main crawl reserve."""
    guessed_urls = [urljoin(base_url, path) for path in COMMON_OPTIONAL_PATHS]
    sitemap_urls = top_optional_sitemap_urls(
        sitemap_priorities,
        base_domain,
        is_internal=is_internal_link,
        should_skip=should_skip_url,
        limit=OPTIONAL_CRAWL_RESERVE,
    )

    merged: list[str] = []
    seen: set[str] = set()
    for url in guessed_urls + sitemap_urls:
        key = normalize_url(url)
        if key in seen:
            continue
        seen.add(key)
        merged.append(url)

    return merged[:OPTIONAL_CRAWL_RESERVE]


async def _fetch_optional_pages(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    base_domain: str,
    sitemap_priorities: dict[str, float | None],
    robots: RobotFileParser,
    semaphore: asyncio.Semaphore,
    visited: set[str],
    slots_remaining: int,
    fetch_stats: CrawlFetchStats | None = None,
) -> list[Page]:
    """Fetch optional pages to fill remaining budget after main crawl."""
    if slots_remaining <= 0:
        return []

    optional_urls = _optional_reserve_urls(base_url, sitemap_priorities, base_domain)

    batch: list[str] = []
    for url in optional_urls:
        if len(batch) >= slots_remaining:
            break
        key = normalize_url(url)
        url_id = url_hash(key)
        if url_id in visited:
            continue
        visited.add(url_id)
        batch.append(url)

    if not batch:
        return []

    fetch_results = await asyncio.gather(
        *[
            _fetch_page(
                client,
                url,
                0,
                base_domain,
                robots,
                semaphore,
                fetch_stats,
            )
            for url in batch
        ]
    )

    pages: list[Page] = []
    for result in fetch_results:
        if result is None:
            continue
        pages.append(result["page"])
        if len(pages) >= slots_remaining:
            break

    logger.info(
        "Optional crawl reserve: fetched %d pages (%d candidates)",
        len(pages),
        len(optional_urls),
    )
    return pages


async def crawl_site(
    start_url: str,
    client: httpx.AsyncClient | None = None,
    *,
    on_progress: ProgressCallback = None,
) -> CrawlResult:
    """
    Crawl a site given a start_url to generate an llms.txt that reflects the entire website's structure.

    Returns CrawlResult with pages and crawl metadata.
    """
    parsed_start = urlparse(start_url)
    base_domain = registrable_domain(parsed_start.hostname or "")
    base_url = f"{parsed_start.scheme}://{parsed_start.hostname}"

    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    visited: set[str] = set() # store url hashes
    pages: list[Page] = []
    page_index_by_url: dict[str, int] = {} # normalized url -> index in resulting Page list
    sitemap_exists = False

    async def _run_crawl(active_client: httpx.AsyncClient) -> CrawlResult:
        nonlocal sitemap_exists
        homepage_signals: HomepageSignals | None = None
        fetch_stats = CrawlFetchStats()
        emit_stage(on_progress, STAGE_CHECKING_ACCESS)
        robots, robots_sitemaps, robots_text, robots_status = await _load_robots(
            active_client, base_url
        )
        robots_blocked = not robots.can_fetch("*", base_url)
        homepage_timed_out = (
            False
            if robots_blocked
            else await _probe_homepage_timeout(active_client, base_url)
        )
        if robots_blocked or homepage_timed_out:
            return CrawlResult(
                pages=[],
                base_url=base_url,
                sitemap_exists=False,
                robots_text=robots_text,
                robots_status=robots_status,
                homepage_signals=None,
                llms_txt_exists=False,
                robots_blocked=robots_blocked,
                homepage_timed_out=homepage_timed_out,
            )
        emit_stage(on_progress, STAGE_DISCOVERING_PAGES)
        sitemap_candidates = _sitemap_candidate_urls(base_url, robots_sitemaps)
        if robots_sitemaps:
            logger.info("robots.txt declared %d sitemap(s): %s", len(robots_sitemaps), robots_sitemaps)
        sitemap_priorities, sitemap_exists = await _collect_sitemap_priorities(
            active_client, sitemap_candidates, semaphore
        )
        logger.info("Sitemap found: %d URLs", len(sitemap_priorities))

        emit_stage(on_progress, STAGE_CRAWLING)
        crawl_queue: dict[str, tuple[float, str, int]] = {}
        last_reported_pages = 0
        inbound_counts: dict[str, int] = {}

        # initialize seed crawl queue with more important pages first from official sitemaps
        _seed_crawl_queue(crawl_queue, base_url, base_domain, sitemap_priorities)

        while crawl_queue and len(pages) < MAIN_CRAWL_BUDGET:
            batch_candidates = _sorted_crawl_queue(crawl_queue)
            batch: list[tuple[str, int]] = []
            remaining = MAIN_CRAWL_BUDGET - len(pages)

            for score, url, depth in batch_candidates:
                if len(batch) >= min(remaining, MAX_CONCURRENCY):
                    # return if we have reached the main crawl budget
                    break
                key = normalize_url(url)
                url_id = url_hash(key)
                if url_id in visited:
                    # skip if already visited
                    crawl_queue.pop(key, None)
                    continue
                visited.add(url_id)
                crawl_queue.pop(key, None)
                batch.append((url, depth))

            if not batch:
                break

            fetch_results = await asyncio.gather(
                *[
                    _fetch_page(
                        active_client,
                        url,
                        depth,
                        base_domain,
                        robots,
                        semaphore,
                        fetch_stats,
                    )
                    for url, depth in batch
                ]
            )

            # bfs: process pages in order of depth, then add links to crawl queue
            for result, (url, depth) in zip(fetch_results, batch):
                if len(pages) >= MAIN_CRAWL_BUDGET:
                    break
                if result is None:
                    continue

                if depth == 0 and result.get("homepage_signals"):
                    homepage_signals = result["homepage_signals"]

                page = result["page"]
                _store_crawled_page(
                    page,
                    result["internal_links"],
                    pages,
                    page_index_by_url,
                    inbound_counts,
                )

                if depth < MAX_DEPTH:
                    for link in result["internal_links"]:
                        _add_crawl_candidate(
                            crawl_queue,
                            link,
                            depth + 1,
                            sitemap_priorities,
                            base_domain=base_domain,
                        )

            if on_progress and len(pages) - last_reported_pages >= 5:
                emit_progress(on_progress, STAGE_CRAWLING, pages_crawled=len(pages))
                last_reported_pages = len(pages)

        # fetch optional sitemap pages to fill remaining budget after main crawl
        optional_pages = await _fetch_optional_pages(
            client=active_client,
            base_url=base_url,
            base_domain=base_domain,
            sitemap_priorities=sitemap_priorities,
            robots=robots,
            semaphore=semaphore,
            visited=visited,
            slots_remaining=MAX_PAGES - len(pages),
            fetch_stats=fetch_stats,
        )
        for page in optional_pages:
            _store_crawled_page(page, [], pages, page_index_by_url, inbound_counts)

        if on_progress and len(pages) != last_reported_pages:
            emit_progress(on_progress, STAGE_CRAWLING, pages_crawled=len(pages))

        llms_txt_exists = await _check_llms_txt(active_client, base_url)

        _enrich_crawled_pages(pages, inbound_counts, sitemap_priorities)
        in_sitemap_count = sum(1 for page in pages if page.in_sitemap)
        logger.info(
            "Pages after crawl: %d (max %d; %d matched sitemap entries)",
            len(pages),
            MAX_PAGES,
            in_sitemap_count,
        )
        return CrawlResult(
            pages=pages,
            base_url=base_url,
            sitemap_exists=sitemap_exists,
            robots_text=robots_text,
            robots_status=robots_status,
            homepage_signals=homepage_signals,
            llms_txt_exists=llms_txt_exists,
            http_errors=fetch_stats.http_errors,
            robots_blocked=robots_blocked,
            homepage_timed_out=homepage_timed_out,
        )

    if client is not None:
        return await _run_crawl(client)

    async with httpx.AsyncClient() as owned_client:
        return await _run_crawl(owned_client)
