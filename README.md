# llms.txt Generator

Generate spec-compliant [llms.txt](https://llmstxt.org) files from any website URL.

The backend crawls a site, extracts page metadata, and builds a structured llms.txt file. The frontend provides a simple UI to submit a URL and view, copy, or download the result.

## Project Structure

```
.
├── backend/     # FastAPI crawler + llms.txt generator
└── frontend/    # React + Vite UI
```

## Quick Start

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
cp .env.example .env
npm run dev
```

App runs at `http://localhost:5173`.

## Documentation

- [Backend README](./backend/README.md) — crawl strategy, API endpoints, configuration
- [Frontend README](./frontend/README.md) — stack, routes, environment variables
