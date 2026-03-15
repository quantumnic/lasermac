"""Image to G-code converter for LaserMac.

Converts raster images (PNG/JPG/BMP/TIFF) to G-code for laser engraving.
Supports 5 dithering modes: threshold, Floyd-Steinberg, Ordered (Bayer),
Jarvis-Judice-Ninke, and grayscale lines.
Includes brightness/contrast/gamma adjustment before conversion.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

# ── Supported dithering modes ──────────────────────────────────────

DITHER_MODES = ("threshold", "floyd", "ordered", "jarvis", "grayscale")

# 4×4 Bayer matrix for ordered dithering
BAYER_4X4 = np.array([
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5],
], dtype=np.float64) / 16.0


def image_to_gcode(
    image_path: str,
    width_mm: float = 100.0,
    height_mm: float | None = None,
    dpi: int = 10,
    mode: str = "threshold",
    speed: int = 3000,
    power_max: int = 1000,
    threshold: int = 128,
    brightness: float = 0.0,
    contrast: float = 0.0,
    gamma: float = 1.0,
    invert: bool = False,
) -> str:
    """Convert an image to G-code for laser engraving.

    Args:
        image_path: Path to image file.
        width_mm: Output width in mm.
        height_mm: Output height in mm (auto from aspect ratio if None).
        dpi: Lines per mm (resolution).
        mode: Dithering mode — one of DITHER_MODES.
        speed: Engraving speed in mm/min.
        power_max: Maximum laser power (S value, typically 0–1000).
        threshold: Brightness threshold for "threshold" mode (0–255).
        brightness: Brightness adjustment (-100 to 100).
        contrast: Contrast adjustment (-100 to 100).
        gamma: Gamma correction (0.1 to 5.0).
        invert: Invert black/white.

    Returns:
        G-code string.
    """
    img = Image.open(image_path).convert("L")

    # Calculate dimensions
    orig_w, orig_h = img.size
    if height_mm is None:
        height_mm = width_mm * (orig_h / orig_w)

    # Resize to match desired resolution
    pixel_w = int(width_mm * dpi)
    pixel_h = int(height_mm * dpi)
    img = img.resize((pixel_w, pixel_h), Image.Resampling.LANCZOS)

    pixels = np.array(img, dtype=np.float64)

    # Apply adjustments
    pixels = adjust_image(pixels, brightness, contrast, gamma)

    # Invert if requested
    if invert:
        pixels = 255.0 - pixels

    # Apply dithering / processing
    if mode == "floyd":
        pixels = _floyd_steinberg(pixels)
    elif mode == "threshold":
        pixels = (pixels < threshold).astype(np.float64) * 255
    elif mode == "ordered":
        pixels = _ordered_dither(pixels)
    elif mode == "jarvis":
        pixels = _jarvis_dither(pixels)
    elif mode == "grayscale":
        pass  # Use raw grayscale values
    else:
        raise ValueError(f"Unknown mode: {mode}. Use one of: {DITHER_MODES}")

    # Generate G-code
    return _pixels_to_gcode(pixels, width_mm, height_mm, speed, power_max, mode)


def adjust_image(
    pixels: np.ndarray,
    brightness: float = 0.0,
    contrast: float = 0.0,
    gamma: float = 1.0,
) -> np.ndarray:
    """Apply brightness, contrast, and gamma adjustments."""
    result = pixels.copy()

    # Brightness (-100 to 100 → mapped to -255 to 255 shift)
    if brightness != 0:
        result = result + brightness * 2.55
        result = np.clip(result, 0, 255)

    # Contrast (-100 to 100)
    if contrast != 0:
        factor = (259 * (contrast + 255)) / (255 * (259 - contrast))
        result = factor * (result - 128) + 128
        result = np.clip(result, 0, 255)

    # Gamma (0.1 to 5.0)
    if gamma != 1.0:
        result = 255.0 * (result / 255.0) ** (1.0 / gamma)
        result = np.clip(result, 0, 255)

    return result


def _floyd_steinberg(pixels: np.ndarray) -> np.ndarray:
    """Apply Floyd-Steinberg dithering."""
    h, w = pixels.shape
    result = pixels.copy()

    for y in range(h):
        for x in range(w):
            old_val = result[y, x]
            new_val = 255.0 if old_val > 127 else 0.0
            result[y, x] = new_val
            error = old_val - new_val

            if x + 1 < w:
                result[y, x + 1] += error * 7 / 16
            if y + 1 < h:
                if x - 1 >= 0:
                    result[y + 1, x - 1] += error * 3 / 16
                result[y + 1, x] += error * 5 / 16
                if x + 1 < w:
                    result[y + 1, x + 1] += error * 1 / 16

    return (result < 128).astype(np.float64) * 255


def _ordered_dither(pixels: np.ndarray) -> np.ndarray:
    """Apply ordered (Bayer matrix) dithering."""
    h, w = pixels.shape
    result = np.zeros_like(pixels)

    for y in range(h):
        for x in range(w):
            threshold = BAYER_4X4[y % 4, x % 4] * 255
            result[y, x] = 255.0 if pixels[y, x] < threshold else 0.0

    return result


def _jarvis_dither(pixels: np.ndarray) -> np.ndarray:
    """Apply Jarvis-Judice-Ninke dithering (wider error diffusion)."""
    h, w = pixels.shape
    result = pixels.copy()

    # Jarvis kernel: error distributed over 12 neighbors
    kernel = [
        (0, 1, 7), (0, 2, 5),
        (1, -2, 3), (1, -1, 5), (1, 0, 7), (1, 1, 5), (1, 2, 3),
        (2, -2, 1), (2, -1, 3), (2, 0, 5), (2, 1, 3), (2, 2, 1),
    ]
    total = 48

    for y in range(h):
        for x in range(w):
            old_val = result[y, x]
            new_val = 255.0 if old_val > 127 else 0.0
            result[y, x] = new_val
            error = old_val - new_val

            for dy, dx, weight in kernel:
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w:
                    result[ny, nx] += error * weight / total

    return (result < 128).astype(np.float64) * 255


def _pixels_to_gcode(
    pixels: np.ndarray,
    width_mm: float,
    height_mm: float,
    speed: int,
    power_max: int,
    mode: str,
) -> str:
    """Convert pixel array to G-code using line-by-line raster scanning."""
    h, w = pixels.shape
    pixel_size_x = width_mm / w
    pixel_size_y = height_mm / h

    lines: list[str] = []
    lines.append("; Generated by LaserMac")
    lines.append(f"; Image size: {width_mm:.1f} x {height_mm:.1f} mm")
    lines.append(f"; Resolution: {w} x {h} px")
    lines.append(f"; Mode: {mode}")
    lines.append("G90 ; Absolute positioning")
    lines.append("G21 ; Millimeters")
    lines.append("M5 S0 ; Laser off")
    lines.append("")

    for row in range(h):
        y = row * pixel_size_y
        # Bi-directional scanning (zigzag)
        if row % 2 == 0:
            x_range = range(w)
        else:
            x_range = range(w - 1, -1, -1)

        # Move to start of line
        start_x = 0.0 if row % 2 == 0 else (w - 1) * pixel_size_x
        lines.append(f"G0 X{start_x:.3f} Y{y:.3f} S0")

        for col in x_range:
            x = col * pixel_size_x
            val = pixels[row, col]

            if mode == "grayscale":
                # Map grayscale: dark = high power, light = low power
                power = int((1.0 - val / 255.0) * power_max)
            else:
                # Binary: pixel is on (dark) or off
                power = power_max if val > 0 else 0

            if power > 0:
                lines.append(f"G1 X{x:.3f} Y{y:.3f} S{power} F{speed}")
            else:
                lines.append(f"G0 X{x:.3f} Y{y:.3f} S0")

    lines.append("")
    lines.append("M5 S0 ; Laser off")
    lines.append("G0 X0 Y0 ; Return to origin")
    lines.append("")
    return "\n".join(lines)


def dither_preview(
    image_path: str,
    width_px: int = 400,
    mode: str = "threshold",
    threshold: int = 128,
    brightness: float = 0.0,
    contrast: float = 0.0,
    gamma: float = 1.0,
    invert: bool = False,
) -> np.ndarray:
    """Return dithered preview as numpy array (for display, not G-code)."""
    img = Image.open(image_path).convert("L")
    orig_w, orig_h = img.size
    height_px = int(width_px * orig_h / orig_w)
    img = img.resize((width_px, height_px), Image.Resampling.LANCZOS)

    pixels = np.array(img, dtype=np.float64)
    pixels = adjust_image(pixels, brightness, contrast, gamma)

    if invert:
        pixels = 255.0 - pixels

    if mode == "floyd":
        pixels = _floyd_steinberg(pixels)
    elif mode == "threshold":
        pixels = (pixels < threshold).astype(np.float64) * 255
    elif mode == "ordered":
        pixels = _ordered_dither(pixels)
    elif mode == "jarvis":
        pixels = _jarvis_dither(pixels)

    return np.clip(pixels, 0, 255).astype(np.uint8)


def calculate_output_size(
    image_path: str,
    width_mm: float = 100.0,
    height_mm: float | None = None,
) -> tuple[float, float]:
    """Calculate output size in mm for a given image."""
    img = Image.open(image_path)
    orig_w, orig_h = img.size
    if height_mm is None:
        height_mm = width_mm * (orig_h / orig_w)
    return (width_mm, height_mm)
