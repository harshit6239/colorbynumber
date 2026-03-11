"""
Stage 3 – Region Segmentation (Connected Components)

Responsibilities
----------------
* Build an indexed image (HxW, int32) where each pixel value is its palette
  index (0..K-1), derived from the quantized image and palette.
* Run connected-component labeling (8-connectivity by default) so that each
  contiguous same-color blob becomes a unique region.
* Return:
    - region_map   : HxW int32 array of region ids (0 = background, 1..N)
    - region_color : 1D array mapping region_id → palette_index
    - stats        : OpenCV stats array (N+1, 5) with area/bounding-box data
    - centroids    : OpenCV centroids array (N+1, 2)
* Save outputs/regions.png – each region filled with a random color.
"""

import cv2
import numpy as np

# Use 8-connectivity so diagonally adjacent same-color pixels merge
CONNECTIVITY = 8


def _build_index_map(quantized: np.ndarray, palette_bgr: np.ndarray) -> np.ndarray:
    """Map every pixel in *quantized* to the index of its palette color.

    Parameters
    ----------
    quantized:
        BGR uint8 image whose pixel values are exactly entries in *palette_bgr*.
    palette_bgr:
        Array of shape (K, 3) – the palette colors in BGR uint8.

    Returns
    -------
    index_map : np.ndarray
        HxW int32 array; each value is the row index into *palette_bgr*.
    """
    h, w = quantized.shape[:2]
    # Reshape to (N, 3) and broadcast-compare against palette (K, 3)
    flat = quantized.reshape(-1, 3).astype(np.int32)           # (N, 3)
    pal  = palette_bgr.astype(np.int32)                        # (K, 3)
    # Squared distances: (N, K)
    diffs = flat[:, None, :] - pal[None, :, :]                 # (N, K, 3)
    dist2 = (diffs ** 2).sum(axis=2)                           # (N, K)
    index_map = dist2.argmin(axis=1).reshape(h, w).astype(np.int32)
    return index_map


def segment(
    quantized: np.ndarray,
    palette_bgr: np.ndarray,
    connectivity: int = CONNECTIVITY,
    output_path: str | None = "outputs/regions.png",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Identify connected same-color regions in *quantized*.

    Parameters
    ----------
    quantized:
        BGR uint8 image from the quantization stage.
    palette_bgr:
        Array of shape (K, 3) BGR uint8 palette returned by quantize().
    connectivity:
        4 or 8 – connectivity for connected-component analysis.
    output_path:
        Where to save the debug visualization.

    Returns
    -------
    region_map : np.ndarray
        HxW int32 label array.  Label 0 is the background (unused here);
        labels 1..N are region ids.
    region_color : np.ndarray
        1D int32 array of length N+1.  region_color[label] gives the palette
        index for that region (region_color[0] is undefined / -1).
    stats : np.ndarray
        OpenCV stats matrix of shape (N+1, 5):
        columns are [x, y, width, height, area] per label.
    centroids : np.ndarray
        OpenCV centroids matrix of shape (N+1, 2): [cx, cy] per label.
    """
    if quantized is None or quantized.size == 0:
        raise ValueError("segment() received an empty or None image.")
    if palette_bgr.ndim != 2 or palette_bgr.shape[1] != 3:
        raise ValueError("palette_bgr must be shape (K, 3).")

    h, w = quantized.shape[:2]
    k = len(palette_bgr)
    print(f"[segment] Image size       : {w}×{h} px")
    print(f"[segment] Palette size     : {k} colors")
    print(f"[segment] Connectivity     : {connectivity}")

    # --- Step 1: build per-pixel palette index map -------------------------
    index_map = _build_index_map(quantized, palette_bgr)  # HxW, values 0..K-1

    # --- Step 2: connected components for each palette color ---------------
    # We'll accumulate a global label map.  For each palette index we run
    # connectedComponentsWithStats on the binary mask, then offset the labels
    # so they don't collide across colors.
    region_map   = np.zeros((h, w), dtype=np.int32)
    # region_color[label] = palette index; pre-allocate generously
    region_color_list: list[int] = [-1]  # index 0 → undefined
    next_label = 1

    for color_idx in range(k):
        mask = (index_map == color_idx).astype(np.uint8)  # binary mask
        if not mask.any():
            continue  # this palette color is absent from the image
        n_labels, labels, stats, centroids_cc = cv2.connectedComponentsWithStats(
            mask, connectivity=connectivity, ltype=cv2.CV_32S
        )
        # labels: 0 = background (pixels NOT in this color mask), 1..n_labels-1 = blobs
        for local_id in range(1, n_labels):
            global_label = next_label
            region_map[labels == local_id] = global_label
            region_color_list.append(color_idx)
            next_label += 1

    n_regions = next_label - 1
    region_color = np.array(region_color_list, dtype=np.int32)

    print(f"[segment] Regions found    : {n_regions:,}")

    # --- Step 3: compute stats & centroids for the global label map --------
    # Re-run connectedComponentsWithStats on the full label map encoded as a
    # single-channel image.  Since region_map already has unique ids we just
    # need per-region bounding boxes; we compute them directly from the map.
    # Use numpy for speed – build stats array [x, y, w, h, area].
    stats_list     = [np.array([0, 0, 0, 0, 0])]  # label 0 placeholder
    centroids_list = [np.array([0.0, 0.0])]        # label 0 placeholder

    ys, xs = np.mgrid[0:h, 0:w]
    for lbl in range(1, next_label):
        mask = region_map == lbl
        pixel_xs = xs[mask]
        pixel_ys = ys[mask]
        area = int(mask.sum())
        x0, x1 = int(pixel_xs.min()), int(pixel_xs.max())
        y0, y1 = int(pixel_ys.min()), int(pixel_ys.max())
        cx = float(pixel_xs.mean())
        cy = float(pixel_ys.mean())
        stats_list.append(np.array([x0, y0, x1 - x0 + 1, y1 - y0 + 1, area]))
        centroids_list.append(np.array([cx, cy]))

    stats     = np.stack(stats_list).astype(np.int32)      # (N+1, 5)
    centroids = np.stack(centroids_list).astype(np.float64) # (N+1, 2)

    # --- Step 4: debug visualisation – random color per region -------------
    rng = np.random.default_rng(seed=42)
    # color table: label 0 → black background, each region → random BGR
    color_table = np.zeros((next_label, 3), dtype=np.uint8)
    color_table[1:] = rng.integers(0, 256, size=(n_regions, 3), dtype=np.uint8)

    vis = color_table[region_map]  # (H, W, 3) via fancy indexing

    if output_path is not None:
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(output_path, vis)
        print(f"[segment] Saved to         : {output_path}")

    return region_map, region_color, stats, centroids
