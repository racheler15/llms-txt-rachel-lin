from __future__ import annotations

from dataclasses import dataclass, field

from crawler import CrawlResult, HomepageSignals

AI_BOTS = ("GPTBot", "ClaudeBot", "PerplexityBot", "GoogleExtended", "FacebookBot")

DIMENSION_ORDER = (
    "ai_bot_access",
    "structured_data",
    "content_clarity",
    "site_structure",
    "llms_txt",
)


@dataclass
class ReadinessDimension:
    score: int
    max_score: int
    label: str
    detail: str
    recommendations: list[str]
    signals: dict = field(default_factory=dict)


@dataclass
class ReadinessCategory:
    id: str
    score: int
    max_score: int
    label: str


@dataclass
class ReadinessResult:
    total: int
    categories: list[ReadinessCategory]
    recommendations: list[str]
    max_total: int = 100
    js_rendering_likely: bool = False


def detect_js_limited_crawl(crawl: CrawlResult) -> bool:
    """True when crawled HTML looks like JS-rendered shells with little text content."""
    pages = crawl.pages
    if not pages:
        return False

    homepage = next((page for page in pages if page.depth == 0), None)
    if homepage and homepage.word_count < 100:
        return True

    avg_word_count = sum(page.word_count for page in pages) / len(pages)
    if avg_word_count < 80:
        return True

    thin_pages = sum(1 for page in pages if page.word_count < 50)
    return thin_pages / len(pages) >= 0.4


def _parse_robots_sections(robots_text: str) -> dict[str, list[tuple[str, str]]]:
    """Parse robots.txt into per-agent directive lists."""
    sections: dict[str, list[tuple[str, str]]] = {}
    current_agents: list[str] = []

    for raw_line in robots_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()

        if key == "user-agent":
            agent = value.lower()
            current_agents = [agent]
            sections.setdefault(agent, [])
        elif key in ("disallow", "allow") and current_agents:
            for agent in current_agents:
                sections.setdefault(agent, []).append((key, value))

    return sections


def _bot_allowed(sections: dict[str, list[tuple[str, str]]], bot: str) -> bool:
    """Return True if bot has no dedicated block or is not fully disallowed."""
    directives = sections.get(bot.lower())
    if directives is None:
        return True

    for directive, path in directives:
        if directive == "disallow" and path == "/":
            return False
    return True


def _score_llms_txt(crawl: CrawlResult) -> ReadinessDimension:
    exists = crawl.llms_txt_exists
    score = 20 if exists else 0
    detail = "llms.txt found" if exists else "No llms.txt found"
    recommendations = []
    if not exists:
        recommendations.append(
            "Generate and publish an llms.txt file at yourdomain.com/llms.txt"
        )
    return ReadinessDimension(
        score=score,
        max_score=20,
        label="llms.txt file",
        detail=detail,
        recommendations=recommendations,
        signals={"exists": exists},
    )


def _score_ai_bot_access(crawl: CrawlResult) -> ReadinessDimension:
    sections = (
        _parse_robots_sections(crawl.robots_text)
        if crawl.robots_status == 200 and crawl.robots_text
        else {}
    )

    bot_status = {bot: _bot_allowed(sections, bot) for bot in AI_BOTS}
    score = sum(5 for allowed in bot_status.values() if allowed)
    allowed_count = sum(1 for allowed in bot_status.values() if allowed)
    detail = f"{allowed_count}/{len(AI_BOTS)} AI bots allowed"

    recommendations = []
    bot_labels = {
        "GPTBot": "GPTBot",
        "ClaudeBot": "ClaudeBot",
        "PerplexityBot": "PerplexityBot",
        "GoogleExtended": "Google-Extended",
        "FacebookBot": "FacebookBot",
    }
    for bot, allowed in bot_status.items():
        if not allowed:
            label = bot_labels.get(bot, bot)
            if bot == "GPTBot":
                recommendations.append(
                    "Unblock GPTBot in robots.txt to allow ChatGPT to crawl your site"
                )
            else:
                recommendations.append(f"Unblock {label} in robots.txt to allow AI crawlers")

    return ReadinessDimension(
        score=score,
        max_score=25,
        label="AI bot access",
        detail=detail,
        recommendations=recommendations,
        signals=bot_status,
    )


def _score_structured_data(signals: HomepageSignals | None) -> ReadinessDimension:
    has_json_ld = signals.has_json_ld if signals else False
    has_og_title = signals.has_og_title if signals else False
    has_og_description = signals.has_og_description if signals else False

    score = 0
    if has_json_ld:
        score += 10
    if has_og_title:
        score += 5
    if has_og_description:
        score += 5

    present = sum([has_json_ld, has_og_title, has_og_description])
    detail = f"{present}/3 structured data signals present"

    recommendations = []
    if not has_json_ld:
        recommendations.append(
            "Add JSON-LD structured data to help AI engines understand your content"
        )
    if not has_og_title:
        recommendations.append("Add an og:title meta tag to your homepage")
    if not has_og_description:
        recommendations.append("Add an og:description meta tag to your homepage")

    return ReadinessDimension(
        score=score,
        max_score=20,
        label="Structured data",
        detail=detail,
        recommendations=recommendations,
        signals={
            "json_ld": has_json_ld,
            "og_title": has_og_title,
            "og_description": has_og_description,
        },
    )


def _score_content_clarity(crawl: CrawlResult) -> ReadinessDimension:
    pages = crawl.pages
    if not pages:
        return ReadinessDimension(
            score=0,
            max_score=20,
            label="Content clarity",
            detail="No pages crawled",
            recommendations=["Add meta descriptions to pages missing them"],
            signals={"meta_coverage_pct": 0, "avg_word_count": 0},
        )

    with_meta = sum(1 for page in pages if len(page.meta_description) > 50)
    meta_coverage_pct = round(with_meta / len(pages) * 100)
    meta_score = round(meta_coverage_pct / 100 * 10)

    avg_word_count = round(sum(page.word_count for page in pages) / len(pages))
    if avg_word_count > 300:
        word_score = 10
    elif avg_word_count > 150:
        word_score = 5
    else:
        word_score = 0

    score = meta_score + word_score
    detail = (
        f"{meta_coverage_pct}% of pages have meta descriptions; "
        f"average {avg_word_count} words per page"
    )

    recommendations = []
    if meta_coverage_pct < 100:
        recommendations.append("Add meta descriptions to pages missing them")
    if avg_word_count <= 150:
        recommendations.append("Add more substantive content to pages (aim for 300+ words)")

    return ReadinessDimension(
        score=score,
        max_score=20,
        label="Content clarity",
        detail=detail,
        recommendations=recommendations,
        signals={
            "meta_coverage_pct": meta_coverage_pct,
            "avg_word_count": avg_word_count,
        },
    )


def _score_site_structure(crawl: CrawlResult) -> ReadinessDimension:
    has_sitemap = crawl.sitemap_exists
    has_https = crawl.base_url.startswith("https://")
    no_http_errors = crawl.http_errors == 0 and len(crawl.pages) > 0

    score = 0
    if has_sitemap:
        score += 8
    if has_https:
        score += 4
    if no_http_errors:
        score += 3

    signals = {
        "sitemap": has_sitemap,
        "https": has_https,
        "no_http_errors": no_http_errors,
    }
    present = sum(signals.values())
    detail = f"{present}/3 site structure signals present"

    recommendations = []
    if not has_sitemap:
        recommendations.append("Add a sitemap.xml to help AI crawlers discover all your pages")
    if not has_https:
        recommendations.append("Enable HTTPS for your site")
    if crawl.http_errors > 0:
        recommendations.append("Fix pages that return non-200 status codes")

    return ReadinessDimension(
        score=score,
        max_score=15,
        label="Site structure",
        detail=detail,
        recommendations=recommendations,
        signals=signals,
    )


def _rank_recommendations(dimensions: dict[str, ReadinessDimension]) -> list[str]:
    priority_order = [
        "llms_txt",
        "ai_bot_access",
        "structured_data",
        "content_clarity",
        "site_structure",
    ]
    ranked: list[str] = []

    for key in priority_order:
        dimension = dimensions.get(key)
        if dimension:
            ranked.extend(dimension.recommendations)

    return ranked


def compute_readiness(crawl: CrawlResult) -> ReadinessResult:
    dimensions = {
        "llms_txt": _score_llms_txt(crawl),
        "ai_bot_access": _score_ai_bot_access(crawl),
        "structured_data": _score_structured_data(crawl.homepage_signals),
        "content_clarity": _score_content_clarity(crawl),
        "site_structure": _score_site_structure(crawl),
    }
    total = sum(dimension.score for dimension in dimensions.values())
    categories = [
        ReadinessCategory(
            id=key,
            score=dimensions[key].score,
            max_score=dimensions[key].max_score,
            label=dimensions[key].label,
        )
        for key in DIMENSION_ORDER
        if key in dimensions
    ]

    return ReadinessResult(
        total=total,
        categories=categories,
        recommendations=_rank_recommendations(dimensions),
        js_rendering_likely=detect_js_limited_crawl(crawl),
    )
