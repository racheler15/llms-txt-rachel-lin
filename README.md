# llms.txt Generator

Generate spec-compliant [llms.txt](https://llmstxt.org) files from any website URL.

**Live app:** [https://llms-generator.up.railway.app/](https://llms-generator.up.railway.app/)

## Purpose

Take-home implementation built for **site owners and marketing teams** who want to understand and improve their site’s AI visibility — the problem Profound is solving. This app is one concrete piece: crawl a site, score AI readiness, and generate an llms.txt that helps models find the right pages. The live app above demos that flow end to end.

## Usage

1. Enter any site URL on the homepage (e.g. `https://stripe.com`).
2. Watch generation progress: access check → sitemap discovery → crawl → readiness analysis → generate.
3. Review the analysis page: AI readiness score, category breakdown, and the generated llms.txt.
4. Copy or download the file. Revisit past scans from the recent scans list on the homepage.

## Architecture

![System architecture](./docs/architecture.png)

The React frontend connects to the backend over **SSE** (`POST /generate/stream`), pushing stage updates and crawl counts to the UI in real time — no polling. The FastAPI backend crawls the site (with **429/timeout retry** on HTTP fetches), ranks pages with a deterministic importance score, sends the top tier to **Claude Haiku** for categorization, and persists results to SQLite. A background scheduler re-scans domains every 24 hours.

For pipeline design choices and tradeoffs, see the [Backend README](./backend/README.md). For UI components and data flow, see the [Frontend README](./frontend/README.md).

## Design rationale

The [spec](https://llmstxt.org) defines llms.txt as a **curated index for on-demand lookup** — fetched at inference time when an agent needs to orient on a site, not a pretraining dump or sitemap replacement.

This pipeline matches that intent: deterministic page scoring → Claude Haiku section grouping → ~100 links max, with the rest intentionally omitted. More pages would mean a sitemap dump, which is exactly what llms.txt is not for.

## Implementation

Output follows the required spec structure: **H1 title**, optional **blockquote summary**, then **H2 file lists** (plus an `## Optional` section when low-priority pages match).

The optional **narrative section** (freeform text between the blockquote and the H2 lists) is omitted on purpose. The one-line blockquote already orients the reader; a longer “how to interpret these files” paragraph would be either hardcoded boilerplate with little value, or another LLM call per generation — extra cost and latency for something that does not change which pages get surfaced or how accurate the file is.

## Known limitations

- **200-page crawl cap** — large sites are only partially represented; pages are ranked by importance before selection.
- **No JavaScript rendering** — the crawler reads raw HTML only; SPAs and client-rendered content may return incomplete data.
- **Claude improves section quality** — without an API key, a deterministic fallback still works but produces less nuanced groupings.

See [Known Limitations](./backend/README.md#known-limitations) in the backend README for additional edge cases.

## Project Structure

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
