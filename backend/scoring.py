import logging
import re
from urllib.parse import urlparse

from constants import (
    HIGH_VALUE_SEGMENTS,
    HARD_SKIP_PATTERNS,
    MAX_DEPTH,
    OPTIONAL_CAP,
    OPTIONAL_PATTERNS,
    TIER_1_SIZE,
)
from models import Page
from url_utils import dedupe_pages, normalize_url

logger = logging.getLogger(__name__)

_INBOUND_WEIGHT = 10
_DEPTH_WEIGHT = 5
_PATH_DEPTH_WEIGHT = 3
_SITEMAP_WEIGHT = 15
_SITEMAP_PRIORITY_WEIGHT = 10
_DESCRIPTION_WEIGHT = 10
_TITLE_WEIGHT = 3
_DUPLICATE_PENALTY = 15
_HARD_SKIP_PENALTY = 50
_QUERY_PENALTY = 25
_HIGH_VALUE_SEGMENT_BOOST = 5
_OPTIONAL_DEPRIORITY = 10

LOCALE_PATTERN = re.compile(r"^/[a-z]{2}(-[a-z]{2})?/")


def _content_hash_counts(pages: list[Page]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for page in pages:
        counts[page.content_hash] = counts.get(page.content_hash, 0) + 1
    return counts


def matches_optional_pattern(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(pattern in path for pattern in OPTIONAL_PATTERNS)


def should_exclude_crawl_candidate(url: str, *, exclude_legal: bool = True) -> bool:
    """Drop locale variants and optionally legal pages from main crawl candidacy."""
    path = urlparse(url).path
    if LOCALE_PATTERN.match(path):
        return True
    if exclude_legal and "/legal/" in path.lower():
        return True
    return False


def precrawl_optional_url_score(url: str) -> float:
    """Score optional-pattern URLs before fetch; shallower paths rank higher."""
    path = urlparse(url).path.rstrip("/").lower()
    segments = [segment for segment in path.split("/") if segment]

    # Treat paths deeper than ~4 segments as equally low priority
    return max(0, 4 - len(segments)) * _PATH_DEPTH_WEIGHT


def top_optional_sitemap_urls(
    sitemap_priorities: dict[str, float | None],
    base_domain: str,
    *,
    is_internal,
    should_skip,
    limit: int,
) -> list[str]:
    """Return shallow optional-pattern sitemap URLs for the reserved crawl budget."""
    candidates: list[tuple[float, str]] = []

    for url in sitemap_priorities:
        if not is_internal(url, base_domain):
            continue
        if should_exclude_crawl_candidate(url, exclude_legal=False):
            continue
        parsed = urlparse(url)
        if should_skip(parsed.path.lower(), parsed.query):
            continue
        if not matches_optional_pattern(url):
            continue
        candidates.append((precrawl_optional_url_score(url), url))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    selected = [url for _, url in candidates[:limit]]
    logger.info(
        "Optional sitemap candidates: %d after filter; reserving %d for crawl",
        len(candidates),
        len(selected),
    )
    return selected


def precrawl_url_score(url: str, sitemap_priority: float | None = None) -> float:
    """Score a URL before fetch using path depth, sitemap metadata, and heuristics."""
    path = urlparse(url).path.rstrip("/").lower()
    segments = [segment for segment in path.split("/") if segment]

    # penalize long paths, shorter paths probably more important
    score = max(0, 4 - len(segments)) * _PATH_DEPTH_WEIGHT
    score += _SITEMAP_WEIGHT

    if sitemap_priority is not None:
        score += sitemap_priority * _SITEMAP_PRIORITY_WEIGHT

    if segments and segments[0] in HIGH_VALUE_SEGMENTS:
        # high value (common) segment in url path
        score += _HIGH_VALUE_SEGMENT_BOOST

    if any(pattern in path for pattern in OPTIONAL_PATTERNS):
        # lower priority patterns
        score -= _OPTIONAL_DEPRIORITY

    if urlparse(url).query:
        score -= _QUERY_PENALTY

    return score


def prioritize_sitemap_urls(
    sitemap_priorities: dict[str, float | None],
    base_domain: str,
    *,
    is_internal,
    should_skip,
    limit: int,
) -> list[str]:
    """Filter, score, and return the top sitemap URLs in deterministic order."""
    candidates: list[tuple[float, str]] = []

    for url, priority in sitemap_priorities.items():
        if not is_internal(url, base_domain):
            continue
        parsed = urlparse(url)
        if should_skip(parsed.path.lower(), parsed.query):
            continue
        if should_exclude_crawl_candidate(url):
            continue
        candidates.append((precrawl_url_score(url, priority), url))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    selected = [url for _, url in candidates[:limit]]

    logger.info(
        "Sitemap crawl candidates: %d after filter (from %d); seeding top %d",
        len(candidates),
        len(sitemap_priorities),
        len(selected),
    )
    if selected:
        preview = ", ".join(selected[:8])
        logger.info("Top sitemap seeds: %s%s", preview, "..." if len(selected) > 8 else "")

    return selected


def calculate_importance_score(
    page: Page,
    *,
    content_hash_counts: dict[str, int],
) -> float:
    path = urlparse(page.url).path.rstrip("/").lower()
    segments = [segment for segment in path.split("/") if segment]

    score = 0.0

    score += page.inbound_count * _INBOUND_WEIGHT
    score += max(0, MAX_DEPTH - page.depth) * _DEPTH_WEIGHT
    score += max(0, 4 - len(segments)) * _PATH_DEPTH_WEIGHT

    if page.in_sitemap:
        score += _SITEMAP_WEIGHT
    if page.sitemap_priority is not None:
        score += page.sitemap_priority * _SITEMAP_PRIORITY_WEIGHT

    description = page.description or page.h1 or page.title or ""
    if len(description) >= 20:
        score += _DESCRIPTION_WEIGHT
    elif page.title or page.h1:
        score += _TITLE_WEIGHT

    if content_hash_counts.get(page.content_hash, 1) > 1:
        score -= _DUPLICATE_PENALTY

    if segments and segments[0] in HIGH_VALUE_SEGMENTS:
        score += _HIGH_VALUE_SEGMENT_BOOST

    if urlparse(page.url).query:
        score -= _QUERY_PENALTY

    if any(pattern in path for pattern in HARD_SKIP_PATTERNS):
        score -= _HARD_SKIP_PENALTY

    return score


def rank_pages_by_importance(pages: list[Page]) -> list[Page]:
    """Return pages sorted by importance score (highest first)."""
    hash_counts = _content_hash_counts(pages)
    return sorted(
        pages,
        key=lambda page: calculate_importance_score(page, content_hash_counts=hash_counts),
        reverse=True,
    )


def select_tier_1_pages(candidates: list[Page]) -> list[Page]:
    """Return the top-ranked pages sent to the categorizer."""
    ranked = rank_pages_by_importance(dedupe_pages(candidates))
    return ranked[:TIER_1_SIZE]


def select_optional_pages(pages: list[Page], tier_1: list[Page]) -> list[Page]:
    """Pick low-priority Optional-section pages from crawled pages below Tier 1."""
    tier_1_keys = {normalize_url(page.url) for page in tier_1}
    ranked = rank_pages_by_importance(dedupe_pages(pages))
    optional_candidates = [
        page
        for page in ranked
        if normalize_url(page.url) not in tier_1_keys
        and matches_optional_pattern(page.url)
    ]
    return optional_candidates[:OPTIONAL_CAP]
