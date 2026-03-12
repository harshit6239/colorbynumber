import { useRef, useState, useCallback, useEffect } from "react";

function Slide({ beforeSrc, afterSrc, beforeLabel, afterLabel }) {
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

            <span className="ba-label ba-label--before">{beforeLabel}</span>
            <span className="ba-label ba-label--after">{afterLabel}</span>
        </div>
    );
}

export default function BeforeAfterSlider({ slides }) {
    const [current, setCurrent] = useState(0);
    const total = slides.length;

    const prev = () => setCurrent((c) => (c - 1 + total) % total);
    const next = () => setCurrent((c) => (c + 1) % total);

    return (
        <div className="ba-carousel">
            <div
                className="ba-carousel-track"
                style={{ transform: `translateX(-${current * 100}%)` }}
            >
                {slides.map((slide, i) => (
                    <div
                        className="ba-carousel-cell"
                        key={i}
                    >
                        <Slide
                            beforeSrc={slide.beforeSrc}
                            afterSrc={slide.afterSrc}
                            beforeLabel={slide.beforeLabel ?? "Original photo"}
                            afterLabel={
                                slide.afterLabel ?? "Paint-by-number template"
                            }
                        />
                    </div>
                ))}
            </div>

            {total > 1 && (
                <>
                    <button
                        className="ba-nav ba-nav--prev"
                        onClick={prev}
                        aria-label="Previous"
                    >
                        <svg
                            viewBox="0 0 20 20"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2.2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        >
                            <polyline points="13,4 7,10 13,16" />
                        </svg>
                    </button>
                    <button
                        className="ba-nav ba-nav--next"
                        onClick={next}
                        aria-label="Next"
                    >
                        <svg
                            viewBox="0 0 20 20"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2.2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        >
                            <polyline points="7,4 13,10 7,16" />
                        </svg>
                    </button>
                    <div className="ba-dots">
                        {slides.map((_, i) => (
                            <button
                                key={i}
                                className={`ba-dot${i === current ? " ba-dot--active" : ""}`}
                                onClick={() => setCurrent(i)}
                                aria-label={`Slide ${i + 1}`}
                            />
                        ))}
                    </div>
                </>
            )}
        </div>
    );
}
