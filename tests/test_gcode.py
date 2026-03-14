"""Tests for G-code parser and sender."""

import os
import tempfile

from lasermac.gcode import _calculate_bounds, estimate_time, load_gcode, load_gcode_from_string


class TestGcodeLoading:
    """Test G-code file loading."""

    def test_load_from_string(self):
        gcode = "G0 X0 Y0\nG1 X10 Y10 F1000\nG1 X20 Y0"
        job = load_gcode_from_string(gcode)
        assert job.total_lines == 3
        assert job.filename == "generated"

    def test_load_filters_comments(self):
        gcode = "; comment\nG0 X0\n(inline comment)\nG1 X10\n"
        job = load_gcode_from_string(gcode)
        assert job.total_lines == 2

    def test_load_strips_inline_comments(self):
        gcode = "G0 X0 ; move\nG1 X10 (cut)"
        job = load_gcode_from_string(gcode)
        assert ";" not in job.lines[0]
        assert "(" not in job.lines[1]

    def test_load_from_file(self):
        gcode = "G0 X0 Y0\nG1 X50 Y50 F500\n"
        with tempfile.NamedTemporaryFile(suffix=".nc", mode="w", delete=False) as f:
            f.write(gcode)
            path = f.name
        try:
            job = load_gcode(path)
            assert job.total_lines == 2
            assert job.filename.endswith(".nc")
        finally:
            os.unlink(path)

    def test_progress(self):
        job = load_gcode_from_string("G0 X0\nG1 X10\nG1 X20\nG1 X30")
        assert job.progress == 0.0
        job.current_line = 2
        assert job.progress == 0.5
        assert job.progress_percent == 50.0

    def test_empty_job_progress(self):
        job = load_gcode_from_string("")
        assert job.progress == 0.0


class TestBoundsCalculation:
    """Test bounding box calculation."""

    def test_simple_bounds(self):
        lines = ["G0 X0 Y0", "G1 X100 Y50", "G1 X50 Y100"]
        bounds = _calculate_bounds(lines)
        assert bounds == (0.0, 0.0, 100.0, 100.0)

    def test_negative_bounds(self):
        lines = ["G0 X-10 Y-20", "G1 X30 Y40"]
        bounds = _calculate_bounds(lines)
        assert bounds == (-10.0, -20.0, 30.0, 40.0)

    def test_no_coordinates(self):
        lines = ["M3 S1000", "M5 S0"]
        bounds = _calculate_bounds(lines)
        assert bounds == (0, 0, 0, 0)


class TestTimeEstimation:
    """Test job time estimation."""

    def test_simple_move(self):
        lines = ["G1 X100 Y0 F1000"]
        t = estimate_time(lines)
        # 100mm at 1000mm/min = 6 seconds
        assert abs(t - 6.0) < 0.1

    def test_two_moves(self):
        lines = ["G1 X100 Y0 F1000", "G1 X100 Y100 F1000"]
        t = estimate_time(lines)
        # 100mm + 100mm at 1000mm/min = 12 seconds
        assert abs(t - 12.0) < 0.1

    def test_no_moves(self):
        lines = ["M3 S1000"]
        t = estimate_time(lines)
        assert t == 0.0
