"""Tests for power tester grid."""

from lasermac.power_tester import PowerTestConfig, generate_power_test
from lasermac.power_tester import test_grid_bounds as get_grid_bounds


class TestPowerTest:
    def test_default_generates_gcode(self):
        gcode = generate_power_test()
        assert "LaserMac Power Test Grid" in gcode
        assert "G21" in gcode
        assert "G90" in gcode
        assert "M3 S" in gcode

    def test_custom_config(self):
        cfg = PowerTestConfig(
            power_min=200, power_max=800, power_steps=3,
            speed_min=500, speed_max=2000, speed_steps=3,
            square_size=10.0,
        )
        gcode = generate_power_test(cfg)
        assert "S200" in gcode
        assert "S800" in gcode
        assert "F500" in gcode
        assert "F2000" in gcode

    def test_single_step(self):
        cfg = PowerTestConfig(power_steps=1, speed_steps=1)
        gcode = generate_power_test(cfg)
        assert "S100" in gcode  # power_min

    def test_contains_fill(self):
        """Each square should have fill lines."""
        gcode = generate_power_test()
        # Fill lines create many G1 moves inside each square
        g1_count = gcode.count("G1 X")
        assert g1_count > 25  # At least some fill lines

    def test_returns_to_origin(self):
        gcode = generate_power_test()
        assert "G0 X0 Y0" in gcode

    def test_grid_bounds(self):
        cfg = PowerTestConfig(
            power_steps=3, speed_steps=2,
            square_size=5.0, spacing=3.0,
        )
        min_x, min_y, max_x, max_y = get_grid_bounds(cfg)
        assert min_x == 0.0
        assert min_y == 0.0
        assert max_x > 0
        assert max_y > 0

    def test_square_labels_in_comments(self):
        gcode = generate_power_test()
        assert "; Square: S" in gcode
