"""Tests for draw_canvas — mocked, no display needed."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# Mock tkinter and customtkinter before importing draw_canvas
_tk_mock = MagicMock()
_ctk_mock = MagicMock()
# Make CTkFrame a proper class so DrawCanvas can inherit from it
_ctk_mock.CTkFrame = type("CTkFrame", (), {"bind_all": MagicMock(), "grid_columnconfigure": MagicMock(), "grid_rowconfigure": MagicMock()})
_ctk_mock.BooleanVar = MagicMock

sys.modules.setdefault("tkinter", _tk_mock)
sys.modules.setdefault("customtkinter", _ctk_mock)

# Now import
from lasermac.widgets.draw_canvas import DrawCanvas, DrawElement  # noqa: E402


def _make_canvas():
    """Create a DrawCanvas instance with mocked internals."""
    grbl = MagicMock()
    dc = object.__new__(DrawCanvas)
    dc.grbl = grbl
    dc.work_w_mm = 400.0
    dc.work_h_mm = 400.0
    dc.current_tool = "pen"
    dc.elements = []
    dc.redo_stack = []
    dc._current_element = None
    dc._drag_start = None
    dc._preview_id = None
    dc._selected_idx = None
    dc._select_offset = (0, 0)
    dc.show_grid = True
    dc.zoom_level = 1.0
    dc.canvas = MagicMock()
    dc.speed_slider = MagicMock(get=MagicMock(return_value=1000))
    dc.power_slider = MagicMock(get=MagicMock(return_value=500))
    dc.CANVAS_PX = 400
    dc._grid_var = MagicMock(get=MagicMock(return_value=True))
    dc._tool_buttons = {t: MagicMock() for t in DrawCanvas.TOOLS}
    return dc


@pytest.fixture
def dc():
    return _make_canvas()


class TestCoordinateConversion:
    def test_px_to_mm_origin(self, dc):
        assert dc.px_to_mm(0, 0) == (0.0, 0.0)

    def test_px_to_mm_full(self, dc):
        assert dc.px_to_mm(400, 400) == (400.0, 400.0)

    def test_px_to_mm_center(self, dc):
        assert dc.px_to_mm(200, 200) == (200.0, 200.0)

    def test_px_to_mm_with_zoom(self, dc):
        dc.zoom_level = 2.0
        assert dc.px_to_mm(200, 200) == (100.0, 100.0)

    def test_px_to_mm_quarter(self, dc):
        assert dc.px_to_mm(100, 100) == (100.0, 100.0)


class TestGcodeGeneration:
    def test_empty_canvas(self, dc):
        gcode = dc.to_gcode(speed=1000, power=500)
        assert "G21" in gcode
        assert "M2" in gcode

    def test_rect_gcode(self, dc):
        dc.elements.append(DrawElement(kind="rect", points=[(40, 40), (200, 200)]))
        gcode = dc.to_gcode(speed=1000, power=500)
        assert "M3 S500" in gcode
        assert "G0 X40.0 Y40.0" in gcode
        assert "G1 X200.0 Y40.0" in gcode
        assert "G1 X200.0 Y200.0" in gcode
        assert "G1 X40.0 Y200.0" in gcode
        assert "M5" in gcode

    def test_line_gcode(self, dc):
        dc.elements.append(DrawElement(kind="line", points=[(0, 0), (400, 400)]))
        gcode = dc.to_gcode(speed=2000, power=800)
        assert "G1 F2000" in gcode
        assert "M3 S800" in gcode
        assert "G0 X0.0 Y0.0" in gcode
        assert "G1 X400.0 Y400.0" in gcode

    def test_stroke_gcode(self, dc):
        dc.elements.append(DrawElement(kind="pen", points=[(10, 10), (20, 20), (30, 10)]))
        gcode = dc.to_gcode(speed=1000, power=500)
        assert "G0 X10.0 Y10.0" in gcode
        assert "M3 S500" in gcode
        assert "G1 X20.0 Y20.0" in gcode
        assert "G1 X30.0 Y10.0" in gcode

    def test_circle_gcode_has_segments(self, dc):
        dc.elements.append(DrawElement(kind="circle", points=[(200, 200), (250, 200)]))
        gcode = dc.to_gcode(speed=1000, power=300)
        assert "M3 S300" in gcode
        g1_count = gcode.count("G1 X")
        assert g1_count >= 36

    def test_gcode_header_footer(self, dc):
        gcode = dc.to_gcode(speed=500, power=100)
        lines = gcode.split("\n")
        assert any("G21" in ln for ln in lines)
        assert any("G90" in ln for ln in lines)
        assert any("M2" in ln for ln in lines)
        assert any("G1 F500" in ln for ln in lines)


class TestUndoRedo:
    def test_undo_removes_last(self, dc):
        e1 = DrawElement(kind="line", points=[(0, 0), (100, 100)], canvas_ids=[1])
        e2 = DrawElement(kind="rect", points=[(10, 10), (50, 50)], canvas_ids=[2])
        dc.elements = [e1, e2]
        dc.undo()
        assert len(dc.elements) == 1
        assert dc.elements[0] is e1
        assert len(dc.redo_stack) == 1
        assert dc.redo_stack[0] is e2

    def test_redo_restores(self, dc):
        dc.canvas.create_line = MagicMock(return_value=99)
        e1 = DrawElement(kind="line", points=[(0, 0), (100, 100)], canvas_ids=[1])
        dc.redo_stack = [e1]
        dc.redo()
        assert len(dc.elements) == 1
        assert dc.elements[0] is e1
        assert len(dc.redo_stack) == 0

    def test_undo_empty_noop(self, dc):
        dc.undo()
        assert dc.elements == []

    def test_redo_empty_noop(self, dc):
        dc.redo()
        assert dc.redo_stack == []

    def test_undo_redo_roundtrip(self, dc):
        dc.canvas.create_line = MagicMock(return_value=10)
        elem = DrawElement(kind="line", points=[(0, 0), (50, 50)], canvas_ids=[1])
        dc.elements = [elem]
        dc.undo()
        assert len(dc.elements) == 0
        dc.redo()
        assert len(dc.elements) == 1


class TestToolSwitching:
    def test_set_tool(self, dc):
        dc.set_tool("rect")
        assert dc.current_tool == "rect"
        dc.set_tool("circle")
        assert dc.current_tool == "circle"

    def test_set_invalid_tool_ignored(self, dc):
        dc.set_tool("pen")
        dc.set_tool("invalid_tool")
        assert dc.current_tool == "pen"

    def test_all_tools_valid(self, dc):
        for tool in ("pen", "line", "rect", "circle", "eraser", "select"):
            dc.set_tool(tool)
            assert dc.current_tool == tool


class TestClear:
    def test_clear_empties(self, dc):
        dc.elements = [DrawElement(kind="pen", points=[(0, 0), (1, 1)])]
        dc.redo_stack = [DrawElement(kind="line", points=[(0, 0), (1, 1)])]
        dc.clear()
        assert dc.elements == []
        assert dc.redo_stack == []


class TestBurn:
    def test_burn_sends_commands(self, dc):
        dc.elements = [DrawElement(kind="line", points=[(0, 0), (400, 400)])]
        dc.burn(speed=1000, power=500)
        assert dc.grbl.send_command.called
        calls = [c[0][0] for c in dc.grbl.send_command.call_args_list]
        assert any("G21" in c for c in calls)
        assert any("M3 S500" in c for c in calls)


class TestSvg:
    def test_save_svg(self, dc, tmp_path):
        dc.elements = [
            DrawElement(kind="line", points=[(0, 0), (200, 200)]),
            DrawElement(kind="rect", points=[(10, 10), (100, 100)]),
        ]
        path = str(tmp_path / "test.svg")
        dc.save_svg(path)
        with open(path) as f:
            content = f.read()
        assert "<svg" in content
        assert "</svg>" in content
        assert "<line" in content
        assert "<rect" in content
