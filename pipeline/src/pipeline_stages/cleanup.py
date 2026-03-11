"""
Stage 4 – Merge / Remove Tiny Regions

Responsibilities
----------------
* Compute an adaptive minimum-area threshold that balances two signals:
    1. Image-size fraction  -- min_area = (H*W) / AREA_DENOM  (~0.05 % of image)
    2. Median-region fraction -- min_area = median_area / MEDIAN_DENOM (1/10 of median)
  The final threshold is the MINIMUM of the two, then clamped so it never
  exceeds 1 % of the image (prevents erasing meaningful regions on simple or
  low-resolution images) and is always at least 1 px.
* For each region below the threshold, reassign its pixels to the most
  common neighboring region id (boundary-neighbor merge).
* After merging the region_map changes but retains the same coordinate frame;
  region_color is updated accordingly.
* Print counts before and after so the user can judge the cleanup.
* Save outputs/regions_clean.png -- same random-colour visualization as
  stage 3 but for the cleaned map.
"""

import cv2
import numpy as np

# --- Threshold constants ----------------------------------------------------
# Image-fraction method: min_area = (H*W) // AREA_DENOM  (~0.05 %)
AREA_DENOM = 2000

# Median-fraction method: min_area = median_area // MEDIAN_DENOM
MEDIAN_DENOM = 10

# Hard upper cap: never remove a region larger than this share of the image.
# Prevents wiping meaningful shapes on simple / low-res images.
MAX_AREA_FRACTION = 0.01   # 1 %


def _compute_min_area(unique_labels: np.ndarray, stats: np.ndarray,
                      h: int, w: int) -> int:
    """Return an adaptive minimum-area threshold.

    Strategy
    --------
    1. Image-size fraction   : img_thresh    = (H*W) // AREA_DENOM
    2. Median-region fraction: median_thresh = median(areas) // MEDIAN_DENOM
    3. Take the MAXIMUM of the two:
       - On noisy images the median is tiny, so img_thresh dominates → cleans up speckles.
       - On clean images with few large blobs the median may be large, giving a
         proportionally bigger threshold that still only removes minor fragments.
    4. Clamp to [1, MAX_AREA_FRACTION * H * W] so we never erase real regions.
    """
    n_pixels = h * w
    img_thresh = max(1, n_pixels // AREA_DENOM)

    areas = stats[unique_labels, 4]
    median_area = float(np.median(areas)) if len(areas) > 0 else 1.0
    median_thresh = max(1, int(median_area // MEDIAN_DENOM))

    raw = max(img_thresh, median_thresh)

    # Hard cap: never exceed 1 % of image so real regions survive
    cap = max(1, int(n_pixels * MAX_AREA_FRACTION))
    return max(1, min(raw, cap))


def _neighbor_region(region_map: np.ndarray, lbl: int) -> int:
    """Return the most common region id that borders *lbl*.

    Looks at the 8 direct neighbours of every pixel belonging to *lbl* and
    picks the most frequent non-*lbl*, non-zero label.
    Returns *lbl* itself if no external neighbour exists (e.g. entire image).
    """
    mask = (region_map == lbl).astype(np.uint8)
    dilated = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
    border_mask = (dilated == 1) & (region_map != lbl)
    neighbour_labels = region_map[border_mask]
    neighbour_labels = neighbour_labels[neighbour_labels != 0]
    if neighbour_labels.size == 0:
        return lbl
    counts = np.bincount(neighbour_labels)
    return int(counts.argmax())


def merge_tiny_regions(
    region_map: np.ndarray,
    region_color: np.ndarray,
    stats: np.ndarray,
    palette_bgr: np.ndarray,
    area_denom: int = AREA_DENOM,
    output_path: str | None = "outputs/regions_clean.png",
) -> tuple[np.ndarray, np.ndarray]:
    """Remove regions smaller than an adaptive threshold by merging them into
    their dominant neighbour.

    Parameters
    ----------
    region_map:
        HxW int32 label array from stage 3.
    region_color:
        1D int32 array; region_color[label] = palette index.
    stats:
        (N+1, 5) array [x, y, w, h, area] per label from stage 3.
    palette_bgr:
        (K, 3) uint8 palette array from stage 2.
    area_denom:
        Denominator for the image-fraction threshold (overrides AREA_DENOM).
    output_path:
        Where to save the cleaned debug visualization.

    Returns
    -------
    clean_map : np.ndarray
        Updated HxW int32 label array (same label ids, some reassigned).
    clean_color : np.ndarray
        Updated region_color array reflecting any reassignments.
    """
    if region_map is None or region_map.size == 0:
        raise ValueError("merge_tiny_regions() received an empty region_map.")

    h, w = region_map.shape
    unique_labels = np.unique(region_map)
    unique_labels = unique_labels[unique_labels > 0]
    n_before = len(unique_labels)

    min_area = _compute_min_area(unique_labels, stats, h, w)

    areas = stats[unique_labels, 4]
    median_area = float(np.median(areas)) if len(areas) > 0 else 0.0

    print(f"[cleanup] Image size       : {w}x{h} px")
    print(f"[cleanup] Regions before   : {n_before:,}")
    print(f"[cleanup] Median area      : {median_area:.1f} px")
    print(f"[cleanup] img_thresh       : {max(1, (h*w)//area_denom)} px  (image / {area_denom})")
    print(f"[cleanup] median_thresh    : {max(1, int(median_area//MEDIAN_DENOM))} px  (median / {MEDIAN_DENOM})")
    cap = max(1, int((h * w) * MAX_AREA_FRACTION))
    print(f"[cleanup] hard cap         : {cap} px  ({MAX_AREA_FRACTION*100:.1f}% of image)")
    print(f"[cleanup] -> min_area used : {min_area} px")

    clean_map   = region_map.copy()
    clean_color = region_color.copy()

    order = unique_labels[np.argsort(areas)]  # ascending area

    merged_count = 0
    for lbl in order:
        lbl = int(lbl)
        current_area = int((clean_map == lbl).sum())
        if current_area == 0:
            continue  # already merged away
        if current_area >= min_area:
            continue  # large enough -- keep

        # Guard: never merge the last remaining region
        surviving = np.unique(clean_map)
        surviving = surviving[surviving > 0]
        if len(surviving) <= 1:
            break

        target = _neighbor_region(clean_map, lbl)
        if target == lbl:
            continue  # no neighbours; skip

        clean_map[clean_map == lbl] = target
        merged_count += 1

    unique_after = np.unique(clean_map)
    unique_after = unique_after[unique_after > 0]
    n_after = len(unique_after)

    print(f"[cleanup] Regions merged   : {merged_count:,}")
    print(f"[cleanup] Regions after    : {n_after:,}")

    # --- Debug visualisation -----------------------------------------------
    max_label = int(clean_map.max())
    rng = np.random.default_rng(seed=42)
    color_table = np.zeros((max_label + 1, 3), dtype=np.uint8)
    color_table[1:] = rng.integers(0, 256, size=(max_label, 3), dtype=np.uint8)
    vis = color_table[clean_map]

    if output_path is not None:
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(output_path, vis)
        print(f"[cleanup] Saved to         : {output_path}")

    return clean_map, clean_color
