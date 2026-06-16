from dataclasses import dataclass

from changes import detect_changes
from db import (
    finalize_generation,
    get_domain_id,
    get_stored_scan,
    load_generation_hashes,
    load_page_hashes,
    page_hash_map,
    set_unviewed_changes,
)
from generator import categorize_pages, generate_llms_txt
from scan import run_scan


@dataclass
class RecrawlResult:
    content_changed: bool
    regenerated: bool


async def build_llms_txt(pages) -> tuple[str, int]:
    categorized = await categorize_pages(pages)
    return await generate_llms_txt(pages, categorized)


async def recrawl_domain(
    display_name: str,
    url: str,
    *,
    mark_unviewed: bool,
) -> RecrawlResult:
    domain_id = get_domain_id(display_name)
    baseline = load_generation_hashes(domain_id) if domain_id else {}

    stored = get_stored_scan(display_name)
    had_llms_txt = bool(stored and stored.get("llms_txt"))

    scan = await run_scan(url, persist=True)
    domain_id = get_domain_id(display_name) or scan.domain_id
    current_hashes = load_page_hashes(domain_id) if domain_id else page_hash_map(scan.crawl.pages)

    content_changed = detect_changes(baseline, current_hashes)

    regenerated = False
    if content_changed and had_llms_txt and scan.crawl.pages:
        llms_txt, pages_included = await build_llms_txt(scan.crawl.pages)
        finalize_generation(display_name, llms_txt=llms_txt, pages_included=pages_included)
        regenerated = True

    if content_changed:
        set_unviewed_changes(display_name, unviewed=mark_unviewed)

    return RecrawlResult(
        content_changed=content_changed,
        regenerated=regenerated,
    )
