"""
Color-by-Number pipeline entry point.

Usage
-----
    uv run main.py <image_path> [--k <num_colors>] [--smooth-sigma <sigma>] [--quality fast|print]
"""

import argparse
import base64
import io

import cv2
import numpy as np

from src import (
    preprocess, quantize, segment, merge_tiny_regions,
    extract_outline, smooth_outline, place_labels, render_palette,
    render_colored_preview,
)

# max_dimension per quality setting
QUALITY_DIMENSION = {
    "fast": 1000,
    "print": 2500,
}


def run_pipeline(
    image_bytes: bytes,
    k: int = 12,
    smooth_sigma: float = 3.0,
    quality: str = "fast",
) -> dict:
    """Run the full paint-by-number pipeline on raw image bytes.

    Parameters
    ----------
    image_bytes:
        Raw bytes of the input image (JPEG, PNG, or WEBP).
    k:
        Number of palette colors (2–32).
    smooth_sigma:
        Gaussian smoothing sigma for outlines (0 to skip).
    quality:
        "fast" (max 1000 px) or "print" (max 2500 px).

    Returns
    -------
    dict with keys:
        "template"        – base64-encoded PNG of the numbered template
        "palette"         – base64-encoded PNG of the color legend
        "colored_preview" – base64-encoded PNG of the filled preview
    """
    max_dim = QUALITY_DIMENSION.get(quality, 1000)

    # Decode bytes → numpy BGR image
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes — unsupported format or corrupted file.")

    # Stage 1 – Preprocessing
    preprocessed = preprocess(img, output_path=None, max_dimension=max_dim)
    print("[main] Pipeline stage 1 complete.")

    # Stage 2 – Color Quantization
    quantized, palette = quantize(preprocessed, k=k, output_path=None)
    print("[main] Pipeline stage 2 complete.")

    # Stage 3 – Region Segmentation
    region_map, region_color, stats, _ = segment(quantized, palette, output_path=None)
    print("[main] Pipeline stage 3 complete.")

    # Stage 4 – Merge / Remove Tiny Regions
    clean_map, clean_color = merge_tiny_regions(
        region_map, region_color, stats, palette, output_path=None
    )
    print("[main] Pipeline stage 4 complete.")

    # Stage 5 – Outline Extraction
    outline = extract_outline(clean_map, output_path=None)
    print("[main] Pipeline stage 5 complete.")

    # Stage 5b – Outline Smoothing
    if smooth_sigma > 0:
        final_outline = smooth_outline(clean_map, sigma=smooth_sigma, output_path=None)
    else:
        final_outline = outline
    print("[main] Pipeline stage 5b complete.")

    # Stage 6 – Label Placement (keep in-memory, encode directly)
    template_img = place_labels(final_outline, clean_map, clean_color, output_path=None)
    print("[main] Pipeline stage 6 complete.")

    # Stage 7 – Palette Legend (Pillow image → BytesIO)
    from PIL import Image as PilImage
    palette_bgr = render_palette(palette, output_path=None)
    palette_rgb = cv2.cvtColor(palette_bgr, cv2.COLOR_BGR2RGB)
    palette_pil = PilImage.fromarray(palette_rgb)
    palette_buf = io.BytesIO()
    palette_pil.save(palette_buf, format="PNG")
    print("[main] Pipeline stage 7 complete.")

    # Stage 8 – Colored Preview
    preview_img = render_colored_preview(clean_map, clean_color, palette, final_outline, output_path=None)
    print("[main] Pipeline stage 8 complete.")

    # Encode template and preview via cv2.imencode
    _, template_buf = cv2.imencode(".png", template_img)
    _, preview_buf = cv2.imencode(".png", preview_img)

    return {
        "template": base64.b64encode(template_buf.tobytes()).decode(),
        "palette": base64.b64encode(palette_buf.getvalue()).decode(),
        "colored_preview": base64.b64encode(preview_buf.tobytes()).decode(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Paint-by-number template generator.")
    parser.add_argument("image_path", help="Path to the input image.")
    parser.add_argument(
        "--k",
        type=int,
        default=12,
        metavar="NUM_COLORS",
        help="Number of palette colors for quantization (default: 12).",
    )
    parser.add_argument(
        "--smooth-sigma",
        type=float,
        default=3.0,
        metavar="SIGMA",
        help="Gaussian smoothing sigma for outline contours (default: 3.0; 0 to skip).",
    )
    parser.add_argument(
        "--quality",
        choices=["fast", "print"],
        default="fast",
        help="Output quality: 'fast' (1000 px max) or 'print' (2500 px max).",
    )
    args = parser.parse_args()

    with open(args.image_path, "rb") as f:
        image_bytes = f.read()

    result = run_pipeline(image_bytes, k=args.k, smooth_sigma=args.smooth_sigma, quality=args.quality)

    # Save outputs to disk for CLI usage
    import base64
    from pathlib import Path
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    for name, b64 in result.items():
        out_path = out_dir / f"{name}.png"
        out_path.write_bytes(base64.b64decode(b64))
        print(f"[main] Saved {out_path}")


if __name__ == "__main__":
    main()

