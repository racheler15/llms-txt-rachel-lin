# Automated llms.txt Generator — Frontend

React UI for generating spec-compliant [llms.txt](https://llmstxt.org) files from any website URL.

## Contents

- [Stack](#stack)
- [Screenshots](#screenshots)
- [Routes](#routes)
- [Components](#components)
- [Data Flow](#data-flow)
- [Error cases](#error-cases)
- [Scheduled rescans](#scheduled-rescans)
- [Project Layout](#project-layout)
- [Known Limitations](#known-limitations)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Scripts](#scripts)

## Stack

- React 19, TypeScript, Vite
- React Router — client-side routing
- TanStack React Query — API requests and loading/error state
- Carbon Icons — UI icons

## Screenshots
### Home Page
<img width="800" alt="image" src="https://github.com/user-attachments/assets/757d868a-c2b0-47b0-bcd8-be9ac49a9c9b" />

### Analysis Page
<img width="800" alt="Analysis overview and readiness score" src="https://github.com/user-attachments/assets/b6c86616-10c9-4ee6-89b8-eee4ca25a8a2" />

<img width="800" alt="Categories breakdown" src="https://github.com/user-attachments/assets/1a23dfcc-5ac6-41fd-9279-016f003d9de1" />

<img width="800" alt="Generated llms.txt output" src="https://github.com/user-attachments/assets/15e32573-41a1-4521-9932-55043d60d3d0" />

## Routes

| Route | Page | Description |
|-------|------|-------------|
| `/` | Home | URL input form and recent scans |
| `/analysis/:domain` | Analysis | Readiness score, category breakdown, llms.txt output |

## Components

| Component | Path | Role |
|-----------|------|------|
| `GeneratorForm` | `components/homepage/generator-form/` | URL input, submit, error display; triggers generation |
| `GenerationSteps` | `components/homepage/generator-form/` | Live step checklist during SSE progress |
| `RecentScans` | `components/homepage/recent-scans/` | Lists persisted scans from `GET /scans`; shows **Updated** badge when `has_unviewed_changes` is true |
| `AnalysisOverview` + `StatCards` | `components/analysis/analysis-overview/` | Domain header, page counts, readiness summary, rescan action |
| `CrawlWarning` | `components/analysis/crawl-warning/` | Warns when `readiness.js_rendering_likely` is true — see [Known Limitations](#known-limitations) |
| `ReadinessScore` | `components/analysis/readiness-score/` | Category score bars and recommendations |
| `CategoriesBreakdown` | `components/analysis/categories-breakdown/` | Expandable llms.txt section/page list |
| `GeneratedOutput` | `components/analysis/generated-output/` | Preview, copy, and download llms.txt |

## Data Flow

1. User submits a URL in `GeneratorForm`.
2. `useGenerate` POSTs to `/generate/stream` and parses SSE events via `readSseStream`.
3. Progress events update `GenerationSteps` (`checking_access` → `discovering_pages` → `crawling` → `analyzing_readiness` → `generating`).
4. On `complete`, the response is mapped to `AnalysisData`, seeded into the React Query cache, and the app navigates to `/analysis/:domain`.
5. `Analysis` loads scan data with `useScan`, calls `useMarkViewed` on mount, and renders the overview, optional `CrawlWarning` (when JS-heavy crawl is detected), readiness, categories, and output panels.
6. User can rescan from the analysis page via `useRecrawl`.
7. Opening an analysis page calls `useMarkViewed`, which clears the **Updated** badge on the homepage.

Key files: `hooks/useGenerate.ts`, `lib/readSseStream.ts`, `types/generation.ts`, `types/analysis.ts`.

## Error cases

`GeneratorForm` surfaces errors inline below the URL input. Common cases:

- **Invalid URL** — client-side validation and `422` responses show: *"Please enter a valid URL starting with http:// or https://"*
- 
<img width="800" alt="Invalid URL error on homepage" src="https://github.com/user-attachments/assets/2690d734-ac40-405c-a738-6d25e0c46f0d" />

- **robots.txt blocked** — during the `checking_access` stage, the backend returns `robots_blocked` and the UI shows: *"This site's robots.txt blocks automated crawlers."*
  
<img width="800" alt="robots.txt blocked error on homepage" src="https://github.com/user-attachments/assets/5a96fd30-30c6-4b86-90af-42c9b10a3f80" />

Other backend error types (`timeout`, `no_pages`) follow the same pattern via `parseApiError` in `types/errors.ts`. See [backend README](../backend/README.md) for when each is raised.

## Scheduled rescans

The backend runs a background scheduler (default: every **24 hours**, checked every 15 minutes) that automatically re-crawls saved domains. When page URLs or content hashes differ from the last llms.txt generation baseline, the scheduler:

1. Auto-regenerates llms.txt (if one already existed)
2. Sets `has_unviewed_changes` on the domain

`RecentScans` reads that flag and shows the **Updated** badge next to the domain on the homepage. The badge clears when the user opens the analysis page (`POST /scans/{domain}/mark-viewed`).

Manual **Rescan** on the analysis page re-crawls on demand but does **not** set the badge — only the scheduler does. See [backend README §11](../backend/README.md#11-rescan--change-detection) for the full flow.

<img width="800" alt="Updated badge on a recent scan after scheduled rescan" src="https://github.com/user-attachments/assets/e626e43c-f641-4c82-90be-ce191a6b7bb7" />


## Project Layout

```
src/
├── App.tsx
├── pages/
│   ├── Homepage.tsx
│   └── AnalysisPage.tsx
├── components/
│   ├── navbar/
│   ├── homepage/
│   │   ├── generator-form/
│   │   └── recent-scans/
│   └── analysis/
│       ├── analysis-overview/
│       ├── crawl-warning/
│       ├── categories-breakdown/
│       ├── generated-output/
│       └── readiness-score/
├── hooks/
│   ├── useGenerate.ts    # POST /generate/stream (SSE)
│   ├── useScan.ts        # GET /scans/{domain}
│   ├── useRecentScans.ts # GET /scans
│   ├── useRecrawl.ts     # POST /scans/{domain}/recrawl
│   ├── useMarkViewed.ts  # POST /scans/{domain}/mark-viewed
│   └── useDownload.ts
├── lib/
│   └── readSseStream.ts  # SSE frame parser
└── types/
    ├── analysis.ts       # API response mappers
    └── generation.ts     # Progress step IDs
```

## Known Limitations

- **No JavaScript rendering** — the crawler reads raw HTML only. When the backend sets `readiness.js_rendering_likely`, the analysis page shows a `CrawlWarning` banner (e.g. on JS-heavy sites like Notion):
  
<img width="800" alt="JavaScript crawl warning on notion.so" src="https://github.com/user-attachments/assets/8078af58-198e-4c30-8b3f-f0c6cbc093c5" />

See [backend README](../backend/README.md#5-ai-readiness-score) for detection heuristics. Other crawl and generation limits are documented in the [root README](../README.md#known-limitations) and [backend README](../backend/README.md#known-limitations).

## Getting Started

```bash
npm install
cp .env.example .env
npm run dev
```

Dev server: `http://localhost:5173`

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_URL` | Backend API base URL | `http://localhost:8000` |

Copy `.env.example` to `.env` before running locally. Do not commit `.env`.

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start dev server |
| `npm run build` | Type-check and build for production |
| `npm run preview` | Preview production build |
| `npm run lint` | Run ESLint |
