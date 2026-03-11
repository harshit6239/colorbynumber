"""
Tests for the backend FastAPI app (app.py).

All outbound httpx calls to the pipeline are intercepted with respx so these
tests run without a real pipeline server.
"""

from time import time

import httpx
import jwt
import pytest
import respx
from starlette.testclient import TestClient

import app as app_module
from app import app, ip_timestamps, session_jobs

# ---------------------------------------------------------------------------
# Constants matching conftest.py
# ---------------------------------------------------------------------------
JWT_SECRET = "test-secret"
PIPELINE_URL = "http://fake-pipeline"
FAKE_JOB_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

MOCK_PIPELINE_202 = httpx.Response(202, json={"jobId": FAKE_JOB_ID})
MOCK_PIPELINE_RESULT = httpx.Response(
    200,
    json={
        "status": "done",
        "result": {"template": "abc", "palette": "def", "colored_preview": "ghi"},
    },
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_token(session_id: str, exp_offset: int = 1800) -> str:
    payload = {"session_id": session_id, "exp": int(time()) + exp_offset}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _expired_token(session_id: str) -> str:
    return _make_token(session_id, exp_offset=-1)


def _sample_image() -> bytes:
    """Minimal 8-byte fake PNG — backend does NOT decode pixels, just proxies."""
    return b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clear_state():
    """Reset in-memory state before every test."""
    session_jobs.clear()
    ip_timestamps.clear()
    yield
    session_jobs.clear()
    ip_timestamps.clear()


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
# POST /jobs — session handling
# ---------------------------------------------------------------------------
class TestSessionHandling:
    @respx.mock
    def test_new_session_token_returned(self, client):
        respx.post(f"{PIPELINE_URL}/jobs").mock(return_value=MOCK_PIPELINE_202)
        r = client.post(
            "/jobs",
            files={"image": ("img.png", _sample_image(), "image/png")},
        )
        assert r.status_code == 202
        assert "x-session-token" in r.headers
        token = r.headers["x-session-token"]
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        assert "session_id" in payload

    @respx.mock
    def test_existing_session_reused(self, client):
        session_id = "existing-session-id"
        token = _make_token(session_id)
        respx.post(f"{PIPELINE_URL}/jobs").mock(return_value=MOCK_PIPELINE_202)
        r = client.post(
            "/jobs",
            headers={"X-Session-Token": token},
            files={"image": ("img.png", _sample_image(), "image/png")},
        )
        assert r.status_code == 202
        # Returned token should encode the same session_id
        returned_payload = jwt.decode(
            r.headers["x-session-token"], JWT_SECRET, algorithms=["HS256"]
        )
        assert returned_payload["session_id"] == session_id

    def test_expired_session_token_returns_401(self, client):
        token = _expired_token("some-session")
        r = client.post(
            "/jobs",
            headers={"X-Session-Token": token},
            files={"image": ("img.png", _sample_image(), "image/png")},
        )
        assert r.status_code == 401
        assert "expired" in r.json()["detail"].lower()

    def test_invalid_session_token_returns_401(self, client):
        r = client.post(
            "/jobs",
            headers={"X-Session-Token": "not.a.jwt"},
            files={"image": ("img.png", _sample_image(), "image/png")},
        )
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /jobs — rate limiting
# ---------------------------------------------------------------------------
class TestRateLimit:
    @respx.mock
    def test_rate_limit_exceeded_returns_429(self, client, monkeypatch):
        monkeypatch.setattr(app_module, "RATE_LIMIT_JOBS", 2)
        respx.post(f"{PIPELINE_URL}/jobs").mock(return_value=MOCK_PIPELINE_202)

        # Two successful submissions
        for _ in range(2):
            r = client.post(
                "/jobs", files={"image": ("img.png", _sample_image(), "image/png")}
            )
            assert r.status_code == 202

        # Third should be rejected
        r = client.post(
            "/jobs", files={"image": ("img.png", _sample_image(), "image/png")}
        )
        assert r.status_code == 429
        assert "rate limit" in r.json()["detail"].lower()

    @respx.mock
    def test_rate_limit_resets_after_window(self, client, monkeypatch):
        monkeypatch.setattr(app_module, "RATE_LIMIT_JOBS", 1)
        monkeypatch.setattr(app_module, "RATE_LIMIT_WINDOW_SECONDS", 600)
        respx.post(f"{PIPELINE_URL}/jobs").mock(return_value=MOCK_PIPELINE_202)

        # First call succeeds
        r = client.post(
            "/jobs", files={"image": ("img.png", _sample_image(), "image/png")}
        )
        assert r.status_code == 202

        # Simulate timestamps falling outside the window
        ip = list(ip_timestamps.keys())[0]
        ip_timestamps[ip] = [t - 700 for t in ip_timestamps[ip]]  # push into the past

        # Should succeed again
        r = client.post(
            "/jobs", files={"image": ("img.png", _sample_image(), "image/png")}
        )
        assert r.status_code == 202

    @respx.mock
    def test_different_ips_independently_rate_limited(self, client, monkeypatch):
        monkeypatch.setattr(app_module, "RATE_LIMIT_JOBS", 1)
        respx.post(f"{PIPELINE_URL}/jobs").mock(return_value=MOCK_PIPELINE_202)

        # IP-A hits its limit
        r = client.post(
            "/jobs",
            headers={"X-Forwarded-For": "1.2.3.4"},
            files={"image": ("img.png", _sample_image(), "image/png")},
        )
        assert r.status_code == 202

        r = client.post(
            "/jobs",
            headers={"X-Forwarded-For": "1.2.3.4"},
            files={"image": ("img.png", _sample_image(), "image/png")},
        )
        assert r.status_code == 429

        # IP-B should still be allowed
        r = client.post(
            "/jobs",
            headers={"X-Forwarded-For": "9.9.9.9"},
            files={"image": ("img.png", _sample_image(), "image/png")},
        )
        assert r.status_code == 202


# ---------------------------------------------------------------------------
# POST /jobs — pipeline proxy behaviour
# ---------------------------------------------------------------------------
class TestSubmitPipelineProxy:
    @respx.mock
    def test_success_returns_job_id(self, client):
        respx.post(f"{PIPELINE_URL}/jobs").mock(return_value=MOCK_PIPELINE_202)
        r = client.post(
            "/jobs", files={"image": ("img.png", _sample_image(), "image/png")}
        )
        assert r.status_code == 202
        assert r.json()["jobId"] == FAKE_JOB_ID

    @respx.mock
    def test_job_registered_in_session(self, client):
        respx.post(f"{PIPELINE_URL}/jobs").mock(return_value=MOCK_PIPELINE_202)
        r = client.post(
            "/jobs", files={"image": ("img.png", _sample_image(), "image/png")}
        )
        token_payload = jwt.decode(
            r.headers["x-session-token"], JWT_SECRET, algorithms=["HS256"]
        )
        session_id = token_payload["session_id"]
        assert FAKE_JOB_ID in session_jobs[session_id]

    @respx.mock
    def test_pipeline_validation_error_forwarded(self, client):
        respx.post(f"{PIPELINE_URL}/jobs").mock(
            return_value=httpx.Response(400, json={"detail": "Image too small."})
        )
        r = client.post(
            "/jobs", files={"image": ("img.png", _sample_image(), "image/png")}
        )
        assert r.status_code == 400
        assert r.json()["detail"] == "Image too small."

    @respx.mock
    def test_pipeline_busy_forwarded(self, client):
        respx.post(f"{PIPELINE_URL}/jobs").mock(
            return_value=httpx.Response(503, json={"detail": "Server busy."})
        )
        r = client.post(
            "/jobs", files={"image": ("img.png", _sample_image(), "image/png")}
        )
        assert r.status_code == 503

    @respx.mock
    def test_pipeline_unreachable_returns_502(self, client):
        respx.post(f"{PIPELINE_URL}/jobs").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        r = client.post(
            "/jobs", files={"image": ("img.png", _sample_image(), "image/png")}
        )
        assert r.status_code == 502
        assert "unreachable" in r.json()["detail"].lower()

    @respx.mock
    def test_form_params_forwarded_to_pipeline(self, client):
        route = respx.post(f"{PIPELINE_URL}/jobs").mock(return_value=MOCK_PIPELINE_202)
        client.post(
            "/jobs",
            data={"k": "8", "smooth_sigma": "2.5", "quality": "print"},
            files={"image": ("img.png", _sample_image(), "image/png")},
        )
        assert route.called
        # Verify the request body included the custom params
        sent_content = route.calls[0].request.content.decode(errors="replace")
        assert "8" in sent_content
        assert "2.5" in sent_content
        assert "print" in sent_content

    def test_k_out_of_range_rejected_by_backend(self, client):
        r = client.post(
            "/jobs",
            data={"k": "16"},
            files={"image": ("img.png", _sample_image(), "image/png")},
        )
        assert r.status_code == 422

    def test_smooth_sigma_out_of_range_rejected(self, client):
        r = client.post(
            "/jobs",
            data={"smooth_sigma": "11"},
            files={"image": ("img.png", _sample_image(), "image/png")},
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /jobs/{job_id} — ownership & proxy
# ---------------------------------------------------------------------------
class TestPollJob:
    def test_missing_session_token_returns_401(self, client):
        r = client.get(f"/jobs/{FAKE_JOB_ID}")
        assert r.status_code == 401
        assert "missing" in r.json()["detail"].lower()

    def test_expired_token_returns_401(self, client):
        token = _expired_token("some-session")
        r = client.get(f"/jobs/{FAKE_JOB_ID}", headers={"X-Session-Token": token})
        assert r.status_code == 401

    def test_job_not_in_session_returns_403(self, client):
        session_id = "owner-session"
        token = _make_token(session_id)
        # Session has no jobs
        r = client.get(f"/jobs/{FAKE_JOB_ID}", headers={"X-Session-Token": token})
        assert r.status_code == 403
        assert "does not belong" in r.json()["detail"].lower()

    def test_job_from_different_session_returns_403(self, client):
        owner_session = "owner-session"
        other_session = "other-session"
        session_jobs[owner_session].add(FAKE_JOB_ID)

        token = _make_token(other_session)
        r = client.get(f"/jobs/{FAKE_JOB_ID}", headers={"X-Session-Token": token})
        assert r.status_code == 403

    @respx.mock
    def test_poll_proxied_to_pipeline(self, client):
        session_id = "poll-session"
        session_jobs[session_id].add(FAKE_JOB_ID)
        token = _make_token(session_id)

        respx.get(f"{PIPELINE_URL}/jobs/{FAKE_JOB_ID}").mock(
            return_value=MOCK_PIPELINE_RESULT
        )
        r = client.get(f"/jobs/{FAKE_JOB_ID}", headers={"X-Session-Token": token})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "done"
        assert "result" in body

    @respx.mock
    def test_poll_processing_status(self, client):
        session_id = "poll-session"
        session_jobs[session_id].add(FAKE_JOB_ID)
        token = _make_token(session_id)

        respx.get(f"{PIPELINE_URL}/jobs/{FAKE_JOB_ID}").mock(
            return_value=httpx.Response(200, json={"status": "processing"})
        )
        r = client.get(f"/jobs/{FAKE_JOB_ID}", headers={"X-Session-Token": token})
        assert r.status_code == 200
        assert r.json()["status"] == "processing"

    @respx.mock
    def test_poll_pipeline_unreachable_returns_502(self, client):
        session_id = "poll-session"
        session_jobs[session_id].add(FAKE_JOB_ID)
        token = _make_token(session_id)

        respx.get(f"{PIPELINE_URL}/jobs/{FAKE_JOB_ID}").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        r = client.get(f"/jobs/{FAKE_JOB_ID}", headers={"X-Session-Token": token})
        assert r.status_code == 502
