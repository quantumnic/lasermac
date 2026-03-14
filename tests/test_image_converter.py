"""Tests for image to G-code converter."""

import os
import tempfile

import numpy as np
from PIL import Image

from lasermac.image_converter import calculate_output_size, image_to_gcode


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
            # White pixels should not have S1000
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


class TestSizeCalculation:
    """Test output size calculation."""

    def test_auto_height(self):
        path = _create_test_image(width=200, height=100)
        try:
            w, h = calculate_output_size(path, width_mm=100)
            assert w == 100.0
            assert h == 50.0  # 100 * (100/200)
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
