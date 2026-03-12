import { useRef, useState, useCallback, useEffect } from "react";

export default function BeforeAfterSlider({
    beforeSrc,
    afterSrc,
    beforeLabel = "Original photo",
    afterLabel = "Paint-by-number template",
}) {
    const [pos, setPos] = useState(50);
    const containerRef = useRef(null);
    const dragging = useRef(false);

    const calc = useCallback((clientX) => {
        const r = containerRef.current.getBoundingClientRect();
        setPos(
            Math.min(100, Math.max(0, ((clientX - r.left) / r.width) * 100)),
        );
    }, []);

    useEffect(() => {
        const move = (e) => {
            if (dragging.current) calc(e.clientX);
        };
        const tMove = (e) => {
            if (dragging.current) calc(e.touches[0].clientX);
        };
        const up = () => {
            dragging.current = false;
        };
        window.addEventListener("mousemove", move);
        window.addEventListener("mouseup", up);
        window.addEventListener("touchmove", tMove, { passive: true });
        window.addEventListener("touchend", up);
        return () => {
            window.removeEventListener("mousemove", move);
            window.removeEventListener("mouseup", up);
            window.removeEventListener("touchmove", tMove);
            window.removeEventListener("touchend", up);
        };
    }, [calc]);

    const onStart = (clientX) => {
        dragging.current = true;
        calc(clientX);
    };

    return (
        <div
            className="ba-slider"
            ref={containerRef}
            onMouseDown={(e) => {
                e.preventDefault();
                onStart(e.clientX);
            }}
            onTouchStart={(e) => onStart(e.touches[0].clientX)}
        >
            {/* After — full width, sits beneath */}
            <div className="ba-pane ba-pane--after">
                {afterSrc ? (
                    <img
                        src={afterSrc}
                        alt={afterLabel}
                        draggable={false}
                    />
                ) : (
                    <div className="ba-demo ba-demo--after" />
                )}
            </div>

            {/* Before — clipped to the left of the handle */}
            <div
                className="ba-pane ba-pane--before"
                style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }}
            >
                {beforeSrc ? (
                    <img
                        src={beforeSrc}
                        alt={beforeLabel}
                        draggable={false}
                    />
                ) : (
                    <div className="ba-demo ba-demo--before" />
                )}
            </div>

            {/* Divider line + drag knob */}
            <div
                className="ba-divider"
                style={{ left: `${pos}%` }}
            >
                <div
                    className="ba-knob"
                    onMouseDown={(e) => {
                        e.stopPropagation();
                        e.preventDefault();
                        onStart(e.clientX);
                    }}
                    onTouchStart={(e) => {
                        e.stopPropagation();
                        onStart(e.touches[0].clientX);
                    }}
                >
                    <svg
                        viewBox="0 0 20 20"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                    >
                        <polyline points="6,4 2,10 6,16" />
                        <polyline points="14,4 18,10 14,16" />
                    </svg>
                </div>
            </div>

            {/* Labels */}
            <span className="ba-label ba-label--before">{beforeLabel}</span>
            <span className="ba-label ba-label--after">{afterLabel}</span>
        </div>
    );
}
