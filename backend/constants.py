from enum import Enum


class Category(str, Enum):
    GETTING_STARTED = "Getting Started"
    API = "API"
    DOCS = "Docs"
    EXAMPLES = "Examples"
    PRODUCTS = "Products"
    PRICING = "Pricing"
    CHANGELOG = "Changelog"
    INTEGRATIONS = "Integrations"
    FAQ = "FAQ"
    OPTIONAL = "Optional"


CATEGORY_RULES: dict[Category, list[str]] = {
    Category.GETTING_STARTED: [
        "/getting-started", "/quickstart", "/quick-start",
        "/installation", "/onboarding", "/setup",
    ],
    Category.API: [
        "/api-reference", "/api-docs", "/api/reference",
        "/reference", "/sdk", "/endpoints",
    ],
    Category.DOCS: [
        "/docs", "/documentation", "/guide", "/guides",
        "/tutorial", "/tutorials", "/developer", "/manual",
        "/learn", "/handbook",
    ],
    Category.EXAMPLES: [
        "/examples", "/samples", "/demos", "/templates",
        "/playground", "/sandbox", "/snippets",
    ],
    Category.PRODUCTS: [
        "/products", "/features", "/solutions", "/use-cases",
        "/enterprise", "/platform",
    ],
    Category.PRICING: [
        "/pricing", "/plans", "/fees",
    ],
    Category.INTEGRATIONS: [
        "/integrations", "/plugins", "/connectors",
        "/extensions", "/marketplace",
    ],
    Category.CHANGELOG: [
        "/changelog", "/releases", "/release-notes",
        "/whats-new", "/updates",
    ],
    Category.FAQ: [
        "/faq", "/troubleshooting", "/knowledge-base",
    ],
    Category.OPTIONAL: [
        "/blog", "/posts", "/news", "/articles", "/newsroom",
        "/customers", "/case-studies", "/partners",
        "/about", "/team", "/careers", "/contact", "/jobs",
        "/press", "/media", "/community", "/forum",
        "/sessions", "/annual-updates", "/lp",
    ],
}

SKIP_PATTERNS = [
    "/login", "/signup", "/sign-up", "/sign-in", "/register",
    "/auth", "/oauth", "/sso",
    "/search", "/404", "/500",
    "/cart", "/checkout/",
    "/cdn-cgi/", "/assets/", "/static/",
    "/tag/", "/tags/", "/category/", "/categories/",
    "/page/",
    "/terms", "/privacy", "/legal", "/policy",
    "/tos", "/cookies", "/compliance",
    "/sitemap", "/robots.txt",
    "/rss", "/feed", "/atom",
    ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".pdf", ".zip", ".css", ".js",
]

SECTION_ORDER = [
    Category.GETTING_STARTED,
    Category.API,
    Category.DOCS,
    Category.EXAMPLES,
    Category.PRODUCTS,
    Category.PRICING,
    Category.INTEGRATIONS,
    Category.CHANGELOG,
    Category.FAQ,
    Category.OPTIONAL,
]

COMMON_DOC_PATHS: list[str] = sorted(set(
    path
    for c in (Category.GETTING_STARTED, Category.API, Category.DOCS)
    for path in CATEGORY_RULES[c]
))
