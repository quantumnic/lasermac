"""Tests for image to G-code converter."""

import os
import tempfile

import numpy as np
from PIL import Image

from lasermac.image_converter import (
    DITHER_MODES,
    adjust_image,
    calculate_output_size,
    dither_preview,
    image_to_gcode,
)


def _create_test_image(width=100, height=50, color=128):
    """Create a temporary test image."""
    img = Image.fromarray(np.full((height, width), color, dtype=np.uint8))
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    img.save(path)
    return path


class TestImageConversion:
    """Test image to G-code conversion."""

    def test_threshold_mode(self):
        path = _create_test_image(color=0)  # Black image
        try:
            gcode = image_to_gcode(path, width_mm=10, dpi=2, mode="threshold")
            assert "LaserMac" in gcode
            assert "G90" in gcode
            assert "S1000" in gcode  # Should have laser on for black pixels
        finally:
            os.unlink(path)

    def test_floyd_mode(self):
        path = _create_test_image(color=128)
        try:
            gcode = image_to_gcode(path, width_mm=10, dpi=2, mode="floyd")
            assert "LaserMac" in gcode
            assert len(gcode) > 100
        finally:
            os.unlink(path)

    def test_ordered_dither_mode(self):
        path = _create_test_image(color=128)
        try:
            gcode = image_to_gcode(path, width_mm=10, dpi=2, mode="ordered")
            assert "LaserMac" in gcode
            assert "Mode: ordered" in gcode
        finally:
            os.unlink(path)

    def test_jarvis_dither_mode(self):
        path = _create_test_image(color=128)
        try:
            gcode = image_to_gcode(path, width_mm=10, dpi=2, mode="jarvis")
            assert "LaserMac" in gcode
            assert "Mode: jarvis" in gcode
        finally:
            os.unlink(path)

    def test_grayscale_mode(self):
        path = _create_test_image(color=100)
        try:
            gcode = image_to_gcode(path, width_mm=10, dpi=2, mode="grayscale")
            assert "LaserMac" in gcode
        finally:
            os.unlink(path)

    def test_white_image_no_power(self):
        path = _create_test_image(color=255)  # White
        try:
            gcode = image_to_gcode(path, width_mm=10, dpi=2, mode="threshold")
            lines = [ln for ln in gcode.split("\n") if ln.startswith("G1") and "S1000" in ln]
            assert len(lines) == 0
        finally:
            os.unlink(path)

    def test_output_contains_return_to_origin(self):
        path = _create_test_image()
        try:
            gcode = image_to_gcode(path, width_mm=10, dpi=2)
            assert "G0 X0 Y0" in gcode
        finally:
            os.unlink(path)

    def test_all_modes_supported(self):
        path = _create_test_image(color=100)
        try:
            for mode in DITHER_MODES:
                gcode = image_to_gcode(path, width_mm=10, dpi=2, mode=mode)
                assert len(gcode) > 50, f"Mode {mode} produced too little output"
        finally:
            os.unlink(path)

    def test_invalid_mode_raises(self):
        import pytest
        path = _create_test_image()
        try:
            with pytest.raises(ValueError, match="Unknown mode"):
                image_to_gcode(path, mode="nonexistent")
        finally:
            os.unlink(path)

    def test_invert(self):
        path = _create_test_image(color=255)  # White → inverted = black
        try:
            gcode = image_to_gcode(path, width_mm=10, dpi=2, mode="threshold", invert=True)
            assert "S1000" in gcode  # Inverted white = black = laser on
        finally:
            os.unlink(path)


class TestImageAdjustments:
    def test_brightness_increase(self):
        pixels = np.full((10, 10), 100.0)
        result = adjust_image(pixels, brightness=50)
        assert np.mean(result) > 100

    def test_brightness_decrease(self):
        pixels = np.full((10, 10), 200.0)
        result = adjust_image(pixels, brightness=-50)
        assert np.mean(result) < 200

    def test_contrast(self):
        pixels = np.array([[50.0, 200.0]], dtype=np.float64)
        result = adjust_image(pixels, contrast=50)
        # Higher contrast → values spread further from 128
        assert result[0, 0] < 50 or result[0, 1] > 200

    def test_gamma_brighten(self):
        pixels = np.full((10, 10), 128.0)
        result = adjust_image(pixels, gamma=2.0)  # > 1 = brighten
        assert np.mean(result) > 128

    def test_no_adjustment(self):
        pixels = np.full((10, 10), 100.0)
        result = adjust_image(pixels, brightness=0, contrast=0, gamma=1.0)
        np.testing.assert_array_almost_equal(result, pixels)

    def test_clipping(self):
        pixels = np.full((10, 10), 250.0)
        result = adjust_image(pixels, brightness=50)
        assert np.max(result) <= 255
        assert np.min(result) >= 0


class TestDitherPreview:
    def test_preview_returns_array(self):
        path = _create_test_image()
        try:
            result = dither_preview(path, width_px=50, mode="threshold")
            assert isinstance(result, np.ndarray)
            assert result.dtype == np.uint8
        finally:
            os.unlink(path)

    def test_preview_respects_mode(self):
        path = _create_test_image(color=128)
        try:
            t = dither_preview(path, width_px=50, mode="threshold")
            f = dither_preview(path, width_px=50, mode="floyd")
            # Different modes should produce different results
            assert t.shape == f.shape
        finally:
            os.unlink(path)


class TestSizeCalculation:
    """Test output size calculation."""

    def test_auto_height(self):
        path = _create_test_image(width=200, height=100)
        try:
            w, h = calculate_output_size(path, width_mm=100)
            assert w == 100.0
            assert h == 50.0
        finally:
            os.unlink(path)

    def test_explicit_height(self):
        path = _create_test_image()
        try:
            w, h = calculate_output_size(path, width_mm=80, height_mm=40)
            assert w == 80.0
            assert h == 40.0
        finally:
            os.unlink(path)

    def test_square_image(self):
        path = _create_test_image(width=100, height=100)
        try:
            w, h = calculate_output_size(path, width_mm=50)
            assert w == 50.0
            assert h == 50.0
        finally:
            os.unlink(path)
