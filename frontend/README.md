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
| `/` | Home | URL input form |
| `/analysis` | Analysis | Generated llms.txt output (copy/download) |

## Project Structure

```
src/
├── App.tsx              # Router + layout (navbar)
├── pages/
│   ├── HomePage.tsx
│   └── AnalysisPage.tsx
├── components/
│   ├── navbar/
│   ├── generator-form/
│   └── generated-output/
└── hooks/
    ├── useGenerate.ts   # POST /generate
    └── useDownload.ts   # Download llms.txt file
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
