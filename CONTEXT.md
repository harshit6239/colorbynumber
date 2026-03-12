# Project Context — Color by Number

> Load this file at the start of a new chat to resume where we left off.

---

## What this project is

A web app that converts any photo into a printable paint-by-number template.
It is a **monorepo** with three services:

| Service    | Tech             | Port (local) | Deploy target |
| ---------- | ---------------- | ------------ | ------------- |
| `pipeline` | Python / FastAPI | 8000         | Render        |
| `backend`  | Python / FastAPI | 8001         | Render        |
| `frontend` | React + Vite     | 5173         | Vercel        |

---

## Current status — everything is built and working

| Component                     | Status                          |
| ----------------------------- | ------------------------------- |
| Pipeline service              | ✅ complete + tested            |
| Backend service               | ✅ complete + tested            |
| Frontend (3 pages, dark mode) | ✅ complete, build passes       |
| README                        | ✅ up to date                   |
| `.env.example` files          | ✅ up to date                   |
| Deployment (Render + Vercel)  | ✅ documented, not yet deployed |

---

## Monorepo structure

```
colorbynumber/
├── main.py                         # CLI entry point (dev use)
├── pyproject.toml
├── README.md
├── CONTEXT.md                      # ← this file
├── .env.example                    # all 3 services' vars, clearly labelled
├── examples/
│   └── image.png
├── outputs/                        # CLI output (gitignored)
├── src/
│   └── pipeline_stages/            # core image-processing library
│       ├── preprocessing.py
│       ├── quantization.py
│       ├── segmentation.py
│       ├── outline.py
│       ├── outline_smoothing.py
│       ├── label_placement.py
│       ├── colored_preview.py
│       ├── palette_legend.py
│       └── cleanup.py
├── utils/
│   └── io.py
│
├── pipeline/                       # FastAPI image-processing worker
│   ├── app.py
│   ├── main.py                     # run_pipeline() — called by app.py
│   ├── pyproject.toml
│   ├── .env.example
│   └── tests/
│       └── test_app.py
│
├── backend/                        # FastAPI public-facing API
│   ├── app.py
│   ├── pyproject.toml
│   ├── .env.example
│   └── tests/
│       ├── conftest.py
│       ├── test_app.py
│       └── test_integration.py
│
└── frontend/                       # React + Vite SPA
    ├── index.html
    ├── vite.config.js              # dev proxy /jobs → :8001
    ├── vercel.json                 # SPA rewrite rule
    ├── .env.example
    ├── package.json                # React 18 + Vite 7 + react-router-dom
    └── src/
        ├── main.jsx
        ├── App.jsx                 # BrowserRouter: /, /generate, /support
        ├── App.css                 # design tokens (light+dark), all styles
        ├── api.js                  # fetch wrapper + JWT session management
        ├── components/
        │   └── Layout.jsx          # sticky nav + dark-mode toggle
        └── pages/
            ├── Home.jsx            # landing page (hero + 3 feature cards)
            ├── Generate.jsx        # upload → settings → spinner → results
            └── Support.jsx         # Buy Me a Coffee page
```

---

## Key design decisions

### Pipeline (`pipeline/app.py`)

- Auth: `X-API-Key` header checked against `PIPELINE_API_KEY` env var
- One `ThreadPoolExecutor` (size = `MAX_WORKERS`); returns 503 if busy
- Job results stored in an in-memory dict with TTL cleanup (background task)
- Validates: MIME type (jpeg/png/webp), file size ≤ `MAX_IMAGE_BYTES`, pixel dims `MIN_IMAGE_PX`–`MAX_IMAGE_PX`
- k range: 2–15 colors; smooth_sigma: 0–10; quality: `fast` (≤1000px) | `print` (≤2500px)
- `GET /health` + `HEAD /health` for Render keep-alive

### Backend (`backend/app.py`)

- Anonymous sessions: HS256 JWT with `{ session_id, exp }`, 30-min TTL
- Client sends `X-Session-Token` header; backend refreshes it on every successful `/jobs` POST
- In-memory `session_jobs[session_id] → set[job_id]` for ownership checks
- Rate limiting: **5 jobs per 10 minutes per IP** (sliding window, in-memory)
- CORS: `ALLOW_ORIGINS` env var (default `*`; restrict to Vercel domain in production)
- `PIPELINE_API_KEY` is never sent to the browser

### Frontend (`frontend/src/`)

- `api.js` stores the JWT in `localStorage` under `cbn_session_token` and attaches it to every request
- Polling interval: 2500 ms
- Dark mode: `data-theme` attribute on `<html>`, reads `prefers-color-scheme` on first visit, persists to `localStorage` as `cbn_dark`
- Vite dev proxy forwards `/jobs` and `/health` to `http://localhost:8001` — no `VITE_BACKEND_URL` needed locally

---

## Environment variables summary

### pipeline/.env

```env
PIPELINE_API_KEY=            # required — shared with backend
MAX_WORKERS=1
JOB_TTL_SECONDS=300
MAX_IMAGE_BYTES=10485760
MIN_IMAGE_PX=100
MAX_IMAGE_PX=8000
```

### backend/.env

```env
PIPELINE_URL=http://localhost:8000   # required
PIPELINE_API_KEY=                    # required — same value as pipeline's
JWT_SECRET=                          # required — different from API key
SESSION_TTL_SECONDS=1800
RATE_LIMIT_JOBS=5
RATE_LIMIT_WINDOW_SECONDS=600
ALLOW_ORIGINS=*
PORT=8001
```

### frontend/.env (only needed in production)

```env
VITE_BACKEND_URL=https://your-backend.onrender.com
```

---

## Running the full stack locally

```powershell
# Terminal 1 — pipeline
cd pipeline
$env:PIPELINE_API_KEY="test-key"
uv run uvicorn app:app --port 8000 --reload

# Terminal 2 — backend
cd backend
$env:PIPELINE_URL="http://localhost:8000"
$env:PIPELINE_API_KEY="test-key"
$env:JWT_SECRET="dev-secret"
uv run uvicorn app:app --port 8001 --reload

# Terminal 3 — frontend
cd frontend
npm run dev      # → http://localhost:5173
```

---

## Running tests

```powershell
# Pipeline tests
cd pipeline
$env:PIPELINE_API_KEY="test-key"
uv run pytest tests/ -v

# Backend unit tests
cd backend
$env:PIPELINE_API_KEY="fake-pipeline-key"
$env:PIPELINE_URL="http://fake-pipeline"
$env:JWT_SECRET="test-secret"
uv run pytest tests/test_app.py -v

# Backend integration tests (starts real pipeline subprocess)
uv run pytest tests/test_integration.py -v

# All backend tests
uv run pytest tests/ -v
```

---

## Deployment

### Render (pipeline + backend)

Both are **Render Web Services**:

| Setting        | Pipeline                                             | Backend                                              |
| -------------- | ---------------------------------------------------- | ---------------------------------------------------- |
| Root directory | `pipeline`                                           | `backend`                                            |
| Build command  | `uv sync`                                            | `uv sync`                                            |
| Start command  | `uv run uvicorn app:app --host 0.0.0.0 --port $PORT` | `uv run uvicorn app:app --host 0.0.0.0 --port $PORT` |

Pipeline env vars to set: `PIPELINE_API_KEY`  
Backend env vars to set: `PIPELINE_URL`, `PIPELINE_API_KEY`, `JWT_SECRET`, `ALLOW_ORIGINS`

### Vercel (frontend)

| Setting          | Value           |
| ---------------- | --------------- |
| Root directory   | `frontend`      |
| Build command    | `npm run build` |
| Output directory | `dist`          |

Env var to set: `VITE_BACKEND_URL` = deployed backend URL (no trailing slash)

---

## What's left / possible next steps

### Deployment

- [ ] **Deploy** — push to GitHub, connect Render + Vercel
- [ ] **Buy Me a Coffee link** — replace placeholder URL in `frontend/src/pages/Support.jsx` (two `href` values) with real BMC profile URL
- [ ] **ALLOW_ORIGINS** — after deploying frontend, set Vercel domain in backend's `ALLOW_ORIGINS` env var on Render

### UI / Frontend improvements

- [ ] **Loading progress** — show per-stage progress ("Quantizing…", "Smoothing edges…", "Placing labels…") instead of a generic spinner; requires pipeline to emit SSE or stage updates
- [ ] **Image zoom / pan** — add pinch-zoom or scroll-zoom on the result image so users can inspect numbered regions closely
- [ ] **Settings preview** — show a live thumbnail or color-count badge that updates as the k slider moves
- [ ] **Error recovery UX** — on 503 (pipeline busy) auto-retry with backoff + a visible queue-position message
- [ ] **Mobile nav** — collapse nav links into a hamburger menu on small screens
- [ ] **Animations** — subtle fade/slide transitions between pages (using CSS `View Transitions API` or Framer Motion)
- [ ] **Result share button** — copy a shareable link or download all three outputs as a ZIP
- [ ] **Home page examples** — add a before/after image carousel showing real pipeline output to build trust

### Feature additions

- [ ] SVG export of the template (scalable for large prints)
- [ ] Custom palette — let user pick colors manually instead of auto-quantizing
- [ ] Printable PDF output (template + palette on one page)
- [ ] Batch processing (multiple images in one session)
