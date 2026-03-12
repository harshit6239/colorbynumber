import { useState, useRef, useEffect } from "react";
import { submitJob, pollJob } from "../api";

const POLL_INTERVAL_MS = 2500;

// ─── Helpers ────────────────────────────────────────────────────────────────

function b64Src(b64) {
    return `data:image/png;base64,${b64}`;
}

function downloadB64(b64, filename) {
    const a = document.createElement("a");
    a.href = b64Src(b64);
    a.download = filename;
    a.click();
}

// ─── Sub-components ─────────────────────────────────────────────────────────

function DropZone({ preview, onFile }) {
    const [dragging, setDragging] = useState(false);
    const inputRef = useRef(null);

    function handleFiles(files) {
        const f = files[0];
        if (f) onFile(f);
    }

    function onDrop(e) {
        e.preventDefault();
        setDragging(false);
        handleFiles(e.dataTransfer.files);
    }

    function onKeyDown(e) {
        if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
    }

    return (
        <div className="upload-area">
            <div
                className={`drop-zone${dragging ? " dragging" : ""}${preview ? " has-preview" : ""}`}
                role="button"
                tabIndex={0}
                aria-label="Click or drag an image here"
                onClick={() => inputRef.current?.click()}
                onKeyDown={onKeyDown}
                onDragOver={(e) => {
                    e.preventDefault();
                    setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
            >
                {preview ? (
                    <img
                        src={preview}
                        alt="Selected image preview"
                        className="upload-preview"
                    />
                ) : (
                    <>
                        <div
                            className="drop-icon"
                            aria-hidden="true"
                        >
                            <svg
                                viewBox="0 0 24 24"
                                xmlns="http://www.w3.org/2000/svg"
                            >
                                <rect
                                    x="3"
                                    y="3"
                                    width="18"
                                    height="18"
                                    rx="2"
                                    ry="2"
                                />
                                <circle
                                    cx="8.5"
                                    cy="8.5"
                                    r="1.5"
                                />
                                <polyline points="21 15 16 10 5 21" />
                            </svg>
                        </div>
                        <p className="drop-label">Drop an image here</p>
                        <p className="drop-hint">
                            JPEG · PNG · WebP &nbsp;·&nbsp; max 10 MB
                        </p>
                    </>
                )}
            </div>
            <input
                ref={inputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="visually-hidden"
                onChange={(e) =>
                    e.target.files[0] && handleFiles(e.target.files)
                }
            />
            {preview && (
                <button
                    className="btn-ghost change-btn"
                    onClick={() => inputRef.current?.click()}
                >
                    Change image
                </button>
            )}
        </div>
    );
}

function Spinner({ label }) {
    return (
        <div
            className="spinner-screen"
            role="status"
            aria-live="polite"
        >
            <div
                className="spinner-palette"
                aria-hidden="true"
            >
                <span className="spinner-color" />
                <span className="spinner-color" />
                <span className="spinner-color" />
                <span className="spinner-color" />
                <span className="spinner-color" />
            </div>
            <p className="spinner-label">{label}</p>
            <p className="spinner-hint">This may take 30–90 seconds.</p>
        </div>
    );
}

function ResultTabs({ result }) {
    const [tab, setTab] = useState("template");

    const tabs = [
        { id: "template", label: "Template", filename: "template.png" },
        {
            id: "colored_preview",
            label: "Colored Preview",
            filename: "colored_preview.png",
        },
        { id: "palette", label: "Palette", filename: "palette.png" },
    ];

    return (
        <div className="result-tabs">
            <div
                className="tab-bar"
                role="tablist"
            >
                {tabs.map((t) => (
                    <button
                        key={t.id}
                        role="tab"
                        aria-selected={tab === t.id}
                        className={`tab-btn${tab === t.id ? " active" : ""}`}
                        onClick={() => setTab(t.id)}
                    >
                        {t.label}
                    </button>
                ))}
            </div>

            {tabs.map((t) => (
                <div
                    key={t.id}
                    role="tabpanel"
                    hidden={tab !== t.id}
                    className="tab-panel"
                >
                    <div className="result-img-wrap">
                        <img
                            src={b64Src(result[t.id])}
                            alt={t.label}
                            className="result-img"
                        />
                    </div>
                    <button
                        className="btn-primary download-btn"
                        onClick={() => downloadB64(result[t.id], t.filename)}
                    >
                        ↓ Download {t.label}
                    </button>
                </div>
            ))}
        </div>
    );
}

// ─── Generate page ───────────────────────────────────────────────────────────

export default function Generate() {
    // idle | submitting | polling | done
    const [phase, setPhase] = useState("idle");

    const [file, setFile] = useState(null);
    const [preview, setPreview] = useState(null);
    const [k, setK] = useState(12);
    const [smoothSigma, setSmoothSigma] = useState(3.0);
    const [quality, setQuality] = useState("fast");

    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);

    const pollTimer = useRef(null);

    useEffect(() => {
        return () => {
            if (preview) URL.revokeObjectURL(preview);
        };
    }, [preview]);

    function handleFile(f) {
        const allowed = ["image/jpeg", "image/png", "image/webp"];
        if (!allowed.includes(f.type)) {
            setError("Unsupported file type. Please use JPEG, PNG, or WebP.");
            return;
        }
        setError(null);
        setFile(f);
        setPreview(URL.createObjectURL(f));
    }

    async function handleSubmit() {
        if (!file) return;

        setError(null);
        setPhase("submitting");

        let jobId;
        try {
            const data = await submitJob({
                image: file,
                k,
                smoothSigma,
                quality,
            });
            jobId = data.jobId;
        } catch (err) {
            setError(err.message);
            setPhase("idle");
            return;
        }

        setPhase("polling");

        async function poll() {
            try {
                const data = await pollJob(jobId);

                if (data.status === "done") {
                    setResult({
                        template: data.result.template,
                        colored_preview: data.result.colored_preview,
                        palette: data.result.palette,
                    });
                    setPhase("done");
                } else if (data.status === "failed") {
                    setError(
                        data.error ||
                            "Processing failed — try a different image.",
                    );
                    setPhase("idle");
                } else {
                    pollTimer.current = setTimeout(poll, POLL_INTERVAL_MS);
                }
            } catch (err) {
                setError(err.message);
                setPhase("idle");
            }
        }

        poll();
    }

    function handleReset() {
        clearTimeout(pollTimer.current);
        setFile(null);
        setPreview(null);
        setResult(null);
        setError(null);
        setK(12);
        setSmoothSigma(3.0);
        setQuality("fast");
        setPhase("idle");
    }

    // ── Loading ─────────────────────────────────────────────────────────────
    if (phase === "submitting") return <Spinner label="Uploading image…" />;
    if (phase === "polling")
        return <Spinner label="Generating your template…" />;

    // ── Results ─────────────────────────────────────────────────────────────
    if (phase === "done" && result) {
        return (
            <div className="page">
                <div className="container">
                    <div className="results-header">
                        <h2 className="page-heading">Your HueCraft template</h2>
                        <button
                            className="btn-ghost"
                            onClick={handleReset}
                        >
                            ← New image
                        </button>
                    </div>
                    <ResultTabs result={result} />
                </div>
            </div>
        );
    }

    // ── Form ─────────────────────────────────────────────────────────────────
    return (
        <div className="page">
            <div className="container">
                <header className="gen-header">
                    <h2 className="page-heading">Generate your template</h2>
                    <p className="page-sub">
                        Upload a photo, tune the palette, and let HueCraft do
                        the rest.
                    </p>
                </header>

                <div className="form-grid">
                    {/* Left: upload */}
                    <section
                        className="card"
                        aria-label="Image upload"
                    >
                        <DropZone
                            preview={preview}
                            onFile={handleFile}
                        />
                    </section>

                    {/* Right: settings */}
                    <section
                        className="card settings-card"
                        aria-label="Settings"
                    >
                        <h3 className="settings-heading">Settings</h3>

                        {/* Number of colors */}
                        <div className="field">
                            <div className="field-row">
                                <label htmlFor="slider-k">Colors</label>
                                <span className="field-value">{k}</span>
                            </div>
                            <input
                                id="slider-k"
                                type="range"
                                min="2"
                                max="15"
                                step="1"
                                value={k}
                                onChange={(e) => setK(Number(e.target.value))}
                                className="slider"
                            />
                            <div className="slider-hints">
                                <span>2</span>
                                <span>15</span>
                            </div>
                        </div>

                        {/* Smoothing */}
                        <div className="field">
                            <div className="field-row">
                                <label htmlFor="slider-sigma">
                                    Edge smoothing
                                </label>
                                <span className="field-value">
                                    {smoothSigma.toFixed(1)}
                                </span>
                            </div>
                            <input
                                id="slider-sigma"
                                type="range"
                                min="0"
                                max="10"
                                step="0.5"
                                value={smoothSigma}
                                onChange={(e) =>
                                    setSmoothSigma(Number(e.target.value))
                                }
                                className="slider"
                            />
                            <div className="slider-hints">
                                <span>None</span>
                                <span>Max</span>
                            </div>
                        </div>

                        {/* Quality */}
                        <div className="field">
                            <label className="field-label">Quality</label>
                            <div
                                className="toggle-group"
                                role="group"
                                aria-label="Quality"
                            >
                                <button
                                    className={`toggle-btn${quality === "fast" ? " active" : ""}`}
                                    onClick={() => setQuality("fast")}
                                    aria-pressed={quality === "fast"}
                                >
                                    Fast
                                    <span>≤ 1 000 px</span>
                                </button>
                                <button
                                    className={`toggle-btn${quality === "print" ? " active" : ""}`}
                                    onClick={() => setQuality("print")}
                                    aria-pressed={quality === "print"}
                                >
                                    Print
                                    <span>≤ 2 500 px</span>
                                </button>
                            </div>
                        </div>

                        {error && (
                            <p
                                className="error-banner"
                                role="alert"
                            >
                                {error}
                            </p>
                        )}

                        <button
                            className="btn-primary submit-btn"
                            disabled={!file}
                            onClick={handleSubmit}
                        >
                            Generate Color-by-Number
                        </button>
                    </section>
                </div>
            </div>
        </div>
    );
}
