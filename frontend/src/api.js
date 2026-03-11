/**
 * Backend API client.
 *
 * VITE_BACKEND_URL: full URL of the backend service (no trailing slash).
 * When unset the Vite dev-server proxy handles /jobs and /health requests,
 * so relative paths work out of the box locally.
 */
const BASE = (import.meta.env.VITE_BACKEND_URL || "").replace(/\/$/, "");

const TOKEN_KEY = "cbn_session_token";

function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

function saveToken(token) {
    if (token) localStorage.setItem(TOKEN_KEY, token);
}

function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
}

/**
 * Submit a new paint-by-number job.
 *
 * @param {{ image: File, k: number, smoothSigma: number, quality: string }} opts
 * @returns {Promise<{ jobId: string }>}
 */
export async function submitJob({ image, k, smoothSigma, quality }) {
    const form = new FormData();
    form.append("image", image);
    form.append("k", String(k));
    form.append("smooth_sigma", String(smoothSigma));
    form.append("quality", quality);

    const headers = {};
    const token = getToken();
    if (token) headers["X-Session-Token"] = token;

    let res;
    try {
        res = await fetch(`${BASE}/jobs`, {
            method: "POST",
            headers,
            body: form,
        });
    } catch {
        throw new Error("Cannot reach the server. Check your connection.");
    }

    // Persist refreshed session token from response header.
    saveToken(res.headers.get("X-Session-Token"));

    if (!res.ok) {
        if (res.status === 401) {
            // Expired or invalid token — clear it so next call creates a fresh session.
            clearToken();
        }
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Server error (${res.status}).`);
    }

    return res.json();
}

/**
 * Poll the status of an existing job.
 *
 * @param {string} jobId
 * @returns {Promise<{ status: string, result?: object, error?: string }>}
 */
export async function pollJob(jobId) {
    const token = getToken();

    let res;
    try {
        res = await fetch(`${BASE}/jobs/${jobId}`, {
            headers: token ? { "X-Session-Token": token } : {},
        });
    } catch {
        throw new Error("Lost connection while waiting for results.");
    }

    if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Server error (${res.status}).`);
    }

    return res.json();
}
