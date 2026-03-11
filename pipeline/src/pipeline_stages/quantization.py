"""
Stage 2 – Color Quantization (Palette Extraction)

Responsibilities
----------------
* Reduce the image to K distinct colors via K-Means clustering.
* Return the quantized image (every pixel replaced by its nearest cluster
  center) and the palette as an array of BGR integer triples.
* Warn when K exceeds the number of unique colors in the image.
* Save outputs/quantized.png for visual inspection.
"""

import cv2
import numpy as np
from sklearn.cluster import KMeans, MiniBatchKMeans

# Tunable constants
DEFAULT_K = 12
# Pixel count above which MiniBatchKMeans is used automatically for speed
MINIBATCH_THRESHOLD = 150_000


def quantize(
    img: np.ndarray,
    k: int = DEFAULT_K,
    output_path: str | None = "outputs/quantized.png",
    random_state: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Quantize *img* to *k* colors using K-Means clustering.

    Parameters
    ----------
    img:
        Preprocessed BGR image (uint8, HxWx3).
    k:
        Number of target palette colors (clusters).
    output_path:
        Where to save the quantized image for inspection.
    random_state:
        Random seed for reproducibility.

    Returns
    -------
    quantized : np.ndarray
        BGR image of the same shape as *img*, every pixel replaced by its
        nearest palette color (uint8).
    palette_bgr : np.ndarray
        Array of shape (k_actual, 3) – the palette colors as BGR uint8 values.
        k_actual ≤ k when the image has fewer unique colors than k.
    """
    if img is None or img.size == 0:
        raise ValueError("quantize() received an empty or None image.")

    h, w = img.shape[:2]
    n_pixels = h * w
    print(f"[quantize] Image size      : {w}×{h} px ({n_pixels:,} pixels)")

    # --- Clamp K to the number of unique colors ----------------------------
    pixels_rgb = img.reshape(-1, 3)  # (N, 3) BGR
    unique_colors = np.unique(pixels_rgb, axis=0)
    n_unique = len(unique_colors)
    if n_unique < k:
        print(
            f"[quantize] WARNING: K={k} exceeds unique colors ({n_unique}). "
            f"Clamping K to {n_unique}."
        )
        k = n_unique

    print(f"[quantize] K               : {k}")
    print(f"[quantize] Unique colors   : {n_unique:,}")

    # --- Choose KMeans variant based on image size -------------------------
    use_minibatch = n_pixels > MINIBATCH_THRESHOLD
    algo_name = "MiniBatchKMeans" if use_minibatch else "KMeans"
    print(f"[quantize] Algorithm       : {algo_name}")

    pixels_float = pixels_rgb.astype(np.float32)

    if use_minibatch:
        km = MiniBatchKMeans(n_clusters=k, random_state=random_state, n_init=3)
    else:
        km = KMeans(n_clusters=k, random_state=random_state, n_init=10)

    labels = km.fit_predict(pixels_float)           # (N,) int cluster ids
    centers = np.round(km.cluster_centers_).astype(np.uint8)  # (K, 3) BGR

    # --- Report cluster sizes (ensure no empty cluster) --------------------
    cluster_sizes = np.bincount(labels, minlength=k)
    empty_clusters = np.where(cluster_sizes == 0)[0]
    if empty_clusters.size:
        print(
            f"[quantize] WARNING: {empty_clusters.size} empty cluster(s) detected "
            f"(indices {empty_clusters.tolist()}). Consider rerunning with a lower K."
        )
    print("[quantize] Cluster sizes   :")
    for idx, size in enumerate(cluster_sizes):
        pct = 100 * size / n_pixels
        b, g, r = centers[idx]
        print(f"           Color {idx+1:>2d}  BGR=({b:3d},{g:3d},{r:3d})  "
              f"{size:>8,} px  ({pct:5.1f}%)")

    # --- Reconstruct quantized image ---------------------------------------
    quantized_flat = centers[labels]                # (N, 3)
    quantized = quantized_flat.reshape(h, w, 3)     # (H, W, 3)

    # --- Save for inspection -----------------------------------------------
    if output_path is not None:
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(output_path, quantized)
        print(f"[quantize] Saved to        : {output_path}")

    return quantized, centers
