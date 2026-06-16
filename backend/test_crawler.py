from models import Page
from scoring import calculate_importance_score, should_exclude_crawl_candidate
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


def test_internal_link_check_includes_subdomains():
    assert is_internal_link("https://docs.stripe.com/api", "stripe.com") is True
    assert is_internal_link("https://google.com", "stripe.com") is False


def test_locale_filter():
    assert should_exclude_crawl_candidate("https://stripe.com/fr-fr/pricing") is True
    assert should_exclude_crawl_candidate("https://stripe.com/pricing") is False


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
