"""
Pipeline Service — FastAPI application.

Endpoints
---------
GET  /health              — liveness check (no auth)
POST /jobs                — submit image + params, returns { jobId }
GET  /jobs/{job_id}       — poll job status / retrieve result
"""

import asyncio
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from time import time
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, Security, UploadFile
from fastapi.security.api_key import APIKeyHeader

from main import run_pipeline

# ---------------------------------------------------------------------------
# Configuration (env vars with defaults)
# ---------------------------------------------------------------------------
PIPELINE_API_KEY: str = os.environ["PIPELINE_API_KEY"]  # required — fail fast
MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", "1"))
JOB_TTL_SECONDS: int = int(os.getenv("JOB_TTL_SECONDS", "300"))
MAX_IMAGE_BYTES: int = int(os.getenv("MAX_IMAGE_BYTES", str(10 * 1024 * 1024)))

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}

# ---------------------------------------------------------------------------
# In-memory job store
# ---------------------------------------------------------------------------
# job_store[job_id] = {
#   "status": "processing" | "done" | "failed",
#   "result": { "template": b64, "palette": b64, "colored_preview": b64 } | None,
#   "error":  str | None,
#   "created_at": float (unix timestamp),
# }
job_store: dict[str, dict] = {}
_executor: ThreadPoolExecutor | None = None


# ---------------------------------------------------------------------------
# Lifespan: start executor + background TTL cleanup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _executor
    _executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    async def _cleanup_loop():
        while True:
            await asyncio.sleep(60)
            cutoff = time() - JOB_TTL_SECONDS
            expired = [jid for jid, j in job_store.items() if j["created_at"] < cutoff]
            for jid in expired:
                job_store.pop(jid, None)

    cleanup_task = asyncio.create_task(_cleanup_loop())
    yield
    cleanup_task.cancel()
    _executor.shutdown(wait=False)


app = FastAPI(title="Color-by-Number Pipeline Service", lifespan=lifespan)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Security(_api_key_header)) -> None:
    if api_key != PIPELINE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


AuthDep = Annotated[None, Depends(verify_api_key)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _active_job_count() -> int:
    """Number of jobs currently in 'processing' state."""
    return sum(1 for j in job_store.values() if j["status"] == "processing")


def _run_job(job_id: str, image_bytes: bytes, k: int, smooth_sigma: float, quality: str) -> None:
    """Executed inside the thread pool. Updates job_store in place."""
    try:
        result = run_pipeline(image_bytes, k=k, smooth_sigma=smooth_sigma, quality=quality)
        job_store[job_id]["status"] = "done"
        job_store[job_id]["result"] = result
    except Exception as exc:
        job_store[job_id]["status"] = "failed"
        job_store[job_id]["error"] = str(exc)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
@app.head("/health")
def health():
    return {"status": "ok"}


@app.post("/jobs", status_code=202)
async def submit_job(
    _: AuthDep,
    image: UploadFile = File(...),
    k: int = Form(default=12, ge=2, le=32),
    smooth_sigma: float = Form(default=3.0, ge=0.0, le=10.0),
    quality: str = Form(default="fast"),
):
    # Validate quality param
    if quality not in ("fast", "print"):
        raise HTTPException(status_code=422, detail="quality must be 'fast' or 'print'.")

    # Validate MIME type
    if image.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{image.content_type}'. Allowed: jpeg, png, webp.",
        )

    # Read and validate size
    image_bytes = await image.read()
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({len(image_bytes):,} bytes). Max: {MAX_IMAGE_BYTES:,} bytes.",
        )

    # Reject immediately if worker is busy
    if _active_job_count() >= MAX_WORKERS:
        raise HTTPException(status_code=503, detail="Server busy. Try again later.")

    # Create job record
    job_id = str(uuid.uuid4())
    job_store[job_id] = {
        "status": "processing",
        "result": None,
        "error": None,
        "created_at": time(),
    }

    # Submit to thread pool (non-blocking)
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        _executor,
        _run_job,
        job_id, image_bytes, k, smooth_sigma, quality,
    )

    return {"jobId": job_id}


@app.get("/jobs/{job_id}")
def poll_job(_: AuthDep, job_id: str):
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found or expired.")

    if job["status"] == "processing":
        return {"status": "processing"}

    if job["status"] == "failed":
        return {"status": "failed", "error": job["error"]}

    # done
    return {"status": "done", "result": job["result"]}
