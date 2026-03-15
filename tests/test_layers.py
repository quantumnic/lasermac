"""Tests for the layer / operation system."""

from lasermac.layers import (
    OPERATION_CUT,
    OPERATION_ENGRAVE,
    OPERATION_MARK,
    OPERATIONS,
    Layer,
    OperationSettings,
    create_default_layers,
    default_settings,
    gcode_sort_key,
    operation_color,
    operation_fill_color,
    operation_label,
    operation_line_width,
)


class TestOperationSettings:
    def test_default_cut_settings(self):
        s = default_settings(OPERATION_CUT)
        assert s.operation == OPERATION_CUT
        assert s.speed == 200
        assert s.power == 1000
        assert s.passes == 3
        assert s.fill_mode == "none"  # CUT never fills

    def test_default_engrave_settings(self):
        s = default_settings(OPERATION_ENGRAVE)
        assert s.operation == OPERATION_ENGRAVE
        assert 500 <= s.speed <= 3000
        assert 300 <= s.power <= 700
        assert s.passes == 1
        assert s.fill_mode in ("lines", "schraffur", "none")

    def test_default_mark_settings(self):
        s = default_settings(OPERATION_MARK)
        assert s.operation == OPERATION_MARK
        assert s.speed >= 3000
        assert s.power <= 300
        assert s.passes == 1

    def test_to_dict_from_dict_roundtrip(self):
        s = OperationSettings(
            operation=OPERATION_CUT, speed=300, power=900,
            passes=5, fill_mode="none",
        )
        d = s.to_dict()
        restored = OperationSettings.from_dict(d)
        assert restored.operation == OPERATION_CUT
        assert restored.speed == 300
        assert restored.power == 900
        assert restored.passes == 5

    def test_defaults_are_independent_copies(self):
        s1 = default_settings(OPERATION_CUT)
        s2 = default_settings(OPERATION_CUT)
        s1.speed = 9999
        assert s2.speed != 9999


class TestGcodeExportOrder:
    def test_mark_before_engrave(self):
        assert gcode_sort_key(OPERATION_MARK) < gcode_sort_key(OPERATION_ENGRAVE)

    def test_engrave_before_cut(self):
        assert gcode_sort_key(OPERATION_ENGRAVE) < gcode_sort_key(OPERATION_CUT)

    def test_full_order(self):
        """Mark(0) < Engrave(1) < Cut(2) — cut always last!"""
        assert gcode_sort_key(OPERATION_MARK) == 0
        assert gcode_sort_key(OPERATION_ENGRAVE) == 1
        assert gcode_sort_key(OPERATION_CUT) == 2


class TestOperationColors:
    def test_cut_is_red(self):
        assert operation_color(OPERATION_CUT) == "#FF3333"

    def test_engrave_is_blue(self):
        assert operation_color(OPERATION_ENGRAVE) == "#3399FF"

    def test_mark_is_green(self):
        assert operation_color(OPERATION_MARK) == "#33CC33"

    def test_line_widths(self):
        assert operation_line_width(OPERATION_CUT) == 3  # thick
        assert operation_line_width(OPERATION_ENGRAVE) == 2
        assert operation_line_width(OPERATION_MARK) == 1  # thin

    def test_fill_colors_are_transparent(self):
        for op in OPERATIONS:
            fc = operation_fill_color(op)
            assert fc.endswith("22")  # alpha

    def test_labels_have_icons(self):
        assert "✂️" in operation_label(OPERATION_CUT)
        assert "✏️" in operation_label(OPERATION_ENGRAVE)
        assert "🖊️" in operation_label(OPERATION_MARK)


class TestLayers:
    def test_create_default_layers(self):
        layers = create_default_layers()
        assert len(layers) == 3
        names = [ly.name for ly in layers]
        assert "Cut" in names
        assert "Engrave" in names
        assert "Mark" in names

    def test_layer_operations_match(self):
        layers = create_default_layers()
        for layer in layers:
            assert layer.defaults.operation == layer.operation

    def test_layer_to_dict_from_dict(self):
        layer = Layer(name="Test", operation=OPERATION_CUT, color="#FF0000")
        d = layer.to_dict()
        restored = Layer.from_dict(d)
        assert restored.name == "Test"
        assert restored.operation == OPERATION_CUT
        assert restored.defaults.operation == OPERATION_CUT

    def test_cut_layer_color_is_red(self):
        layers = create_default_layers()
        cut = [ly for ly in layers if ly.operation == OPERATION_CUT][0]
        assert cut.color == "#FF3333"
