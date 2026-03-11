import { Link } from "react-router-dom";

export default function Home() {
    return (
        <div className="home">
            <section className="hero">
                <div className="hero-badge">Free · No account required</div>
                <h1 className="hero-title">
                    Turn any photo into a<br />
                    paint-by-number template
                </h1>
                <p className="hero-sub">
                    Upload your image, choose the number of colors, and download
                    a printable numbered template in under two minutes.
                </p>
                <Link
                    to="/generate"
                    className="btn-primary hero-cta"
                >
                    Get started →
                </Link>
            </section>

            <section
                className="features"
                aria-label="Features"
            >
                <div className="feature-card">
                    <span
                        className="feature-icon"
                        aria-hidden="true"
                    >
                        🖼️
                    </span>
                    <h3>Upload any photo</h3>
                    <p>
                        Supports JPEG, PNG, and WebP up to 10 MB. Works with
                        portraits, landscapes, illustrations, and everything in
                        between.
                    </p>
                </div>
                <div className="feature-card">
                    <span
                        className="feature-icon"
                        aria-hidden="true"
                    >
                        🎨
                    </span>
                    <h3>Customize your palette</h3>
                    <p>
                        Choose 2–15 colors, adjust edge smoothing, and pick Fast
                        or Print quality resolution to match your needs.
                    </p>
                </div>
                <div className="feature-card">
                    <span
                        className="feature-icon"
                        aria-hidden="true"
                    >
                        📄
                    </span>
                    <h3>Download your template</h3>
                    <p>
                        Get the numbered template, a filled color preview, and a
                        color legend — all as crisp, high-quality PNGs.
                    </p>
                </div>
            </section>
        </div>
    );
}
