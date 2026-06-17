from bs4 import BeautifulSoup

from constants import COMMON_DOC_PATHS, DOC_PATH_GUESS_THRESHOLD
from crawler import (
    SitemapBudget,
    _build_title,
    _collect_sitemap_priorities,
    _fetch_with_retry,
    _merge_sitemap_priorities,
    _nested_sitemaps_to_fetch,
    _optional_reserve_urls,
    _parse_sitemap_priorities,
    _prioritize_nested_sitemaps,
    _seed_crawl_queue,
)
from models import Page
from scoring import (
    calculate_importance_score,
    should_exclude_crawl_candidate,
    should_exclude_sitemap_entry,
)
from url_utils import dedupe_pages, is_internal_link, normalize_url, should_skip_url


def _page(path: str, depth: int, **overrides) -> Page:
    defaults = {
        "url": f"https://example.com{path}",
        "title": "",
        "description": "",
        "h1": "",
        "og_type": "",
        "depth": depth,
        "content_hash": "test",
    }
    defaults.update(overrides)
    return Page(**defaults)


def test_url_normalization():
    assert normalize_url("https://Stripe.com/Pricing/") == "https://stripe.com/Pricing"
    assert normalize_url("https://stripe.com/pricing?utm_source=x") == "https://stripe.com/pricing"


def test_build_title_prefers_og_title_when_title_is_global():
    html = """
    <html><head>
      <title>Acme: Global Site Title</title>
      <meta property="og:title" content="Help Center - Acme" />
    </head><body><h1>How can we help?</h1></body></html>
    """
    assert _build_title(BeautifulSoup(html, "lxml")) == "Help Center - Acme"


def test_build_title_falls_back_to_title_when_og_missing():
    html = "<html><head><title>About Us</title></head><body></body></html>"
    assert _build_title(BeautifulSoup(html, "lxml")) == "About Us"


def test_build_title_falls_back_to_h1_when_title_and_og_missing():
    html = "<html><head></head><body><h1>Contact</h1></body></html>"
    assert _build_title(BeautifulSoup(html, "lxml")) == "Contact"


def test_internal_link_check_includes_subdomains():
    assert is_internal_link("https://docs.stripe.com/api", "stripe.com") is True
    assert is_internal_link("https://google.com", "stripe.com") is False


def test_locale_filter():
    assert should_exclude_crawl_candidate("https://stripe.com/fr-fr/pricing") is True
    assert should_exclude_crawl_candidate("https://stripe.com/pricing") is False


def test_should_exclude_sitemap_entry_filters_deep_and_blog_posts():
    assert should_exclude_sitemap_entry("https://example.com/docs") is False
    assert should_exclude_sitemap_entry("https://example.com/blog") is False
    assert should_exclude_sitemap_entry("https://example.com/blog/2024/my-post") is True
    assert should_exclude_sitemap_entry("https://example.com/a/b/c/d/e/page") is True
    assert should_exclude_sitemap_entry("https://example.com/login") is True


def test_importance_score_prioritizes_shallow_pages():
    shallow = _page("/pricing", depth=1)
    deep = _page("/blog/2020/old-post", depth=4)
    assert calculate_importance_score(shallow, content_hash_counts={}) > calculate_importance_score(
        deep, content_hash_counts={}
    )


def test_dedupe_pages_keeps_best_metadata():
    lower_quality = _page("/pricing", depth=2, url="https://Example.com/pricing/")
    higher_quality = _page(
        "/pricing",
        depth=1,
        url="https://example.com/pricing",
        description="Plans and pricing for all products",
        in_sitemap=True,
    )
    result = dedupe_pages([lower_quality, higher_quality])
    assert len(result) == 1
    assert result[0].description == "Plans and pricing for all products"
    assert result[0].in_sitemap is True


def test_should_skip_url_filters_noisy_params():
    assert should_skip_url("/blog", "page=2") is True
    assert should_skip_url("/blog", "utm_source=x") is True
    assert should_skip_url("/login", "") is True
    assert should_skip_url("/pricing", "") is False


def test_prioritize_nested_sitemaps_fetches_core_before_bulk():
    urls = [
        "https://example.com/sitemap_g_vids1.xml",
        "https://example.com/sitemap_core.xml",
        "https://example.com/sitemap_g_shorties1.xml",
        "https://example.com/sitemap_channels.xml",
    ]
    ordered = _prioritize_nested_sitemaps(urls)
    assert ordered.index("https://example.com/sitemap_core.xml") < ordered.index(
        "https://example.com/sitemap_g_vids1.xml"
    )
    assert ordered.index("https://example.com/sitemap_channels.xml") < ordered.index(
        "https://example.com/sitemap_g_shorties1.xml"
    )


def test_nested_sitemaps_to_fetch_skips_bulk_content():
    urls = [
        "https://example.com/sitemap_core.xml",
        "https://example.com/sitemap_g_vids1.xml",
        "https://example.com/sitemap_models1.xml",
        "https://example.com/sitemap_playlists1.xml",
        "https://example.com/sitemap_lang.xml",
    ]
    selected = _nested_sitemaps_to_fetch(urls)
    assert selected == [
        "https://example.com/sitemap_core.xml",
        "https://example.com/sitemap_lang.xml",
    ]


def test_merge_sitemap_priorities_stops_at_url_budget():
    budget = SitemapBudget(max_urls=3, max_nested=10)
    incoming = {
        "https://example.com/a": None,
        "https://example.com/b": None,
        "https://example.com/c": None,
        "https://example.com/d": None,
    }
    merged = _merge_sitemap_priorities({}, incoming, budget)
    assert len(merged) == 3
    assert budget.url_count == 3
    assert budget.capped is True


def test_parse_sitemap_priorities_respects_max_entries():
    xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/one</loc></url>
      <url><loc>https://example.com/two</loc></url>
      <url><loc>https://example.com/three</loc></url>
    </urlset>
    """
    soup = BeautifulSoup(xml, "lxml-xml")
    entries = _parse_sitemap_priorities(soup, max_entries=2)
    assert len(entries) == 2
    assert "https://example.com/one" in entries
    assert "https://example.com/two" in entries


def test_collect_sitemap_priorities_caps_nested_fetches():
    import asyncio

    import httpx

    index_xml = """
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://example.com/sitemap_core.xml</loc></sitemap>
      <sitemap><loc>https://example.com/sitemap_g_vids1.xml</loc></sitemap>
      <sitemap><loc>https://example.com/sitemap_g_vids2.xml</loc></sitemap>
    </sitemapindex>
    """
    core_xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/about</loc></url>
      <url><loc>https://example.com/pricing</loc></url>
    </urlset>
    """
    bulk_xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/video/1</loc></url>
    </urlset>
    """
    fetched: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        fetched.append(str(request.url))
        if request.url.path.endswith("sitemaps.xml"):
            return httpx.Response(200, text=index_xml)
        if request.url.path.endswith("sitemap_core.xml"):
            return httpx.Response(200, text=core_xml)
        return httpx.Response(200, text=bulk_xml)

    async def run() -> tuple[dict[str, float | None], bool]:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="https://example.com") as client:
            semaphore = asyncio.Semaphore(5)
            return await _collect_sitemap_priorities(
                client,
                ["https://example.com/sitemaps.xml"],
                semaphore,
                budget=SitemapBudget(max_nested=1, max_urls=100),
            )

    merged, found = asyncio.run(run())
    assert found is True
    assert "https://example.com/about" in merged
    assert "https://example.com/pricing" in merged
    assert "https://example.com/video/1" not in merged
    assert any(url.endswith("sitemap_core.xml") for url in fetched)
    assert not any(url.endswith("sitemap_g_vids1.xml") for url in fetched)


def test_collect_sitemap_priorities_stops_at_url_budget_before_next_fetch():
    import asyncio

    import httpx

    index_xml = """
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://example.com/sitemap_core.xml</loc></sitemap>
      <sitemap><loc>https://example.com/sitemap_lang.xml</loc></sitemap>
    </sitemapindex>
    """
    core_xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/about</loc></url>
      <url><loc>https://example.com/pricing</loc></url>
      <url><loc>https://example.com/docs</loc></url>
    </urlset>
    """
    lang_xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/fr</loc></url>
    </urlset>
    """
    fetched: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        fetched.append(str(request.url))
        if request.url.path.endswith("sitemaps.xml"):
            return httpx.Response(200, text=index_xml)
        if request.url.path.endswith("sitemap_core.xml"):
            return httpx.Response(200, text=core_xml)
        return httpx.Response(200, text=lang_xml)

    async def run() -> tuple[dict[str, float | None], bool]:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="https://example.com") as client:
            semaphore = asyncio.Semaphore(5)
            return await _collect_sitemap_priorities(
                client,
                ["https://example.com/sitemaps.xml"],
                semaphore,
                budget=SitemapBudget(max_nested=10, max_urls=2),
            )

    merged, found = asyncio.run(run())
    assert found is True
    assert len(merged) == 2
    assert "https://example.com/fr" not in merged
    assert any(url.endswith("sitemap_core.xml") for url in fetched)
    assert not any(url.endswith("sitemap_lang.xml") for url in fetched)


def test_fetch_with_retry_recovers_from_429():
    import asyncio

    import httpx

    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429)
        return httpx.Response(200, text="ok")

    async def run() -> httpx.Response | None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="https://example.com") as client:
            return await _fetch_with_retry(client, "https://example.com/page")

    response = asyncio.run(run())
    assert response is not None
    assert response.status_code == 200
    assert attempts == 2


def test_fetch_with_retry_skips_after_exhausted_429():
    import asyncio

    import httpx

    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(429)

    async def run() -> httpx.Response | None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="https://example.com") as client:
            return await _fetch_with_retry(client, "https://example.com/page")

    response = asyncio.run(run())
    assert response is not None
    assert response.status_code == 429
    assert attempts == 3


def test_fetch_with_retry_recovers_from_timeout():
    import asyncio

    import httpx

    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadTimeout("timed out")
        return httpx.Response(200, text="ok")

    async def run() -> httpx.Response | None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="https://example.com") as client:
            return await _fetch_with_retry(client, "https://example.com/page")

    response = asyncio.run(run())
    assert response is not None
    assert response.status_code == 200
    assert attempts == 2


def test_optional_reserve_urls_merges_guesses_when_sitemap_has_optional_urls():
    sitemap = {"https://example.com/privacy": 0.8}
    urls = _optional_reserve_urls("https://example.com", sitemap, "example.com")
    normalized = {normalize_url(url) for url in urls}
    assert "https://example.com/privacy" in normalized
    assert "https://example.com/terms" in normalized


def test_seed_crawl_queue_guesses_doc_paths_when_sitemap_sparse():
    crawl_queue: dict[str, tuple[float, str, int]] = {}
    _seed_crawl_queue(crawl_queue, "https://example.com", "example.com", {})

    guessed_urls = {url for _, url, _ in crawl_queue.values()}
    assert "https://example.com/docs" in guessed_urls


def test_seed_crawl_queue_skips_doc_guesses_when_sitemap_is_rich():
    crawl_queue: dict[str, tuple[float, str, int]] = {}
    sitemap_priorities = {
        f"https://example.com/page-{index}": 0.5
        for index in range(DOC_PATH_GUESS_THRESHOLD)
    }
    _seed_crawl_queue(crawl_queue, "https://example.com", "example.com", sitemap_priorities)

    guessed_urls = {url for _, url, _ in crawl_queue.values()}
    for path in COMMON_DOC_PATHS:
        assert f"https://example.com{path}" not in guessed_urls
