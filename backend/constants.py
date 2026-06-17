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

HIGH_VALUE_SEGMENTS = {
    "about", "faq", "faqs", "contact", "press", "blog",
    "docs", "doc", "pricing", "careers", "jobs",
    "payments", "billing", "checkout", "connect", "tax",
    "products", "developers", "api", "platform", "solutions",
}

MAX_DEPTH = 3
MAX_SITEMAP_URLS = 5_000
MAX_NESTED_SITEMAPS = 8
MAX_SITEMAP_DEPTH = 3
SITEMAP_PRIORITY_MARKERS = (
    "core", "page", "pages", "static", "channel", "post", "blog", "doc",
)
SITEMAP_BULK_MARKERS = (
    "vid", "video", "shorties", "image", "media", "model", "playlist",
)
TIER_1_SIZE = 100
OPTIONAL_CRAWL_RESERVE = 15
SITEMAP_SEED_LIMIT = 150
DOC_PATH_GUESS_THRESHOLD = 20
OPTIONAL_CAP = 8
OPTIONAL_SECTION_NAME = "Optional"
HOMEPAGE_BOOST = 1000
DOC_PATH_BOOST = 500

# Never crawl or include in llms.txt
HARD_SKIP_PATTERNS = [
    "/login", "/signup", "/sign-up", "/sign-in", "/register",
    "/auth", "/oauth", "/sso",
    "/search", "/404", "/500",
    "/cart", "/checkout/",
    "/cdn-cgi/", "/assets/", "/static/",
    "/tag/", "/tags/", "/category/", "/categories/",
    "/page/",
    "/sitemap", "/robots.txt",
    "/rss", "/feed", "/atom",
    ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".pdf", ".zip", ".css", ".js",
]

# Low-priority pages eligible for the spec ## Optional section
OPTIONAL_PATTERNS = [
    "/terms", "/privacy", "/legal", "/policy",
    "/tos", "/cookies", "/compliance",
    "/press", "/newsroom", "/media",
    "/careers", "/jobs", "/blog", "/posts", "/news",
    "/articles", "/community", "/forum", "/contact",
    "/about/team", "/partners", "/case-studies",
]

COMMON_DOC_PATHS: list[str] = sorted(set(
    path
    for c in (Category.GETTING_STARTED, Category.API, Category.DOCS)
    for path in CATEGORY_RULES[c]
))

COMMON_OPTIONAL_PATHS: list[str] = [
    "/privacy",
    "/terms",
    "/legal",
    "/policy",
    "/tos",
    "/cookies",
    "/compliance",
]
