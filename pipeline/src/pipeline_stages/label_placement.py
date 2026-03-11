"""
Stage 6 – Label Placement (Numbering Regions)

Responsibilities
----------------
* For each region in the cleaned region map, compute its centroid.
* If the centroid falls outside the region (concave shapes), fall back to the
  region's medoid (pixel closest to the mean).
* Skip regions whose area is too small to fit a readable number.
* Draw the palette color index (1-based) at each centroid on a copy of the
  outline image so numbers appear inside white interior areas.
* Font scale is fixed (legible at typical print sizes); the number is the
  shared palette index, so multiple disconnected regions of the same color
  all show the same digit.
* Save outputs/template_numbered.png.
"""

import cv2
import numpy as np

# Minimum region area (px²) required to place a label
MIN_LABEL_AREA = 200

# OpenCV font settings
FONT            = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE      = 0.35
FONT_THICKNESS  = 1
FONT_COLOR_BGR  = (0, 0, 0)   # black text on white interior


def _interior_anchor(region_mask: np.ndarray, outline_gray: np.ndarray) -> tuple[int, int]:
    """Return (x, y) — the point inside *region_mask* furthest from any boundary.

    Uses a distance transform on the white (interior) pixels of the outline
    masked to the current region, so the anchor is guaranteed to be:
      • inside the region
      • as far from every boundary line as possible
    Falls back to the region medoid if the distance transform yields no hit.
    """
    # Interior pixels of this region: white in outline AND belonging to this label
    interior = ((outline_gray == 255) & region_mask).astype(np.uint8)

    if interior.any():
        dist = cv2.distanceTransform(interior, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
        idx  = int(dist.argmax())
        h, w = interior.shape
        return idx % w, idx // w

    # Fallback: medoid of region pixels
    ys, xs = np.where(region_mask)
    cx, cy = float(xs.mean()), float(ys.mean())
    dists  = (xs - cx) ** 2 + (ys - cy) ** 2
    best   = int(dists.argmin())
    return int(xs[best]), int(ys[best])


def place_labels(
    outline: np.ndarray,
    clean_map: np.ndarray,
    region_color: np.ndarray,
    output_path: str | None = "outputs/template_numbered.png",
    min_label_area: int = MIN_LABEL_AREA,
) -> np.ndarray:
    """Draw palette-index numbers inside each region on a copy of *outline*.

    Parameters
    ----------
    outline:
        HxW uint8 binary image from stage 5 (0=boundary, 255=interior).
    clean_map:
        HxW int32 label map from stage 4.
    region_color:
        1D int32 array; region_color[label] = 0-based palette index.
    output_path:
        Where to save the numbered template.
    min_label_area:
        Regions smaller than this (px²) are skipped.

    Returns
    -------
    template : np.ndarray
        BGR image of the outline with numbers drawn on it.
    """
    if outline is None or outline.size == 0:
        raise ValueError("place_labels() received an empty outline image.")

    # Work on a BGR copy so we can draw coloured text if needed later
    if outline.ndim == 2:
        outline_gray = outline
        template = cv2.cvtColor(outline, cv2.COLOR_GRAY2BGR)
    else:
        outline_gray = cv2.cvtColor(outline, cv2.COLOR_BGR2GRAY)
        template = outline.copy()

    unique_labels = np.unique(clean_map)
    unique_labels = unique_labels[unique_labels > 0]

    h, w = clean_map.shape
    print(f"[labels]  Image size       : {w}×{h} px")
    print(f"[labels]  Regions to label : {len(unique_labels)}")

    labeled_count  = 0
    skipped_count  = 0

    for lbl in unique_labels:
        lbl = int(lbl)
        mask = clean_map == lbl
        area = int(mask.sum())

        if area < min_label_area:
            skipped_count += 1
            continue

        # Palette index is 0-based internally; display as 1-based
        palette_idx  = int(region_color[lbl])
        display_num  = str(palette_idx + 1)

        cx, cy = _interior_anchor(mask, outline_gray)

        # Centre the text on the centroid
        (tw, th), baseline = cv2.getTextSize(
            display_num, FONT, FONT_SCALE, FONT_THICKNESS
        )
        text_x = cx - tw // 2
        text_y = cy + th // 2

        # Clamp so text doesn't fall off the image edge
        text_x = max(0, min(w - tw - 1, text_x))
        text_y = max(th, min(h - baseline - 1, text_y))

        cv2.putText(
            template, display_num, (text_x, text_y),
            FONT, FONT_SCALE, FONT_COLOR_BGR, FONT_THICKNESS, cv2.LINE_AA
        )
        labeled_count += 1

    print(f"[labels]  Labels placed    : {labeled_count}")
    print(f"[labels]  Regions skipped  : {skipped_count}  "
          f"(area < {min_label_area} px)")

    if output_path is not None:
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(output_path, template)
        print(f"[labels]  Saved to         : {output_path}")

    return template
