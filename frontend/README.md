# llms.txt Generator — Frontend

React UI for generating spec-compliant [llms.txt](https://llmstxt.org) files from any website URL.

## Stack

- React 19, TypeScript, Vite
- React Router — client-side routing
- TanStack React Query — API requests and loading/error state
- Carbon Icons — UI icons

## Routes

| Route | Page | Description |
|-------|------|-------------|
| `/` | Home | URL input form and recent scans |
| `/analysis/:domain` | Analysis | Readiness score, category breakdown, llms.txt output |

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
│   ├── useGenerate.ts    # POST /generate
│   ├── useScan.ts        # GET /scans/{domain}
│   ├── useRecentScans.ts # GET /scans
│   ├── useRecrawl.ts     # POST /scans/{domain}/recrawl
│   ├── useMarkViewed.ts  # POST /scans/{domain}/mark-viewed
│   └── useDownload.ts
└── types/
    └── analysis.ts       # API response mappers
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
