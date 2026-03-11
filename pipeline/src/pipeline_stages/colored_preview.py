"""
Stage 8 – Color-Filled Preview

Responsibilities
----------------
* Render a full-color preview of the completed paint-by-number so the user
  can visualize exactly what the finished painting will look like.
* Each region in the cleaned region map is filled with its palette color.
* The smoothed boundary lines are overlaid in black so the result resembles
  a finished coloring-book page.
* Saves outputs/colored_preview.png.
"""

import cv2
import numpy as np


def render_colored_preview(
    clean_map: np.ndarray,
    region_color: np.ndarray,
    palette_bgr: np.ndarray,
    outline: np.ndarray,
    output_path: str | None = "outputs/colored_preview.png",
) -> np.ndarray:
    """Generate a color-filled preview image overlaid with outlines.

    Parameters
    ----------
    clean_map:
        HxW int32 label array from stage 4.
    region_color:
        1D int32 array; region_color[label] = 0-based palette index.
    palette_bgr:
        (K, 3) uint8 palette array from stage 2.
    outline:
        HxW uint8 binary image (0=boundary, 255=interior) from stage 5 or 5b.
    output_path:
        Where to save the preview image.

    Returns
    -------
    preview : np.ndarray
        BGR color-filled image with outlines (same size as clean_map).
    """
    if clean_map is None or clean_map.size == 0:
        raise ValueError("render_colored_preview() received an empty clean_map.")

    h, w = clean_map.shape
    print(f"[preview] Image size       : {w}×{h} px")

    # Build a per-pixel color lookup: label → palette BGR
    # region_color[label] gives 0-based palette index;
    # labels 0 (background) map to white.
    max_label = int(clean_map.max())
    color_table = np.zeros((max_label + 1, 3), dtype=np.uint8)
    for lbl in range(1, max_label + 1):
        if lbl < len(region_color):
            pal_idx = int(region_color[lbl])
            if 0 <= pal_idx < len(palette_bgr):
                color_table[lbl] = palette_bgr[pal_idx]
            else:
                color_table[lbl] = (200, 200, 200)  # fallback gray
        else:
            color_table[lbl] = (200, 200, 200)

    # Fill every pixel with its region's palette color
    preview = color_table[clean_map]   # (H, W, 3) via fancy indexing

    # Overlay boundary lines in black
    if outline.ndim == 3:
        outline_gray = cv2.cvtColor(outline, cv2.COLOR_BGR2GRAY)
    else:
        outline_gray = outline
    boundary_mask = outline_gray == 0
    preview[boundary_mask] = (0, 0, 0)

    if output_path is not None:
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(output_path, preview)

    n_colors = len(np.unique(region_color[region_color >= 0]))
    print(f"[preview] Palette colors   : {len(palette_bgr)}")
    if output_path is not None:
        print(f"[preview] Saved to         : {output_path}")

    return preview
