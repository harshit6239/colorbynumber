"""
Backend Service — FastAPI application.

Provides an anonymous-session layer on top of the pipeline service.

Endpoints
---------
GET  /health              — liveness check (no auth)
POST /jobs                — create session if needed, rate-limit by IP,
                            proxy job to pipeline; returns { jobId }
                            + X-Session-Token response header
GET  /jobs/{job_id}       — validate session ownership, proxy poll to pipeline

Session model
-------------
Sessions are anonymous JWTs (HS256) stored client-side.
Payload: { "session_id": "<uuid>", "exp": <unix timestamp> }
The backend keeps an in-memory mapping of session_id → set[job_id] to
enforce ownership checks.  All state is ephemeral (no DB).

Rate limiting
-------------
Per-IP sliding window: RATE_LIMIT_JOBS requests per RATE_LIMIT_WINDOW_SECONDS.
Counters are in-memory and reset on server restart.
"""

import os
import uuid
from collections import defaultdict
from time import time

import httpx
import jwt
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Configuration (env vars with defaults)
# ---------------------------------------------------------------------------
PIPELINE_URL: str = os.environ["PIPELINE_URL"].rstrip("/")        # required
PIPELINE_API_KEY: str = os.environ["PIPELINE_API_KEY"]            # required
JWT_SECRET: str = os.environ["JWT_SECRET"]                        # required
JWT_ALGORITHM = "HS256"
SESSION_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", "1800"))  # 30 min
RATE_LIMIT_JOBS: int = int(os.getenv("RATE_LIMIT_JOBS", "5"))
RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "600"))  # 10 min

# ---------------------------------------------------------------------------
# In-memory state  (ephemeral — resets on restart)
# ---------------------------------------------------------------------------
# session_jobs[session_id] -> set of job_ids owned by that session
session_jobs: dict[str, set[str]] = defaultdict(set)
# ip_timestamps[ip] -> list of submission unix timestamps (sliding window)
ip_timestamps: dict[str, list[float]] = defaultdict(list)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Color-by-Number Backend")

# Allow all origins in development; tighten ALLOW_ORIGINS in production.
_ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOW_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["X-Session-Token"],  # required so JS can read the token
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _client_ip(request: Request) -> str:
    """Return the real client IP, honouring X-Forwarded-For from Render's proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host  # type: ignore[union-attr]


def _create_session_token(session_id: str) -> str:
    payload = {
        "session_id": session_id,
        "exp": int(time()) + SESSION_TTL_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_session_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session token.")


def _check_and_record_rate_limit(ip: str) -> None:
    """Raise 429 if the IP has hit the rate limit; otherwise record this request."""
    now = time()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    # Prune timestamps outside the window
    ip_timestamps[ip] = [t for t in ip_timestamps[ip] if t > cutoff]
    if len(ip_timestamps[ip]) >= RATE_LIMIT_JOBS:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded. Max {RATE_LIMIT_JOBS} jobs per "
                f"{RATE_LIMIT_WINDOW_SECONDS // 60} minutes."
            ),
        )
    ip_timestamps[ip].append(now)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
@app.head("/health")
def health():
    return {"status": "ok"}


@app.post("/jobs", status_code=202)
async def submit_job(
    request: Request,
    image: UploadFile = File(...),
    k: int = Form(default=12, ge=2, le=15),
    smooth_sigma: float = Form(default=3.0, ge=0.0, le=10.0),
    quality: str = Form(default="fast"),
    x_session_token: str | None = Header(default=None),
):
    # Resolve or create session
    if x_session_token:
        payload = _decode_session_token(x_session_token)
        session_id = payload["session_id"]
    else:
        session_id = str(uuid.uuid4())

    # Rate-limit by IP (raises 429 if exceeded, records the request if ok)
    _check_and_record_rate_limit(_client_ip(request))

    # Read image bytes before forwarding
    image_bytes = await image.read()

    # Forward to pipeline
    async with httpx.AsyncClient() as pipeline_client:
        try:
            resp = await pipeline_client.post(
                f"{PIPELINE_URL}/jobs",
                headers={"X-API-Key": PIPELINE_API_KEY},
                files={"image": (image.filename or "image", image_bytes, image.content_type)},
                data={
                    "k": str(k),
                    "smooth_sigma": str(smooth_sigma),
                    "quality": quality,
                },
                timeout=30.0,
            )
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Pipeline unreachable: {exc}")

    if resp.status_code != 202:
        detail = resp.json().get("detail", "Pipeline error.") if resp.content else "Pipeline error."
        raise HTTPException(status_code=resp.status_code, detail=detail)

    job_id = resp.json()["jobId"]

    # Register job under this session
    session_jobs[session_id].add(job_id)

    # Return 202 with refreshed session token
    response = JSONResponse(status_code=202, content={"jobId": job_id})
    response.headers["X-Session-Token"] = _create_session_token(session_id)
    return response


@app.get("/jobs/{job_id}")
async def poll_job(
    job_id: str,
    x_session_token: str | None = Header(default=None),
):
    if not x_session_token:
        raise HTTPException(status_code=401, detail="Missing session token.")

    payload = _decode_session_token(x_session_token)
    session_id = payload["session_id"]

    # Ownership check
    if job_id not in session_jobs.get(session_id, set()):
        raise HTTPException(status_code=403, detail="Job does not belong to this session.")

    # Proxy poll to pipeline
    async with httpx.AsyncClient() as pipeline_client:
        try:
            resp = await pipeline_client.get(
                f"{PIPELINE_URL}/jobs/{job_id}",
                headers={"X-API-Key": PIPELINE_API_KEY},
                timeout=10.0,
            )
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Pipeline unreachable: {exc}")

    return JSONResponse(status_code=resp.status_code, content=resp.json())
