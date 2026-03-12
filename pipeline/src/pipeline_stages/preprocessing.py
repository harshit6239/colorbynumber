"""
Stage 1 – Preprocessing & Size Normalization

Responsibilities
----------------
* Validate the input image meets a minimum size requirement.
* Downscale oversized images so the largest dimension ≤ MAX_DIMENSION,
  preserving aspect ratio.
* Apply a mild Gaussian blur to suppress high-frequency noise.
* Save the result to outputs/preprocessed.png for visual inspection.
"""

import cv2
import numpy as np

# Tunable constants
MAX_DIMENSION = 1000   # px – images larger than this are downscaled
MIN_DIMENSION = 50     # px – images smaller than this trigger a warning
BLUR_KERNEL = (7, 7)   # Gaussian kernel; must be odd × odd


def _resize_to_max(img: np.ndarray, max_dim: int) -> np.ndarray:
    """Return a copy of *img* scaled so its largest side equals *max_dim*.

    Does nothing when the image already fits within *max_dim*.
    """
    h, w = img.shape[:2]
    largest = max(h, w)
    if largest <= max_dim:
        return img
    scale = max_dim / largest
    new_w = max(1, round(w * scale))
    new_h = max(1, round(h * scale))
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


def preprocess(
    img: np.ndarray,
    output_path: str | None = "outputs/preprocessed.png",
    max_dimension: int = MAX_DIMENSION,
    min_dimension: int = MIN_DIMENSION,
    blur_kernel: tuple[int, int] = BLUR_KERNEL,
) -> np.ndarray:
    """Preprocess *img* for the paint-by-number pipeline.

    Parameters
    ----------
    img:
        Input BGR image as a NumPy array (loaded with cv2.imread or similar).
    output_path:
        Where to save the preprocessed image for inspection.
    max_dimension:
        Downscale the image if its largest side exceeds this value.
    min_dimension:
        Emit a warning when either dimension is smaller than this value.
    blur_kernel:
        Gaussian kernel size (width, height) – both values must be odd.

    Returns
    -------
    np.ndarray
        Preprocessed BGR image.
    """
    if img is None or img.size == 0:
        raise ValueError("preprocess() received an empty or None image.")

    orig_h, orig_w = img.shape[:2]
    print(f"[preprocess] Original size : {orig_w}×{orig_h} px")

    # --- Minimum size guard ------------------------------------------------
    if orig_h < min_dimension or orig_w < min_dimension:
        print(
            f"[preprocess] WARNING: image is very small ({orig_w}×{orig_h} px). "
            f"Regions may be unreliable. Consider supplying a larger image "
            f"(minimum recommended: {min_dimension}×{min_dimension} px)."
        )

    # --- Scale down oversized images ---------------------------------------
    resized = _resize_to_max(img, max_dimension)
    new_h, new_w = resized.shape[:2]
    if (new_h, new_w) != (orig_h, orig_w):
        print(f"[preprocess] Resized to    : {new_w}×{new_h} px")
    else:
        print(f"[preprocess] No resize needed (image fits within {max_dimension} px).")

    # --- Gaussian smoothing ------------------------------------------------
    blurred = cv2.GaussianBlur(resized, blur_kernel, 0)
    print(f"[preprocess] Gaussian blur : kernel={blur_kernel}")

    # --- Save for inspection -----------------------------------------------
    if output_path is not None:
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(output_path, blurred)
        print(f"[preprocess] Saved to      : {output_path}")

    return blurred
