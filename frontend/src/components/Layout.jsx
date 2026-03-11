import { useState } from "react";
import { Outlet, NavLink } from "react-router-dom";

export default function Layout() {
    const [dark, setDark] = useState(() => {
        const stored = localStorage.getItem("cbn_dark");
        const isDark =
            stored !== null
                ? stored === "true"
                : window.matchMedia("(prefers-color-scheme: dark)").matches;
        // Apply immediately in the initializer to avoid a flash on first render.
        document.documentElement.setAttribute(
            "data-theme",
            isDark ? "dark" : "light",
        );
        return isDark;
    });

    function toggle() {
        setDark((d) => {
            const next = !d;
            document.documentElement.setAttribute(
                "data-theme",
                next ? "dark" : "light",
            );
            localStorage.setItem("cbn_dark", next);
            return next;
        });
    }

    const linkClass = ({ isActive }) => `nav-link${isActive ? " active" : ""}`;

    return (
        <>
            <nav className="nav">
                <NavLink
                    to="/"
                    className="nav-logo"
                >
                    <span
                        className="nav-logo-icon"
                        aria-hidden="true"
                    >
                        #
                    </span>
                    Color by Number
                </NavLink>

                <div className="nav-links">
                    <NavLink
                        to="/"
                        end
                        className={linkClass}
                    >
                        Home
                    </NavLink>
                    <NavLink
                        to="/generate"
                        className={linkClass}
                    >
                        Generate
                    </NavLink>
                    <NavLink
                        to="/support"
                        className={linkClass}
                    >
                        ☕ Support
                    </NavLink>
                </div>

                <button
                    className="dark-toggle"
                    onClick={toggle}
                    aria-label={
                        dark ? "Switch to light mode" : "Switch to dark mode"
                    }
                    title={dark ? "Light mode" : "Dark mode"}
                >
                    {dark ? "☀️" : "🌙"}
                </button>
            </nav>

            <main>
                <Outlet />
            </main>
        </>
    );
}
