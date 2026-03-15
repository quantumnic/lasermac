"""Tests for machine profiles."""

import json

from lasermac.profiles import MachineProfile, list_profiles


class TestMachineProfile:
    def test_default_profile(self):
        p = MachineProfile()
        assert p.work_x == 300.0
        assert p.work_y == 300.0
        assert p.max_power == 1000

    def test_to_dict_from_dict(self):
        p = MachineProfile(
            name="TestBot", work_x=500, work_y=400,
            max_speed=12000, invert_x=True,
        )
        d = p.to_dict()
        restored = MachineProfile.from_dict(d)
        assert restored.name == "TestBot"
        assert restored.work_x == 500
        assert restored.invert_x is True

    def test_from_grbl_detect(self):
        cfg = {
            "work_x": 430.0, "work_y": 390.0,
            "max_speed": 12000.0, "max_power": 1000,
            "steps_x": 80.0, "steps_y": 80.0,
            "invert_x": False, "invert_y": True,
            "laser_mode": True,
        }
        p = MachineProfile.from_grbl_detect(cfg)
        assert p.work_x == 430.0
        assert p.work_y == 390.0
        assert p.invert_y is True

    def test_save_and_load(self, tmp_path):
        p = MachineProfile(name="My Laser", work_x=250, work_y=250)
        path = p.save(tmp_path)
        assert path.exists()
        loaded = MachineProfile.load(path)
        assert loaded.name == "My Laser"
        assert loaded.work_x == 250

    def test_list_profiles_includes_builtins(self, tmp_path):
        profiles = list_profiles(tmp_path)
        names = [p.name for p in profiles]
        assert "Totem S 300x300" in names
        assert "xTool D1 Pro 430x390" in names
        assert "Generic GRBL" in names

    def test_list_profiles_includes_custom(self, tmp_path):
        custom = MachineProfile(name="Custom Cutter", work_x=600, work_y=400)
        custom.save(tmp_path)
        profiles = list_profiles(tmp_path)
        names = [p.name for p in profiles]
        assert "Custom Cutter" in names

    def test_save_creates_json(self, tmp_path):
        p = MachineProfile(name="Test Machine")
        path = p.save(tmp_path)
        data = json.loads(path.read_text())
        assert data["name"] == "Test Machine"
        assert data["work_x"] == 300.0
