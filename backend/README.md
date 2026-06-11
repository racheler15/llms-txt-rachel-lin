# Backend — llms.txt Generator

FastAPI backend that crawls a website and generates a spec-compliant [llms.txt](https://llmstxt.org) file.

## How It Works

The crawler normalizes any input URL to the site root before crawling (e.g. `https://stripe.com/pricing` → `https://stripe.com`). This ensures the generated llms.txt reflects the entire site rather than a single section. The homepage is the highest-signal starting point — nav links from the root point to every major section, which feeds the page importance scorer.

If a `sitemap.xml` exists it's used as the primary URL source; otherwise the crawler falls back to BFS from the homepage.

### Crawl Strategy

1. **Normalize** the input URL to a root origin (`scheme://hostname`).
2. **Attempt to fetch `/sitemap.xml`** — if found, seed the crawl queue with its `<loc>` entries.
3. **Fall back to BFS** from the homepage if no sitemap is available, following internal links up to `MAX_DEPTH` (default 3).
4. For each page, extract **title**, **meta description**, **h1**, and a **content hash** for dedup.
5. Stop after `MAX_PAGES` (default 50) pages.

### Deduplication

- **URL dedup:** URLs are normalized (lowercased host, stripped trailing slashes, removed UTM params) and hashed to avoid revisiting the same page via different links.
- **Content dedup:** Page body text is hashed so duplicate content served at different URLs can be detected downstream.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Running

```bash
uvicorn main:app --reload --port 8000
```

API runs at `http://localhost:8000`.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | API key for AI-assisted page categorization |

Copy `.env.example` to `.env` before running locally. Do not commit `.env`.

## API

### `POST /generate`

Crawl a website and return a generated llms.txt file. Used by the frontend.

**Request body:**

```json
{
  "url": "https://example.com"
}
```

**Response:**

```json
{
  "llms_txt": "# Example\n\n> An example website.\n\n..."
}
```

**Errors:**

| Status | Detail |
|--------|--------|
| 400 | Invalid URL. Must be a valid http or https URL. |
| 404 | No pages could be crawled from this site. |

### `POST /crawl`

Crawl a website and return extracted page metadata.

**Request body:**

```json
{
  "url": "https://example.com"
}
```

**Response:** array of `Page` objects:

```json
[
  {
    "url": "https://example.com",
    "title": "Example Domain",
    "description": "An example website.",
    "h1": "Example Domain",
    "depth": 0,
    "content_hash": "a1b2c3..."
  }
]
```

## Configuration

Constants in `crawler.py`:

| Constant | Default | Description |
|----------|---------|-------------|
| `MAX_DEPTH` | 3 | Maximum BFS link-follow depth |
| `MAX_PAGES` | 50 | Maximum number of pages to crawl |
| `REQUEST_DELAY` | 0.5s | Delay between requests (politeness) |
| `TIMEOUT` | 10s | HTTP request timeout |

## Known Limitations

- **Subdomain content is not crawled.** Sites that host documentation on a subdomain (e.g. `docs.stripe.com`) will not have that content included. The crawler only follows links on the same hostname as the input URL. Common doc paths like `/docs` and `/api` are probed on the root domain automatically.
- **Page budget is fixed at 50.** Large sites with thousands of pages will only have a subset represented. Pages are prioritized by crawl depth (shallower = more important).
- **JavaScript-rendered content is not supported.** The crawler fetches raw HTML only. Single-page apps or sites that load content dynamically via JavaScript will return empty or incomplete data.
