import asyncio
import json
import logging
import os
import re
from urllib.parse import urlparse

import anthropic
from dotenv import load_dotenv

from constants import OPTIONAL_CAP, OPTIONAL_SECTION_NAME
from models import Page
from scoring import select_optional_pages, select_tier_1_pages, matches_optional_pattern
from url_utils import dedupe_pages, normalize_url, should_skip_url

load_dotenv()

logger = logging.getLogger(__name__)

MIN_DESCRIPTION_LENGTH = 20
MAX_LINKS_PER_SECTION = 15
MAX_TOTAL_LINKS = 100
MAX_PAGES_TO_SELECT = 30
CLAUDE_MODEL = "claude-haiku-4-5-20251001"


def _get_homepage(pages: list[Page]) -> Page | None:
    return next((p for p in pages if p.depth == 0), None)


def _homepage_context(pages: list[Page]) -> str:
    homepage = _get_homepage(pages) or pages[0]
    title = homepage.title or homepage.h1 or urlparse(homepage.url).hostname or ""
    description = homepage.description or homepage.h1 or ""
    return (
        f"Site: {title}\n"
        f"URL: {homepage.url}\n"
        f"Description: {description}\n"
        f"H1: {homepage.h1 or 'n/a'}"
    )


def _page_summary(page: Page) -> str:
    desc = page.description or page.h1 or page.title or ""
    title = page.title or page.h1 or "untitled"
    return f"- {page.url} | {title} | {desc[:120]} | depth={page.depth}"


def _candidate_pages(pages: list[Page]) -> list[Page]:
    candidates = []
    for page in dedupe_pages(pages):
        parsed = urlparse(page.url)
        path = parsed.path.lower()
        if path in ("", "/"):
            continue
        if should_skip_url(path, parsed.query):
            continue
        if parsed.query:
            continue
        candidates.append(page)
    return candidates


def _page_lookup(pages: list[Page]) -> dict[str, Page]:
    return {normalize_url(page.url): page for page in dedupe_pages(pages)}


def _parse_json_object(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object")
    return parsed


async def _create_claude_message(*, api_key: str, max_tokens: int, content: str):
    client = anthropic.Anthropic(api_key=api_key)
    return await asyncio.to_thread(
        client.messages.create,
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": content}],
    )


def _resolve_categorized_urls(
    raw: dict,
    lookup: dict[str, Page],
    *,
    used_urls: set[str] | None = None,
) -> dict[str, list[Page]]:
    grouped: dict[str, list[Page]] = {}
    seen = set(used_urls or ())

    for section, urls in raw.items():
        if not isinstance(section, str) or not isinstance(urls, list):
            continue
        if section.strip().lower() == OPTIONAL_SECTION_NAME.lower():
            continue

        section_pages: list[Page] = []
        for url in urls:
            if not isinstance(url, str):
                continue
            normalized = normalize_url(url)
            if normalized in seen or normalized not in lookup:
                continue
            seen.add(normalized)
            section_pages.append(lookup[normalized])

        if section_pages:
            grouped[section.strip()] = section_pages

    return grouped


async def _categorize_with_claude(
    pages: list[Page],
    tier_1: list[Page],
) -> dict[str, list[Page]] | None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or not tier_1:
        return None

    catalog = "\n".join(_page_summary(page) for page in tier_1)
    prompt = (
        "You are building an llms.txt file for a website.\n\n"
        "## Homepage context\n"
        f"{_homepage_context(pages)}\n\n"
        "Use this to understand what kind of site this is and which pages "
        "would be most useful for an LLM learning about it.\n\n"
        f"## Tier 1 pages ({len(tier_1)} highest-importance candidates)\n"
        f"{catalog}\n\n"
        "## Task\n"
        f"1. Pick the {MAX_PAGES_TO_SELECT} most useful pages from the list above\n"
        "2. Group them into 4-6 meaningful sections for THIS specific site\n"
        "3. Prefer diverse, unique pages — include each URL at most once across all sections\n"
        "4. Exclude filter/listing variants, duplicate paths, "
        "and nav/booking pages unless core to understanding the business\n"
        "5. Do NOT include the homepage URL in any section\n"
        "6. Do NOT create an Optional section — it is added separately\n\n"
        "Return ONLY valid JSON:\n"
        '{"Section Name": ["url1", "url2"], ...}\n\n'
        "Every URL must appear in the Tier 1 list above. Do not invent URLs."
    )

    try:
        response = await _create_claude_message(
            api_key=api_key,
            max_tokens=2000,
            content=prompt,
        )
        raw = _parse_json_object(response.content[0].text)
        grouped = _resolve_categorized_urls(raw, _page_lookup(pages))
        if not grouped:
            logger.warning("Claude returned no valid categorized URLs")
            return None
        return grouped
    except Exception:
        logger.exception("Claude categorization failed, using fallback")
        return None


def _categorize_fallback(tier_1: list[Page]) -> dict[str, list[Page]]:
    """Importance-ranked fallback when Claude is unavailable."""
    if not tier_1:
        return {}
    return {"Main": tier_1[:MAX_PAGES_TO_SELECT]}


async def categorize_pages(pages: list[Page]) -> dict[str, list[Page]]:
    """
    Rank pages, categorize Tier 1 via Claude, and append a spec Optional section.
    """
    candidates = _candidate_pages(pages)
    tier_1 = select_tier_1_pages(candidates)
    optional_pages = select_optional_pages(candidates, tier_1)
    logger.info(
        "Optional section: %d pages from %d below-tier-1 optional matches",
        len(optional_pages),
        sum(1 for p in candidates if matches_optional_pattern(p.url)),
    )

    main_sections = (
        await _categorize_with_claude(pages, tier_1) or _categorize_fallback(tier_1)
    )

    used_urls = {
        normalize_url(page.url)
        for section_pages in main_sections.values()
        for page in section_pages
    }
    optional_pages = [
        page for page in optional_pages
        if normalize_url(page.url) not in used_urls
    ][:OPTIONAL_CAP]

    result = dict(main_sections)
    if optional_pages:
        result[OPTIONAL_SECTION_NAME] = optional_pages
    return result


async def _generate_site_description(title: str, url: str) -> str:
    """Use Claude to generate a one-sentence site description when none exists."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return ""
    try:
        response = await _create_claude_message(
            api_key=api_key,
            max_tokens=100,
            content=(
                f"Write a single concise sentence describing what this website/product is. "
                f"No quotes, no prefix, just the description.\n\n"
                f"Title: {title}\n"
                f"URL: {url}"
            ),
        )
        return response.content[0].text.strip()
    except Exception:
        return ""


def _page_description(page: Page) -> str:
    return page.description or page.h1 or page.title or ""


def _section_limit(section_name: str) -> int:
    if section_name.strip().lower() == OPTIONAL_SECTION_NAME.lower():
        return OPTIONAL_CAP
    return MAX_LINKS_PER_SECTION


async def generate_llms_txt(
    pages: list[Page],
    categorized: dict[str, list[Page]],
) -> tuple[str, int]:
    """Assemble a spec-compliant llms.txt markdown string and return included page count."""
    homepage = _get_homepage(pages)
    site_title = homepage.title if homepage else urlparse(pages[0].url).hostname

    if homepage and homepage.description:
        site_description = homepage.description
    elif homepage:
        site_description = await _generate_site_description(homepage.title, homepage.url)
    else:
        site_description = ""

    main_sections = {
        name: section_pages
        for name, section_pages in categorized.items()
        if name.strip().lower() != OPTIONAL_SECTION_NAME.lower()
    }
    optional_pages = categorized.get(OPTIONAL_SECTION_NAME, [])

    lines: list[str] = []
    total_links = 0
    emitted_urls: set[str] = set()

    lines.append(f"# {site_title}")
    lines.append("")

    if site_description:
        lines.append(f"> {site_description}")
        lines.append("")

    def append_section(section_name: str, section_pages: list[Page]) -> None:
        nonlocal total_links

        remaining_link_count = MAX_TOTAL_LINKS - total_links
        if remaining_link_count <= 0:
            return

        section_limit = _section_limit(section_name)
        visible_pages = section_pages[:min(section_limit, remaining_link_count)]

        lines.append(f"## {section_name}")
        lines.append("")

        section_links = 0
        for page in visible_pages:
            page_key = normalize_url(page.url)
            if page_key in emitted_urls:
                continue

            description = _page_description(page)
            if len(description) < MIN_DESCRIPTION_LENGTH:
                continue
            link_title = page.title or page.h1 or urlparse(page.url).path
            entry = f"- [{link_title}]({page.url}): {description}"
            lines.append(entry)
            emitted_urls.add(page_key)
            total_links += 1
            section_links += 1

        if section_links == 0:
            lines.pop()
            lines.pop()
        else:
            lines.append("")

    for section_name, section_pages in main_sections.items():
        append_section(section_name, section_pages)

    if optional_pages:
        append_section(OPTIONAL_SECTION_NAME, optional_pages)

    return "\n".join(lines).rstrip() + "\n", total_links
