# Automated llms.txt Generator

Generate spec-compliant [llms.txt](https://llmstxt.org) files from any website URL.

**Live app:** [https://llms-generator.up.railway.app/](https://llms-generator.up.railway.app/)

## Purpose

Take-home implementation built for **site owners and marketing teams** who want to understand and improve their site’s AI visibility — the problem Profound is solving. This app is one concrete piece: crawl a site, score AI readiness, and generate an llms.txt that helps models find the right pages. The live app above demos that flow end to end.

## Demo

Quick runthrough of the implementation with audio! 
https://drive.google.com/file/d/1hUvXgc3Udg_zZTgRAmAr_74mTuTpedmK/view?usp=sharing

## Usage

1. Enter any site URL on the homepage (e.g. `https://stripe.com`).
2. Watch generation progress: access check → discovering links → crawl → readiness analysis → generate.
3. Review the analysis page: AI readiness score, category breakdown, and the generated llms.txt.
4. Copy or download the file. Revisit past scans from the recent scans list on the homepage.

## Architecture

![System architecture](./docs/architecture.png)

The React frontend connects to the backend over **SSE** (`POST /generate/stream`), pushing stage updates and crawl counts to the UI in real time — no polling. The FastAPI backend crawls the site (with **429/timeout retry** on HTTP fetches), ranks pages with a deterministic importance score, sends the top tier to **Claude Haiku** for categorization, and persists results to SQLite. A background scheduler re-scans domains every 24 hours.

For pipeline design choices and tradeoffs, see the [Backend README](./backend/README.md). For UI components and data flow, see the [Frontend README](./frontend/README.md).

## Design Rationale

The [spec](https://llmstxt.org) defines llms.txt as a **curated index for on-demand lookup** — fetched at inference time when an agent needs to orient on a site, not a pretraining dump or sitemap replacement.

This pipeline matches that intent: deterministic page scoring → Claude Haiku section grouping → ~100 links max, with the rest intentionally omitted. More pages would mean a sitemap dump, which is exactly what llms.txt is not for.

**Completeness vs. speed:** return results quickly with a high-signal subset, not an exhaustive crawl. The crawler caps at 200 pages, seeds and fetches in importance order (sitemap priority, inbound links, path depth), and skips individual page failures rather than blocking the job. That tradeoff matches the spec — an orientation index for agents, not a full-site mirror. See [Priority Crawl](./backend/README.md#4-priority-crawl) in the backend README for the crawl budget and retry behavior.

**No JavaScript rendering (intentional):** the crawler uses plain HTTP fetches, not a headless browser. That is a deliberate tradeoff — spinning up a browser per page is far slower and more resource-intensive than `GET` + HTML parse, especially at a 200-page budget. Most production AI crawlers (GPTBot, ClaudeBot, PerplexityBot, etc.) work the same way today, so this pipeline reflects what those bots actually see, not what Chrome renders after JavaScript runs. Client-rendered SPAs may look empty or incomplete; the analysis page flags that case with a warning rather than hiding the gap.

`robots.txt` governs crawler access (can a bot visit at all), while `llms.txt` is a content guide for bots that are already allowed in. A site can have a perfect llms.txt but still be invisible to ChatGPT if GPTBot is blocked in robots.txt — these are complementary, not redundant, signals. The AI readiness score reflects both dimensions separately. See [AI Readiness Score](./backend/README.md#5-ai-readiness-score) in the backend README for the full scoring breakdown.

## Implementation

Output follows the required spec structure: **H1 title**, optional **blockquote summary**, then **H2 file lists** (plus an `## Optional` section when low-priority pages match).

The optional **narrative section** (freeform text between the blockquote and the H2 lists) is omitted on purpose. The one-line blockquote already orients the reader; a longer “how to interpret these files” paragraph would be either hardcoded boilerplate with little value, or another LLM call per generation — extra cost and latency for something that does not change which pages get surfaced or how accurate the file is.

## Known Limitations

- **200-page crawl cap** — large sites are only partially represented; pages are ranked by importance before selection.
- **No JavaScript rendering** — raw HTML only by design (see [Design Rationale](#design-rationale)); SPAs may return incomplete data. The analysis page warns when crawled pages have thin body text (word-count heuristic — see [backend README](./backend/README.md#5-ai-readiness-score)).
- **Large template-heavy sites** — marketplaces and similar sites can have thousands of near-duplicate SEO landing pages that dominate sitemaps and the crawl budget; output may include a few arbitrary listing pages rather than a curated subset.
- **Single-pass categorization** — Claude picks pages and invents section names in one call with no post-validation; listing pages that reach tier 1 may land in vague catch-all sections instead of being dropped or routed to Optional.
- **Claude improves section quality** — without an API key, a deterministic fallback still works but produces less nuanced groupings.

See [Known Limitations](./backend/README.md#known-limitations) in the backend README for additional edge cases.

## Future work

Potential next features to improve crawling results and llms.txt generation:

- **In-app llms.txt editor** — let users tweak sections and links after generation, then save back to the stored scan.
- **Smarter crawl selection** — template caps and URL-pattern deduping so marketplace/SEO landing pages don't dominate sitemaps and the crawl budget; section-aware BFS and better sitemap seeding (often better ROI than raising the 200-page cap).
- **Crawl tuning controls** — UI presets or sliders for crawl configuration (e.g. 300–500 page budget for large doc sites, lower concurrency, stricter depth) when breadth matters more than speed.
- **Categorization validation** — post-pass rules to drop or reroute listing-style pages to Optional instead of vague catch-all sections; refine or split the single-pass Claude call if section quality still lags.

## Project Layout

```
.
├── backend/     # FastAPI crawler + llms.txt generator
├── frontend/    # React + Vite UI
└── docs/        # Architecture diagram
```

## Quick Start

**Prerequisites:** Python 3, Node.js. `ANTHROPIC_API_KEY` is optional — fallback categorization works without it, but Claude produces better section groupings.

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8000
```

API runs at `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_URL defaults to http://localhost:8000
npm run dev
```

App runs at `http://localhost:5173`.

## Documentation

- [Backend README](./backend/README.md) — pipeline, design choices, API endpoints, database schema, configuration
- [Frontend README](./frontend/README.md) — components, data flow, environment variables
