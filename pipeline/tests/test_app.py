"""
Tests for the pipeline FastAPI app (app.py).

All tests mock `run_pipeline` so they run without executing the real image
processing pipeline (fast, no GPU/CV2 weight).
"""

import base64
import time
from unittest.mock import patch

import cv2
import numpy as np
import pytest
from starlette.testclient import TestClient

import app as app_module
from app import app, job_store

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
API_KEY = "test-key"
HEADERS = {"X-API-Key": API_KEY}

MOCK_RESULT = {
    "template": base64.b64encode(b"fake-template").decode(),
    "palette": base64.b64encode(b"fake-palette").decode(),
    "colored_preview": base64.b64encode(b"fake-preview").decode(),
}


def _tiny_png() -> bytes:
    """Return bytes of a small 10×10 PNG — used to trigger min-size checks."""
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    img[:] = (0, 200, 0)  # green (BGR)
    _, buf = cv2.imencode(".png", img)
    return buf.tobytes()


def _sample_png() -> bytes:
    """Return a ~270 KB random-noise 300×300 PNG, well above any min-size limit."""
    rng = np.random.default_rng(42)
    img = rng.integers(0, 256, (300, 300, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".png", img)
    return buf.tobytes()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clear_job_store():
    """Ensure job_store is empty before every test."""
    job_store.clear()
    yield
    job_store.clear()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
class TestHealth:
    def test_get_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_head_returns_200_no_body(self, client):
        r = client.head("/health")
        assert r.status_code == 200
        assert r.content == b""


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
class TestAuth:
    def test_missing_key_on_submit(self, client):
        r = client.post("/jobs", files={"image": ("img.png", _tiny_png(), "image/png")})
        assert r.status_code == 401

    def test_wrong_key_on_submit(self, client):
        r = client.post(
            "/jobs",
            headers={"X-API-Key": "totally-wrong"},
            files={"image": ("img.png", _tiny_png(), "image/png")},
        )
        assert r.status_code == 401

    def test_missing_key_on_poll(self, client):
        r = client.get("/jobs/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 401

    def test_valid_key_reaches_endpoint(self, client):
        """A valid key should not be rejected for auth (may fail for other reasons)."""
        with patch("app.run_pipeline", return_value=MOCK_RESULT):
            r = client.post(
                "/jobs",
                headers=HEADERS,
                files={"image": ("img.png", _sample_png(), "image/png")},
            )
        assert r.status_code != 401


# ---------------------------------------------------------------------------
# POST /jobs — input validation
# ---------------------------------------------------------------------------
class TestSubmitValidation:
    def test_unsupported_mime_type(self, client):
        r = client.post(
            "/jobs",
            headers=HEADERS,
            files={"image": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert r.status_code == 400
        assert "Unsupported file type" in r.json()["detail"]

    def test_file_too_large(self, client, monkeypatch):
        monkeypatch.setattr(app_module, "MAX_IMAGE_BYTES", 5)
        r = client.post(
            "/jobs",
            headers=HEADERS,
            files={"image": ("img.png", _sample_png(), "image/png")},
        )
        assert r.status_code == 400
        assert "too large" in r.json()["detail"]

    def test_image_too_small_pixels(self, client, monkeypatch):
        monkeypatch.setattr(app_module, "MIN_IMAGE_PX", 500)
        r = client.post(
            "/jobs",
            headers=HEADERS,
            files={"image": ("img.png", _tiny_png(), "image/png")},
        )
        assert r.status_code == 400
        assert "too small" in r.json()["detail"]

    def test_image_too_large_pixels(self, client, monkeypatch):
        monkeypatch.setattr(app_module, "MAX_IMAGE_PX", 50)
        r = client.post(
            "/jobs",
            headers=HEADERS,
            files={"image": ("img.png", _sample_png(), "image/png")},
        )
        assert r.status_code == 400
        assert "too large" in r.json()["detail"]

    def test_invalid_quality_value(self, client):
        r = client.post(
            "/jobs",
            headers=HEADERS,
            data={"quality": "ultra"},
            files={"image": ("img.png", _tiny_png(), "image/png")},
        )
        assert r.status_code == 422
        assert "quality" in r.json()["detail"]

    def test_k_too_small(self, client):
        r = client.post(
            "/jobs",
            headers=HEADERS,
            data={"k": "1"},
            files={"image": ("img.png", _sample_png(), "image/png")},
        )
        assert r.status_code == 422

    def test_k_too_large(self, client):
        r = client.post(
            "/jobs",
            headers=HEADERS,
            data={"k": "16"},
            files={"image": ("img.png", _sample_png(), "image/png")},
        )
        assert r.status_code == 422

    def test_smooth_sigma_too_large(self, client):
        r = client.post(
            "/jobs",
            headers=HEADERS,
            data={"smooth_sigma": "10.1"},
            files={"image": ("img.png", _sample_png(), "image/png")},
        )
        assert r.status_code == 422

    def test_smooth_sigma_negative(self, client):
        r = client.post(
            "/jobs",
            headers=HEADERS,
            data={"smooth_sigma": "-0.1"},
            files={"image": ("img.png", _sample_png(), "image/png")},
        )
        assert r.status_code == 422

    def test_server_busy_returns_503(self, client):
        with patch("app._active_job_count", return_value=999):
            r = client.post(
                "/jobs",
                headers=HEADERS,
                files={"image": ("img.png", _sample_png(), "image/png")},
            )
        assert r.status_code == 503
        assert "busy" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /jobs — happy path
# ---------------------------------------------------------------------------
class TestSubmitSuccess:
    def test_returns_202_with_job_id(self, client):
        with patch("app.run_pipeline", return_value=MOCK_RESULT):
            r = client.post(
                "/jobs",
                headers=HEADERS,
                files={"image": ("img.png", _sample_png(), "image/png")},
            )
        assert r.status_code == 202
        body = r.json()
        assert "jobId" in body
        assert len(body["jobId"]) == 36  # UUID length

    def test_accepts_jpeg(self, client):
        rng = np.random.default_rng(42)
        img = rng.integers(0, 256, (300, 300, 3), dtype=np.uint8)
        _, buf = cv2.imencode(".jpg", img)
        with patch("app.run_pipeline", return_value=MOCK_RESULT):
            r = client.post(
                "/jobs",
                headers=HEADERS,
                files={"image": ("img.jpg", buf.tobytes(), "image/jpeg")},
            )
        assert r.status_code == 202

    def test_job_created_in_store(self, client):
        with patch("app.run_pipeline", return_value=MOCK_RESULT):
            r = client.post(
                "/jobs",
                headers=HEADERS,
                files={"image": ("img.png", _sample_png(), "image/png")},
            )
        job_id = r.json()["jobId"]
        assert job_id in job_store

    def test_custom_params_accepted(self, client):
        with patch("app.run_pipeline", return_value=MOCK_RESULT):
            r = client.post(
                "/jobs",
                headers=HEADERS,
                data={"k": "8", "smooth_sigma": "2.5", "quality": "print"},
                files={"image": ("img.png", _sample_png(), "image/png")},
            )
        assert r.status_code == 202

    def test_k_at_max_boundary(self, client):
        """k=15 is exactly at the new max and must be accepted."""
        with patch("app.run_pipeline", return_value=MOCK_RESULT):
            r = client.post(
                "/jobs",
                headers=HEADERS,
                data={"k": "15"},
                files={"image": ("img.png", _sample_png(), "image/png")},
            )
        assert r.status_code == 202


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}
# ---------------------------------------------------------------------------
class TestPollJob:
    def _seed(self, status, result=None, error=None):
        job_store["test-job"] = {
            "status": status,
            "result": result,
            "error": error,
            "created_at": time.time(),
        }

    def test_nonexistent_job_returns_404(self, client):
        r = client.get("/jobs/00000000-0000-0000-0000-000000000000", headers=HEADERS)
        assert r.status_code == 404

    def test_processing_job(self, client):
        self._seed("processing")
        r = client.get("/jobs/test-job", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["status"] == "processing"

    def test_failed_job_returns_error(self, client):
        self._seed("failed", error="Something went wrong")
        r = client.get("/jobs/test-job", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "failed"
        assert data["error"] == "Something went wrong"

    def test_done_job_returns_result(self, client):
        self._seed("done", result=MOCK_RESULT)
        r = client.get("/jobs/test-job", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "done"
        assert data["result"]["template"] == MOCK_RESULT["template"]
        assert data["result"]["palette"] == MOCK_RESULT["palette"]
        assert data["result"]["colored_preview"] == MOCK_RESULT["colored_preview"]
