# llms.txt Generator — Frontend

React UI for generating spec-compliant [llms.txt](https://llmstxt.org) files from any website URL.

## Stack

- React 19, TypeScript, Vite
- React Router — client-side routing
- TanStack React Query — API requests and loading/error state
- Carbon Icons — UI icons

## Screenshots
### Home page
<img width="800" alt="image" src="https://github.com/user-attachments/assets/757d868a-c2b0-47b0-bcd8-be9ac49a9c9b" />

### Analysis page
<img width="320" alt="image" src="https://github.com/user-attachments/assets/b6c86616-10c9-4ee6-89b8-eee4ca25a8a2" />
<img width="320" alt="image" src="https://github.com/user-attachments/assets/1a23dfcc-5ac6-41fd-9279-016f003d9de1" />
<img width="320" alt="image" src="https://github.com/user-attachments/assets/15e32573-41a1-4521-9932-55043d60d3d0" />

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
| `RecentScans` | `components/homepage/recent-scans/` | Lists persisted scans from `GET /scans`; links to analysis |
| `AnalysisOverview` + `StatCards` | `components/analysis/analysis-overview/` | Domain header, page counts, readiness summary, rescan action |
| `ReadinessScore` | `components/analysis/readiness-score/` | Category score bars and recommendations |
| `CategoriesBreakdown` | `components/analysis/categories-breakdown/` | Expandable llms.txt section/page list |
| `GeneratedOutput` | `components/analysis/generated-output/` | Preview, copy, and download llms.txt |

## Data Flow

1. User submits a URL in `GeneratorForm`.
2. `useGenerate` POSTs to `/generate/stream` and parses SSE events via `readSseStream`.
3. Progress events update `GenerationSteps` (`checking_access` → `discovering_pages` → `crawling` → `analyzing_readiness` → `generating`).
4. On `complete`, the response is mapped to `AnalysisData`, seeded into the React Query cache, and the app navigates to `/analysis/:domain`.
5. `Analysis` loads scan data with `useScan`, calls `useMarkViewed` on mount, and renders the overview, readiness, categories, and output panels.
6. User can rescan from the analysis page via `useRecrawl`.

Key files: `hooks/useGenerate.ts`, `lib/readSseStream.ts`, `types/generation.ts`, `types/analysis.ts`.

## Project Structure

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
