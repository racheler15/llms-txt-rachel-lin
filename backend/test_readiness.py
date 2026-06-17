from crawler import CrawlResult, HomepageSignals
from models import Page
from readiness import detect_js_limited_crawl


def _page(path: str, *, depth: int = 1, word_count: int = 200) -> Page:
    return Page(
        url=f"https://example.com{path}",
        title="Example",
        description="",
        h1="",
        og_type="",
        depth=depth,
        content_hash=f"hash-{path}",
        word_count=word_count,
    )


def test_detect_js_limited_crawl_flags_spa_homepage():
    crawl = CrawlResult(
        pages=[_page("/", depth=0, word_count=12)],
        base_url="https://example.com",
        robots_text="",
        robots_status=404,
        sitemap_exists=False,
        llms_txt_exists=False,
        http_errors=0,
        homepage_signals=HomepageSignals(
            has_json_ld=False,
            has_og_title=False,
            has_og_description=False,
        ),
    )
    assert detect_js_limited_crawl(crawl) is True


def test_detect_js_limited_crawl_ignores_content_rich_sites():
    crawl = CrawlResult(
        pages=[
            _page("/", depth=0, word_count=800),
            _page("/docs", depth=1, word_count=500),
            _page("/pricing", depth=1, word_count=350),
        ],
        base_url="https://example.com",
        robots_text="",
        robots_status=404,
        sitemap_exists=True,
        llms_txt_exists=False,
        http_errors=0,
        homepage_signals=None,
    )
    assert detect_js_limited_crawl(crawl) is False
