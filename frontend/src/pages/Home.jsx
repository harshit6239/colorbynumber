import { Link } from "react-router-dom";
import BeforeAfterSlider from "../components/BeforeAfterSlider";

export default function Home() {
    return (
        <div className="home">
            <section className="hero">
                <span className="hero-eyebrow">Free · No account required</span>

                <h1 className="hero-title">
                    Craft color from
                    <br />
                    <em>any photograph</em>
                </h1>

                <p className="hero-sub">
                    HueCraft transforms your photos into printable
                    paint-by-number templates — numbered regions, palette
                    legend, and a color preview, all in seconds.
                </p>

                <div className="hero-actions">
                    <Link
                        to="/generate"
                        className="hero-cta"
                    >
                        Start crafting
                        <svg
                            viewBox="0 0 24 24"
                            xmlns="http://www.w3.org/2000/svg"
                        >
                            <line
                                x1="5"
                                y1="12"
                                x2="19"
                                y2="12"
                            />
                            <polyline points="12 5 19 12 12 19" />
                        </svg>
                    </Link>
                    <Link
                        to="/support"
                        className="hero-cta-ghost"
                    >
                        Support the project
                    </Link>
                </div>
            </section>

            <section className="ba-section">
                <p className="ba-section-eyebrow">See the difference</p>
                <h2 className="ba-section-headline">
                    From photo to paint-by-number
                </h2>
                <BeforeAfterSlider
                    slides={[
                        { beforeSrc: "/Before1.png", afterSrc: "/After1.png" },
                        { beforeSrc: "/Before2.jpg", afterSrc: "/After2.png" },
                    ]}
                />
            </section>

            <section
                className="features"
                aria-label="How it works"
            >
                <div className="feature-step">
                    <span
                        className="step-number"
                        aria-hidden="true"
                    >
                        1
                    </span>
                    <h3>Upload any photo</h3>
                    <p>
                        JPEG, PNG, or WebP up to 10 MB. Portraits, landscapes,
                        illustrations — HueCraft handles them all.
                    </p>
                </div>
                <div className="feature-step">
                    <span
                        className="step-number"
                        aria-hidden="true"
                    >
                        2
                    </span>
                    <h3>Craft your palette</h3>
                    <p>
                        Choose 2–15 colors, tune edge smoothing, and pick Fast
                        or Print resolution to match your canvas.
                    </p>
                </div>
                <div className="feature-step">
                    <span
                        className="step-number"
                        aria-hidden="true"
                    >
                        3
                    </span>
                    <h3>Download & paint</h3>
                    <p>
                        Get your numbered template, color preview, and legend —
                        crisp, print-ready PNGs, ready to paint.
                    </p>
                </div>
            </section>
        </div>
    );
}
