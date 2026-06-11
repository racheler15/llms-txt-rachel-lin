import os
from urllib.parse import urlparse

import anthropic
from dotenv import load_dotenv

from constants import (
    Category, CATEGORY_RULES, SKIP_PATTERNS, SECTION_ORDER,
)
from crawler import Page

load_dotenv()

MIN_DESCRIPTION_LENGTH = 20
MAX_LINKS_PER_SECTION = 8
MAX_OPTIONAL_LINKS = 5
MAX_TOTAL_LINKS = 30


def _should_skip(path: str, query: str) -> bool:
    """Check if a URL should be excluded from the llms.txt entirely."""
    if any(pattern in path for pattern in SKIP_PATTERNS):
        return True
    if any(param in query for param in ("page=", "ref=", "utm_")):
        return True
    return False


OG_TYPE_MAP: dict[str, Category] = {
    "article": Category.DOCS,
    "product": Category.PRODUCTS,
}


def _categorize_page(page: Page) -> Category | None:
    """Assign a category to a page based on URL path, then og:type as fallback."""
    parsed = urlparse(page.url)
    path = parsed.path.lower()

    if path == "/" or path == "":
        return None

    if _should_skip(path, parsed.query):
        return None

    for category, prefixes in CATEGORY_RULES.items():
        if any(path.startswith(prefix) for prefix in prefixes):
            return category

    if page.og_type in OG_TYPE_MAP:
        return OG_TYPE_MAP[page.og_type]

    return None


def categorize_pages(pages: list[Page]) -> dict[Category, list[Page]]:
    """Group pages into categories based on URL path patterns."""
    grouped: dict[Category, list[Page]] = {c: [] for c in Category}
    for page in pages:
        category = _categorize_page(page)
        if category is not None:
            grouped[category].append(page)
    return grouped


def _generate_site_description(title: str, url: str) -> str:
    """Use Claude to generate a one-sentence site description when none exists."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return ""
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-20250514",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": (
                    f"Write a single concise sentence describing what this website/product is. "
                    f"No quotes, no prefix, just the description.\n\n"
                    f"Title: {title}\n"
                    f"URL: {url}"
                ),
            }],
        )
        return response.content[0].text.strip()
    except Exception:
        return ""


def generate_llms_txt(
    pages: list[Page],
    categorized: dict[Category, list[Page]],
) -> str:
    """Assemble a spec-compliant llms.txt markdown string."""
    homepage = next((p for p in pages if p.depth == 0), None)
    site_title = homepage.title if homepage else urlparse(pages[0].url).hostname

    if homepage and homepage.description:
        site_description = homepage.description
    elif homepage:
        site_description = _generate_site_description(homepage.title, homepage.url)
    else:
        site_description = ""

    lines: list[str] = []
    total_links = 0

    lines.append(f"# {site_title}")
    lines.append("")

    if site_description:
        lines.append(f"> {site_description}")
        lines.append("")

    for category in SECTION_ORDER:
        category_pages = categorized.get(category, [])
        if not category_pages:
            continue

        # Prioritize by depth (shallower = more important)
        category_pages = sorted(category_pages, key=lambda p: p.depth)

        remaining_link_count = MAX_TOTAL_LINKS - total_links
        if remaining_link_count <= 0:
            break
        section_limit = MAX_OPTIONAL_LINKS if category == Category.OPTIONAL else MAX_LINKS_PER_SECTION
        visible_pages = category_pages[:min(section_limit, remaining_link_count)]

        section_name = category.value
        lines.append(f"## {section_name}")
        lines.append("")

        for page in visible_pages:
            entry = f"- [{page.title}]({page.url})"
            if page.description:
                entry += f": {page.description}"
            lines.append(entry)
            total_links += 1

        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
