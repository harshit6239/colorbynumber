import { useState } from "react";
import { Outlet, NavLink } from "react-router-dom";

const SunIcon = () => (
    <svg
        viewBox="0 0 24 24"
        xmlns="http://www.w3.org/2000/svg"
    >
        <circle
            cx="12"
            cy="12"
            r="4.5"
        />
        <line
            x1="12"
            y1="2"
            x2="12"
            y2="4.5"
        />
        <line
            x1="12"
            y1="19.5"
            x2="12"
            y2="22"
        />
        <line
            x1="4.22"
            y1="4.22"
            x2="5.98"
            y2="5.98"
        />
        <line
            x1="18.02"
            y1="18.02"
            x2="19.78"
            y2="19.78"
        />
        <line
            x1="2"
            y1="12"
            x2="4.5"
            y2="12"
        />
        <line
            x1="19.5"
            y1="12"
            x2="22"
            y2="12"
        />
        <line
            x1="4.22"
            y1="19.78"
            x2="5.98"
            y2="18.02"
        />
        <line
            x1="18.02"
            y1="5.98"
            x2="19.78"
            y2="4.22"
        />
    </svg>
);

const MoonIcon = () => (
    <svg
        viewBox="0 0 24 24"
        xmlns="http://www.w3.org/2000/svg"
    >
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
);

export default function Layout() {
    const [dark, setDark] = useState(() => {
        const stored = localStorage.getItem("cbn_dark");
        const isDark =
            stored !== null
                ? stored === "true"
                : window.matchMedia("(prefers-color-scheme: dark)").matches;
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
                    <span className="nav-logo-wordmark">
                        Hue<span>Craft</span>
                    </span>
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
                        Support
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
                    {dark ? <SunIcon /> : <MoonIcon />}
                </button>
            </nav>

            <main>
                <Outlet />
            </main>
        </>
    );
}
