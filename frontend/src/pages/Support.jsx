export default function Support() {
    return (
        <div className="page">
            <div className="container support-container">
                <div className="support-hero">
                    <span
                        className="support-icon"
                        aria-hidden="true"
                    >
                        ☕
                    </span>
                    <h1 className="page-heading">Buy me a coffee</h1>
                    <p className="support-sub">
                        Color by Number is free and will stay that way. If it
                        saved you time or made your weekend art project more
                        fun, a coffee keeps the server lights on.
                    </p>
                </div>

                <div className="support-grid">
                    {/* Donation card */}
                    <div className="card support-card">
                        <h2 className="support-card-title">
                            Support the project
                        </h2>
                        <p className="support-card-desc">
                            Every contribution — big or small — helps cover
                            hosting costs and motivates future improvements like
                            more palette options, SVG export, and print-ready
                            layouts.
                        </p>

                        <div className="bmc-tiers">
                            <a
                                href="https://www.buymeacoffee.com"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="bmc-btn"
                            >
                                <span aria-hidden="true">☕</span> Buy me a
                                coffee — $5
                            </a>
                            <a
                                href="https://www.buymeacoffee.com"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="bmc-btn bmc-btn--muted"
                            >
                                <span aria-hidden="true">🍕</span> Buy me a
                                pizza — $10
                            </a>
                        </div>

                        <p className="bmc-note">
                            You'll be redirected to Buy Me a Coffee — no account
                            needed, card or PayPal accepted.
                        </p>
                    </div>

                    {/* What it funds */}
                    <div className="card support-card">
                        <h2 className="support-card-title">
                            What your support funds
                        </h2>
                        <ul className="fund-list">
                            <li>
                                <span
                                    className="fund-icon"
                                    aria-hidden="true"
                                >
                                    🖥
                                </span>
                                <div>
                                    <strong>Hosting</strong>
                                    <p>
                                        Pipeline and backend run on Render.
                                        Processing images costs real compute.
                                    </p>
                                </div>
                            </li>
                            <li>
                                <span
                                    className="fund-icon"
                                    aria-hidden="true"
                                >
                                    ⚡
                                </span>
                                <div>
                                    <strong>Faster processing</strong>
                                    <p>
                                        Upgraded instances so your template
                                        generates in seconds, not minutes.
                                    </p>
                                </div>
                            </li>
                            <li>
                                <span
                                    className="fund-icon"
                                    aria-hidden="true"
                                >
                                    🎨
                                </span>
                                <div>
                                    <strong>New features</strong>
                                    <p>
                                        SVG export, custom palettes, printable
                                        PDFs, and more on the roadmap.
                                    </p>
                                </div>
                            </li>
                            <li>
                                <span
                                    className="fund-icon"
                                    aria-hidden="true"
                                >
                                    🔓
                                </span>
                                <div>
                                    <strong>Stays free</strong>
                                    <p>
                                        No paywalls, no sign-ups. Support is
                                        optional — always.
                                    </p>
                                </div>
                            </li>
                        </ul>
                    </div>
                </div>

                <p className="support-thanks">
                    Thank you for using Color by Number. ❤️
                </p>
            </div>
        </div>
    );
}
