"""
Integration tests: backend ↔ pipeline end-to-end.

Spins up the real pipeline server as a subprocess so the full chain is
exercised over the network:

    TestClient (backend)  →  [HTTP]  →  pipeline subprocess  →  run_pipeline()

Run only integration tests:
    uv run pytest tests/test_integration.py -v

Run everything:
    uv run pytest tests/ -v
"""

import os
import socket
import struct
import subprocess
import time
import zlib

import httpx
import jwt
import pytest
from starlette.testclient import TestClient

import app as app_module
from app import app, ip_timestamps, session_jobs

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_PIPELINE_KEY = "integration-key"
_JWT_SECRET = "test-secret"  # matches conftest.py


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _minimal_png(width: int = 150, height: int = 150) -> bytes:
    """Generate a valid PNG using only the Python standard library."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return (
            struct.pack(">I", len(data))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    row = b"\x00" + b"\x00\xff\x00" * width  # filter byte + green RGB pixels
    idat = chunk(b"IDAT", zlib.compress(row * height))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _get_session_id(token: str) -> str:
    return jwt.decode(token, _JWT_SECRET, algorithms=["HS256"])["session_id"]


def _poll_until_done(
    client: TestClient, job_id: str, token: str, max_wait: int = 60
) -> dict:
    """Poll GET /jobs/{job_id} until status != 'processing', then return the body."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        r = client.get(f"/jobs/{job_id}", headers={"X-Session-Token": token})
        assert r.status_code == 200, f"Unexpected poll status {r.status_code}: {r.text}"
        body = r.json()
        if body["status"] != "processing":
            return body
        time.sleep(0.5)
    pytest.fail(f"Job {job_id!r} did not finish within {max_wait}s")


# ---------------------------------------------------------------------------
# Session-scoped pipeline subprocess
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def pipeline_server():
    """Start the real pipeline service on a free port and yield its base URL."""
    port = _free_port()
    env = {
        **os.environ,
        "PIPELINE_API_KEY": _PIPELINE_KEY,
        "MAX_WORKERS": "2",
    }
    proc = subprocess.Popen(
        [
            "uv",
            "run",
            "uvicorn",
            "app:app",
            f"--port={port}",
            "--no-access-log",
            "--timeout-graceful-shutdown=1",
        ],
        cwd=r"a:\CODE\colorbynumber\pipeline",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"

    # Wait up to 30 s for the pipeline to pass a health check
    for _ in range(60):
        try:
            httpx.get(f"{base_url}/health", timeout=1.0)
            break
        except httpx.RequestError:
            time.sleep(0.5)
    else:
        proc.terminate()
        pytest.fail("Pipeline server did not start within 30 s.")

    yield base_url

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture()
def integration_client(pipeline_server, monkeypatch):
    """Backend TestClient wired to the real pipeline subprocess."""
    monkeypatch.setattr(app_module, "PIPELINE_URL", pipeline_server)
    monkeypatch.setattr(app_module, "PIPELINE_API_KEY", _PIPELINE_KEY)
    session_jobs.clear()
    ip_timestamps.clear()
    with TestClient(app) as c:
        yield c
    session_jobs.clear()
    ip_timestamps.clear()


# ---------------------------------------------------------------------------
# Full happy-path flow
# ---------------------------------------------------------------------------
@pytest.mark.integration
class TestFullFlow:
    def test_submit_and_poll_to_completion(self, integration_client):
        """Submit a real image; poll until the pipeline returns a result."""
        r = integration_client.post(
            "/jobs",
            files={"image": ("test.png", _minimal_png(), "image/png")},
        )
        assert r.status_code == 202, r.text
        body = r.json()
        assert "jobId" in body
        token = r.headers["x-session-token"]

        result = _poll_until_done(integration_client, body["jobId"], token)
        assert result["status"] == "done"
        assert "result" in result
        for key in ("template", "palette", "colored_preview"):
            assert key in result["result"], f"Missing result key: {key}"

    def test_custom_params_forwarded_to_pipeline(self, integration_client):
        """Backend forwards k, smooth_sigma, quality and pipeline accepts them."""
        r = integration_client.post(
            "/jobs",
            data={"k": "4", "smooth_sigma": "1.5", "quality": "fast"},
            files={"image": ("test.png", _minimal_png(), "image/png")},
        )
        assert r.status_code == 202, r.text
        token = r.headers["x-session-token"]
        result = _poll_until_done(integration_client, r.json()["jobId"], token)
        assert result["status"] == "done"

    def test_session_token_reused_across_submits(self, integration_client):
        """Jobs submitted with the same session token share the same session_id."""
        r1 = integration_client.post(
            "/jobs",
            files={"image": ("test.png", _minimal_png(), "image/png")},
        )
        assert r1.status_code == 202
        token1 = r1.headers["x-session-token"]

        r2 = integration_client.post(
            "/jobs",
            headers={"X-Session-Token": token1},
            files={"image": ("test.png", _minimal_png(), "image/png")},
        )
        assert r2.status_code == 202
        token2 = r2.headers["x-session-token"]

        # Both tokens encode the same session_id (token was re-issued / refreshed)
        assert _get_session_id(token1) == _get_session_id(token2)


# ---------------------------------------------------------------------------
# Pipeline error forwarding
# ---------------------------------------------------------------------------
@pytest.mark.integration
class TestErrorForwarding:
    def test_unsupported_mime_forwarded_as_400(self, integration_client):
        """Pipeline MIME rejection is forwarded through the backend as 400."""
        r = integration_client.post(
            "/jobs",
            files={"image": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert r.status_code == 400
        assert "unsupported" in r.json()["detail"].lower()

    def test_too_small_image_forwarded_as_400(self, integration_client):
        """Pipeline pixel-size rejection (< 100 px) is forwarded as 400."""
        r = integration_client.post(
            "/jobs",
            files={"image": ("tiny.png", _minimal_png(width=10, height=10), "image/png")},
        )
        assert r.status_code == 400
        assert "too small" in r.json()["detail"].lower()

    def test_k_out_of_range_rejected_by_backend_before_pipeline(self, integration_client):
        """Backend FastAPI validation rejects k > 15 before calling the pipeline."""
        r = integration_client.post(
            "/jobs",
            data={"k": "16"},
            files={"image": ("test.png", _minimal_png(), "image/png")},
        )
        assert r.status_code == 422  # FastAPI form validation — never reaches pipeline


# ---------------------------------------------------------------------------
# Session ownership
# ---------------------------------------------------------------------------
@pytest.mark.integration
class TestSessionOwnership:
    def test_owner_can_poll_job(self, integration_client):
        """The session that submitted a job can poll it."""
        r = integration_client.post(
            "/jobs",
            files={"image": ("test.png", _minimal_png(), "image/png")},
        )
        assert r.status_code == 202
        job_id = r.json()["jobId"]
        token = r.headers["x-session-token"]

        poll = integration_client.get(
            f"/jobs/{job_id}", headers={"X-Session-Token": token}
        )
        assert poll.status_code == 200

    def test_different_session_cannot_poll_job(self, integration_client):
        """A different session is denied access to another session's job."""
        r = integration_client.post(
            "/jobs",
            files={"image": ("test.png", _minimal_png(), "image/png")},
        )
        assert r.status_code == 202
        job_id = r.json()["jobId"]

        other_token = jwt.encode(
            {"session_id": "attacker-session", "exp": int(time.time()) + 1800},
            _JWT_SECRET,
            algorithm="HS256",
        )
        poll = integration_client.get(
            f"/jobs/{job_id}", headers={"X-Session-Token": other_token}
        )
        assert poll.status_code == 403

    def test_multiple_jobs_tracked_in_one_session(self, integration_client):
        """All jobs submitted within the same session are accessible."""
        token = None
        job_ids = []
        for _ in range(2):
            r = integration_client.post(
                "/jobs",
                headers={"X-Session-Token": token} if token else {},
                files={"image": ("test.png", _minimal_png(), "image/png")},
            )
            assert r.status_code == 202
            job_ids.append(r.json()["jobId"])
            token = r.headers["x-session-token"]

        for job_id in job_ids:
            poll = integration_client.get(
                f"/jobs/{job_id}", headers={"X-Session-Token": token}
            )
            assert poll.status_code == 200, f"Job {job_id} not accessible in session"


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
@pytest.mark.integration
class TestRateLimiting:
    def test_rate_limit_blocks_excess_requests(self, integration_client, monkeypatch):
        """IP is blocked after submitting RATE_LIMIT_JOBS requests in the window."""
        monkeypatch.setattr(app_module, "RATE_LIMIT_JOBS", 2)

        for i in range(2):
            r = integration_client.post(
                "/jobs",
                headers={"X-Forwarded-For": "10.0.0.5"},
                files={"image": ("test.png", _minimal_png(), "image/png")},
            )
            assert r.status_code == 202, f"Request {i + 1} failed: {r.text}"

        r = integration_client.post(
            "/jobs",
            headers={"X-Forwarded-For": "10.0.0.5"},
            files={"image": ("test.png", _minimal_png(), "image/png")},
        )
        assert r.status_code == 429
        assert "rate limit" in r.json()["detail"].lower()

    def test_different_ips_have_independent_limits(self, integration_client, monkeypatch):
        """Exhausting one IP's quota does not block a different IP."""
        monkeypatch.setattr(app_module, "RATE_LIMIT_JOBS", 1)

        # IP-A hits the limit
        r = integration_client.post(
            "/jobs",
            headers={"X-Forwarded-For": "11.0.0.1"},
            files={"image": ("test.png", _minimal_png(), "image/png")},
        )
        assert r.status_code == 202

        r = integration_client.post(
            "/jobs",
            headers={"X-Forwarded-For": "11.0.0.1"},
            files={"image": ("test.png", _minimal_png(), "image/png")},
        )
        assert r.status_code == 429

        # IP-B is unaffected
        r = integration_client.post(
            "/jobs",
            headers={"X-Forwarded-For": "11.0.0.2"},
            files={"image": ("test.png", _minimal_png(), "image/png")},
        )
        assert r.status_code == 202
