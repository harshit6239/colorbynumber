"""
Stage 5b – Outline Smoothing

Responsibilities
----------------
* Take the raw pixel-boundary outline (and the underlying region map) and
  produce visually smoother, more hand-drawn-looking boundary curves.
* Method: for every region in the cleaned region map, extract the OpenCV
  contour(s) of its binary mask, smooth the contour-point coordinates with a
  1-D Gaussian kernel (applied separately to x and y), then redraw the
  smoothed polylines on a white canvas.
* The Gaussian sigma controls the amount of smoothing (larger = smoother,
  but too large rounds sharp corners).
* Saves outputs/outline_smooth.png.
"""

import cv2
import numpy as np

DEFAULT_SIGMA      = 3.0    # Gaussian smoothing sigma (contour coords)
MIN_CONTOUR_LEN    = 5      # skip contours shorter than this (noise)
LINE_THICKNESS     = 1


def _gaussian_kernel(sigma: float) -> np.ndarray:
    """Return a 1-D Gaussian kernel for the given sigma (truncated at 4σ)."""
    radius = max(2, int(round(4 * sigma)))
    x = np.arange(-radius, radius + 1, dtype=np.float64)
    k = np.exp(-0.5 * (x / sigma) ** 2)
    return k / k.sum()


def _smooth_contour(pts: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """Smooth an Nx1x2 OpenCV contour array using a 1-D Gaussian.

    The contour is treated as periodic (wrap-around convolution) so the
    start/end join is also smooth for closed loops.
    """
    pts = pts[:, 0, :]                             # (N, 2)
    n   = len(pts)
    if n < len(kernel):
        return pts                                 # too short to smooth

    xs = np.convolve(np.tile(pts[:, 0], 3), kernel, mode="same")[n:2*n]
    ys = np.convolve(np.tile(pts[:, 1], 3), kernel, mode="same")[n:2*n]
    return np.stack([xs, ys], axis=1)


def smooth_outline(
    clean_map: np.ndarray,
    sigma: float = DEFAULT_SIGMA,
    output_path: str | None = "outputs/outline_smooth.png",
) -> np.ndarray:
    """Produce a smooth coloring-book outline from *clean_map*.

    Parameters
    ----------
    clean_map:
        HxW int32 label array from stage 4 (cleaned region map).
    sigma:
        Gaussian smoothing strength for contour coordinates.
        Values 1–3 give subtle smoothing; 4–8 give rounder curves.
    output_path:
        Where to save the smoothed outline image.

    Returns
    -------
    smooth : np.ndarray
        HxW uint8 array; 0 = boundary (black), 255 = interior (white).
    """
    if clean_map is None or clean_map.size == 0:
        raise ValueError("smooth_outline() received an empty clean_map.")

    h, w = clean_map.shape
    kernel = _gaussian_kernel(sigma)

    # Start with a white canvas – boundaries will be drawn in black
    canvas = np.full((h, w), 255, dtype=np.uint8)

    unique_labels = np.unique(clean_map)
    unique_labels = unique_labels[unique_labels > 0]

    print(f"[smooth]  Image size       : {w}×{h} px")
    print(f"[smooth]  Sigma            : {sigma}")
    print(f"[smooth]  Regions          : {len(unique_labels)}")

    total_contours = 0
    for lbl in unique_labels:
        mask = (clean_map == lbl).astype(np.uint8) * 255
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
        )
        for cnt in contours:
            if len(cnt) < MIN_CONTOUR_LEN:
                continue
            smooth_pts = _smooth_contour(cnt, kernel)
            poly = np.round(smooth_pts).astype(np.int32).reshape(-1, 1, 2)
            cv2.polylines(canvas, [poly], isClosed=True,
                          color=0, thickness=LINE_THICKNESS)
            total_contours += 1

    # Always blacken the image border so every edge region is enclosed
    canvas[0, :]  = 0
    canvas[-1, :] = 0
    canvas[:, 0]  = 0
    canvas[:, -1] = 0

    n_black = int((canvas == 0).sum())
    print(f"[smooth]  Contours drawn   : {total_contours}")
    print(f"[smooth]  Boundary pixels  : {n_black:,}  "
          f"({100 * n_black / (h * w):.1f}%)")

    outline_bgr = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
    if output_path is not None:
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(output_path, outline_bgr)
        print(f"[smooth]  Saved to         : {output_path}")

    return canvas
