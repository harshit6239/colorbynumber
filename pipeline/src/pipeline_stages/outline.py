"""
Stage 5 – Boundary Detection (Outline Extraction)

Responsibilities
----------------
* Walk every pixel in the cleaned region map; a pixel is a boundary pixel if
  any of its 4-connected neighbours belongs to a different region.
* Image-border pixels are always marked as boundary (black), giving the page
  a clean frame and ensuring every region is fully enclosed.
* Output is a strictly binary image: 0 (black) = boundary, 255 (white) = fill.
* Optionally dilate the 1-px skeleton by 1 pixel so lines are more visible in
  print or on screen.
* Save outputs/outline.png.
"""

import cv2
import numpy as np


def extract_outline(
    clean_map: np.ndarray,
    output_path: str | None = "outputs/outline.png",
    dilate: bool = False,
) -> np.ndarray:
    """Produce a binary coloring-book outline from *clean_map*.

    Parameters
    ----------
    clean_map:
        HxW int32 label array from stage 4 (cleaned region map).
    output_path:
        Where to save the outline image.
    dilate:
        If True, dilate black boundary lines by 1 px so they are bolder.

    Returns
    -------
    outline : np.ndarray
        HxW uint8 array; 0 = boundary (black), 255 = interior (white).
    """
    if clean_map is None or clean_map.size == 0:
        raise ValueError("extract_outline() received an empty or None clean_map.")

    h, w = clean_map.shape
    print(f"[outline] Image size       : {w}×{h} px")

    # ----- Boundary detection via shifted-neighbour difference ---------------
    # A pixel is a boundary pixel if its label differs from any 4-neighbour.
    # We detect this efficiently with numpy array shifts (no Python loops).

    boundary = np.zeros((h, w), dtype=bool)

    # Compare each pixel to its right / bottom / left / top neighbour.
    # Differences at the shifted edges automatically mark image-border pixels.
    boundary[:, :-1] |= clean_map[:, :-1] != clean_map[:, 1:]   # right
    boundary[:, 1:]  |= clean_map[:, 1:]  != clean_map[:, :-1]  # left
    boundary[:-1, :] |= clean_map[:-1, :] != clean_map[1:, :]   # bottom
    boundary[1:, :]  |= clean_map[1:, :]  != clean_map[:-1, :]  # top

    # Mark the image border as boundary to fully enclose all edge regions
    boundary[0, :]  = True
    boundary[-1, :] = True
    boundary[:, 0]  = True
    boundary[:, -1] = True

    # Convert to uint8: boundary → 0 (black), interior → 255 (white)
    outline = np.where(boundary, np.uint8(0), np.uint8(255))

    # ----- Optional dilation -------------------------------------------------
    if dilate:
        kernel = np.ones((3, 3), dtype=np.uint8)
        # Dilating the inverted mask (black lines = 0) is equivalent to
        # eroding the white interior, which widens the black lines.
        outline = cv2.erode(outline, kernel, iterations=1)
        print("[outline] Boundary lines dilated by 1 px.")

    # ----- Verify binary output ----------------------------------------------
    unique_vals = np.unique(outline)
    if not np.all(np.isin(unique_vals, [0, 255])):
        raise RuntimeError(
            f"[outline] ERROR: non-binary values found: {unique_vals}. "
            "This should not happen – check pipeline integrity."
        )

    n_black = int((outline == 0).sum())
    n_white = int((outline == 255).sum())
    pct_boundary = 100 * n_black / (h * w)
    print(f"[outline] Boundary pixels  : {n_black:,}  ({pct_boundary:.1f}%)")
    print(f"[outline] Interior pixels  : {n_white:,}")

    # ----- Save as 3-channel PNG for compatibility ---------------------------
    outline_bgr = cv2.cvtColor(outline, cv2.COLOR_GRAY2BGR)
    if output_path is not None:
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(output_path, outline_bgr)
        print(f"[outline] Saved to         : {output_path}")

    return outline
