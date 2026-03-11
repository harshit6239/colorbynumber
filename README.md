# Color by Number

Convert any photo into a paint-by-number template with numbered regions, a palette legend, and a colored preview.

## Architecture

```
colorbynumber/
├── pipeline/       # Image processing service (FastAPI, port 8000)
├── backend/        # Public API + session/rate-limit layer (FastAPI, port 8001)
├── frontend/       # React + Vite SPA (port 5173) — deploys to Vercel
├── src/            # Core processing library (used by pipeline)
├── utils/
└── main.py         # CLI entry point (dev / local use)
```

### Request flow

```
Browser
  │
  ▼
backend  (public-facing, Render)
  │  anonymous JWT session  ·  IP rate limiting
  │  hides PIPELINE_API_KEY
  ▼
pipeline  (internal, Render)
  │  image validation  ·  job queue  ·  TTL cleanup
  ▼
run_pipeline()  →  template · palette · colored_preview  (base64)
```

---

## Components

### pipeline/

Image processing worker. Accepts multipart form uploads, runs the color-quantisation pipeline in a thread pool, and exposes job status via polling.

**Key env vars**

| Variable           | Default    | Notes                                                          |
| ------------------ | ---------- | -------------------------------------------------------------- |
| `PIPELINE_API_KEY` | —          | **Required.** Shared secret; set in both pipeline and backend. |
| `MAX_WORKERS`      | `1`        | Thread pool size (concurrent jobs).                            |
| `JOB_TTL_SECONDS`  | `300`      | How long completed jobs are kept in memory.                    |
| `MAX_IMAGE_BYTES`  | `10485760` | Upload size cap (10 MB).                                       |
| `MIN_IMAGE_PX`     | `100`      | Minimum image dimension in pixels.                             |
| `MAX_IMAGE_PX`     | `8000`     | Maximum image dimension in pixels.                             |

**Endpoints**

| Method       | Path             | Auth        | Description                                            |
| ------------ | ---------------- | ----------- | ------------------------------------------------------ |
| `GET / HEAD` | `/health`        | none        | Liveness check — used by Render keep-alive.            |
| `POST`       | `/jobs`          | `X-API-Key` | Submit image. Returns `{ "jobId": "…" }` (HTTP 202).   |
| `GET`        | `/jobs/{job_id}` | `X-API-Key` | Poll status. Returns `processing` / `done` / `failed`. |

**Job form params**

| Field          | Type  | Range             | Default |
| -------------- | ----- | ----------------- | ------- |
| `image`        | file  | jpeg · png · webp | —       |
| `k`            | int   | 2 – 15            | `12`    |
| `smooth_sigma` | float | 0.0 – 10.0        | `3.0`   |
| `quality`      | str   | `fast` · `print`  | `fast`  |

**Done response payload**

```json
{
    "status": "done",
    "result": {
        "template": "<base64 PNG>",
        "palette": "<base64 PNG>",
        "colored_preview": "<base64 PNG>"
    }
}
```

---

### backend/

Public-facing API. Issues anonymous JWT sessions, enforces per-IP rate limiting, and proxies requests to the pipeline. The `PIPELINE_API_KEY` is never exposed to the browser.

**Key env vars**

| Variable                    | Default | Notes                                                                                                                      |
| --------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------- |
| `PIPELINE_URL`              | —       | **Required.** Base URL of the pipeline service.                                                                            |
| `PIPELINE_API_KEY`          | —       | **Required.** Must match the pipeline's key.                                                                               |
| `JWT_SECRET`                | —       | **Required.** ≥ 32 random bytes recommended.                                                                               |
| `SESSION_TTL_SECONDS`       | `1800`  | Session token lifetime (30 min).                                                                                           |
| `RATE_LIMIT_JOBS`           | `3`     | Max job submissions per IP per window.                                                                                     |
| `RATE_LIMIT_WINDOW_SECONDS` | `600`   | Sliding rate-limit window (10 min).                                                                                        |
| `ALLOW_ORIGINS`             | `*`     | Comma-separated allowed CORS origins, e.g. `https://myapp.vercel.app`. Defaults to `*` (all) — **restrict in production**. |

**Endpoints**

| Method       | Path             | Auth                                              | Description                                                           |
| ------------ | ---------------- | ------------------------------------------------- | --------------------------------------------------------------------- |
| `GET / HEAD` | `/health`        | none                                              | Liveness check.                                                       |
| `POST`       | `/jobs`          | `X-Session-Token` header (optional on first call) | Submit job. Returns `{ "jobId": "…" }` + refreshed `X-Session-Token`. |
| `GET`        | `/jobs/{job_id}` | `X-Session-Token` header                          | Poll job — only owner session allowed (403 otherwise).                |

**Session flow**

1. First request: no token → backend mints a new JWT and returns it in the `X-Session-Token` response header.
2. Subsequent requests: client sends the token in `X-Session-Token`; backend decodes it to resolve the session.
3. Token is refreshed (new exp) on every successful submission.
4. Session state (`session_id → job_ids`) is in-memory and ephemeral.

---

## Development setup

Requires [uv](https://docs.astral.sh/uv/) and **Python 3.11**.

### Pipeline

```powershell
cd pipeline
uv sync

# Run dev server
$env:PIPELINE_API_KEY="dev-key"
uv run uvicorn app:app --reload --port 8000

# Run unit tests
$env:PIPELINE_API_KEY="test-key"
uv run pytest tests/ -v
```

### Backend

```powershell
cd backend
uv sync

# Run dev server (pipeline must already be running on 8000)
$env:PIPELINE_URL="http://localhost:8000"
$env:PIPELINE_API_KEY="dev-key"
$env:JWT_SECRET="change-me-to-32-plus-random-bytes"
uv run uvicorn app:app --reload --port 8001

# Run unit tests (no pipeline needed — uses mocks)
uv run pytest tests/test_app.py -v

# Run integration tests (starts real pipeline subprocess automatically)
uv run pytest tests/test_integration.py -v

# Run all tests
uv run pytest tests/ -v
```

### Frontend

```powershell
cd frontend
npm install

# Run dev server (proxies API calls to backend on :8001 automatically)
npm run dev        # http://localhost:5173

# Production build
npm run build
```

**Env var**

| Variable           | Notes                                                                                             |
| ------------------ | ------------------------------------------------------------------------------------------------- |
| `VITE_BACKEND_URL` | Full URL of the deployed backend (no trailing slash). Omit for local dev — Vite proxy handles it. |

---

### CLI (dev / local)

```powershell
# From repo root
uv run python main.py examples/image.png --k 12
```

Output files are written to `outputs/`.

---

## Running both services locally

```powershell
# Terminal 1 — pipeline
cd a:\CODE\colorbynumber\pipeline
$env:PIPELINE_API_KEY="dev-key"
uv run uvicorn app:app --port 8000

# Terminal 2 — backend
cd a:\CODE\colorbynumber\backend
$env:PIPELINE_URL="http://localhost:8000"
$env:PIPELINE_API_KEY="dev-key"
$env:JWT_SECRET="change-me-to-32-plus-random-bytes"
uv run uvicorn app:app --port 8001

# Terminal 3 — frontend
cd a:\CODE\colorbynumber\frontend
npm run dev        # http://localhost:5173
```

The Vite dev server automatically proxies `/jobs` and `/health` to `http://localhost:8001` (backend).  
To override (e.g. point at a deployed backend), set `VITE_BACKEND_URL` in `frontend/.env`.

---

## Deployment (Render)

Both services deploy as **Render Web Services** (free tier).

### pipeline (internal service)

| Setting        | Value                                                |
| -------------- | ---------------------------------------------------- |
| Root directory | `pipeline`                                           |
| Build command  | `uv sync`                                            |
| Start command  | `uv run uvicorn app:app --host 0.0.0.0 --port $PORT` |
| Instance type  | Free                                                 |

**Env vars to set in Render dashboard**

- `PIPELINE_API_KEY` — strong random secret shared with backend

Optional overrides: `MAX_WORKERS`, `JOB_TTL_SECONDS`, `MAX_IMAGE_BYTES`, `MIN_IMAGE_PX`, `MAX_IMAGE_PX`.

### backend (public service)

| Setting        | Value                                                |
| -------------- | ---------------------------------------------------- |
| Root directory | `backend`                                            |
| Build command  | `uv sync`                                            |
| Start command  | `uv run uvicorn app:app --host 0.0.0.0 --port $PORT` |
| Instance type  | Free                                                 |

**Env vars to set in Render dashboard**

- `PIPELINE_URL` — internal URL of the pipeline service
- `PIPELINE_API_KEY` — must match pipeline's value
- `JWT_SECRET` — ≥ 32 bytes, e.g. `openssl rand -hex 32`

Optional overrides: `SESSION_TTL_SECONDS`, `RATE_LIMIT_JOBS`, `RATE_LIMIT_WINDOW_SECONDS`.

> **Tip:** On Render free tier, services spin down after inactivity. Configure a cron monitor to `GET /health` every 10 minutes to keep the pipeline warm if needed.

### frontend (Vercel)

Connect the repo to Vercel and set the following:

| Setting          | Value           |
| ---------------- | --------------- |
| Root directory   | `frontend`      |
| Build command    | `npm run build` |
| Output directory | `dist`          |
| Install command  | `npm install`   |

**Env var to set in Vercel dashboard**

- `VITE_BACKEND_URL` — full URL of your deployed backend, e.g. `https://colorbynumber-backend.onrender.com`

Also set `ALLOW_ORIGINS` in the **backend** Render service to your Vercel domain, e.g. `https://colorbynumber.vercel.app`.

---

## Project structure (full)

```
colorbynumber/
├── main.py                         # CLI entry point
├── pyproject.toml                  # Root project (CLI deps)
├── README.md
├── .env.example                    # All service env vars, clearly labelled
├── examples/
│   └── image.png
├── outputs/                        # CLI output files (gitignored)
├── src/
│   └── pipeline_stages/            # Core image processing modules
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
├── pipeline/                       # Pipeline service  (port 8000)
│   ├── app.py                      # FastAPI app
│   ├── main.py                     # run_pipeline() entry point
│   ├── pyproject.toml
│   ├── .env.example
│   └── tests/
│       └── test_app.py             # 25 unit tests
├── backend/                        # Backend service  (port 8001)
│   ├── app.py                      # FastAPI app
│   ├── pyproject.toml
│   ├── .env.example
│   └── tests/
│       ├── conftest.py
│       ├── test_app.py             # unit tests (mocked pipeline)
│       └── test_integration.py     # integration tests (real pipeline subprocess)
└── frontend/                       # React + Vite SPA  (port 5173)
    ├── index.html
    ├── vite.config.js              # dev proxy → :8001
    ├── vercel.json                 # SPA rewrite rule
    ├── .env.example
    ├── package.json
    └── src/
        ├── main.jsx
        ├── App.jsx                 # Router (/, /generate, /support)
        ├── App.css                 # All styles + dark mode tokens
        ├── api.js                  # fetch wrapper + session token mgmt
        ├── components/
        │   └── Layout.jsx          # Sticky nav + dark-mode toggle
        └── pages/
            ├── Home.jsx            # Landing page
            ├── Generate.jsx        # Upload → settings → results
            └── Support.jsx         # Buy Me a Coffee page
```
