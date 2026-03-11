"""
Stage 7 – Color Legend (Palette Output)

Responsibilities
----------------
* Render a high-quality palette reference image using Pillow so text is
  crisp and anti-aliased at any scale.
* Renders at 3× resolution then downsamples with LANCZOS for print quality.
* Text color (black or white) is chosen automatically based on perceived
  luminance so it is always legible over every swatch.
* Save outputs/palette.png.
"""

import cv2
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Layout constants at 1× (px) — rendered at SCALE× internally
SWATCH_W   = 60    # color swatch width
SWATCH_H   = 44    # color swatch height
CAPTION_W  = 200   # space for hex + RGB caption to the right of swatch
ROW_PAD    = 10    # vertical gap between rows
CANVAS_PAD = 20    # outer margin on all four sides
CORNER_R   = 6     # swatch corner radius
SCALE      = 3     # super-sample factor for high-DPI output

# Font size at 1× – Pillow uses point size, scaled internally
FONT_SIZE_LABEL   = 15   # index number drawn inside swatch
FONT_SIZE_CAPTION = 13   # hex/RGB caption to the right


def _luma(r: int, g: int, b: int) -> float:
    return 0.299 * r + 0.587 * g + 0.114 * b


def _text_color(r: int, g: int, b: int) -> tuple[int, int, int]:
    return (10, 10, 10) if _luma(r, g, b) > 128 else (245, 245, 245)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try to load a clean system font; fall back to Pillow's default."""
    candidates = [
        "arial.ttf", "Arial.ttf",
        "DejaVuSans.ttf", "DejaVuSans-Bold.ttf",
        "LiberationSans-Regular.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def render_palette(
    palette_bgr: np.ndarray,
    output_path: str | None = "outputs/palette.png",
) -> np.ndarray:
    """Render a high-quality color-legend image for *palette_bgr*.

    Parameters
    ----------
    palette_bgr:
        Array of shape (K, 3) BGR uint8 – the palette from stage 2.
    output_path:
        Where to save the legend image.

    Returns
    -------
    legend : np.ndarray
        BGR image of the palette legend (downsampled to 1× from SCALE×).
    """
    k = len(palette_bgr)
    if k == 0:
        raise ValueError("render_palette() received an empty palette.")

    s = SCALE
    row_h    = SWATCH_H + ROW_PAD
    canvas_w = CANVAS_PAD * 2 + SWATCH_W + CAPTION_W
    canvas_h = CANVAS_PAD * 2 + row_h * k

    # Work at super-sampled resolution
    img = Image.new("RGB", (canvas_w * s, canvas_h * s), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    font_label   = _load_font(FONT_SIZE_LABEL * s)
    font_caption = _load_font(FONT_SIZE_CAPTION * s)

    print(f"[palette] Colors in palette : {k}")

    for i, color in enumerate(palette_bgr):
        b_val, g_val, r_val = int(color[0]), int(color[1]), int(color[2])
        fill_rgb = (r_val, g_val, b_val)
        label    = str(i + 1)
        hex_str  = f"#{r_val:02X}{g_val:02X}{b_val:02X}"
        caption  = f"{hex_str}  ({r_val},{g_val},{b_val})"

        y_top = CANVAS_PAD + i * row_h
        x0, y0 = CANVAS_PAD * s, y_top * s
        x1, y1 = (CANVAS_PAD + SWATCH_W) * s - 1, (y_top + SWATCH_H) * s - 1
        cr = CORNER_R * s

        # Rounded-rectangle swatch
        draw.rounded_rectangle([x0, y0, x1, y1], radius=cr, fill=fill_rgb,
                                outline=(100, 100, 100), width=max(1, s // 2))

        # Index number centred in swatch
        txt_col = _text_color(r_val, g_val, b_val)
        bbox = draw.textbbox((0, 0), label, font=font_label)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = x0 + ((x1 - x0) - tw) // 2 - bbox[0]
        ty = y0 + ((y1 - y0) - th) // 2 - bbox[1]
        draw.text((tx, ty), label, fill=txt_col, font=font_label)

        # Caption to the right
        cx = (CANVAS_PAD + SWATCH_W + 10) * s
        bbox_c = draw.textbbox((0, 0), caption, font=font_caption)
        th_c = bbox_c[3] - bbox_c[1]
        cy = y0 + ((y1 - y0) - th_c) // 2 - bbox_c[1]
        draw.text((cx, cy), caption, fill=(30, 30, 30), font=font_caption)

        print(f"  [{label:>2}]  BGR=({b_val:3d},{g_val:3d},{r_val:3d})  {hex_str}")

    # Downsample for smooth, high-quality output
    out_img = img.resize((canvas_w, canvas_h), Image.LANCZOS)

    if output_path is not None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        out_img.save(output_path)
        print(f"[palette] Saved to          : {output_path}  ({canvas_w}×{canvas_h} px)")

    # Return as BGR numpy array so callers get a consistent type
    legend = cv2.cvtColor(np.array(out_img), cv2.COLOR_RGB2BGR)
    return legend

