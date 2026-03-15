"""Machine profiles for LaserMac.

Save/load machine configurations as JSON in ~/.lasermac/profiles/.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PROFILES_DIR = Path.home() / ".lasermac" / "profiles"

# ── Built-in profiles ──────────────────────────────────────────────

BUILTIN_PROFILES: list[dict] = [
    {
        "name": "Totem S 300x300",
        "work_x": 300.0,
        "work_y": 300.0,
        "max_speed": 6000.0,
        "max_power": 1000,
        "steps_x": 80.0,
        "steps_y": 80.0,
        "invert_x": False,
        "invert_y": False,
        "laser_mode": True,
    },
    {
        "name": "xTool D1 Pro 430x390",
        "work_x": 430.0,
        "work_y": 390.0,
        "max_speed": 12000.0,
        "max_power": 1000,
        "steps_x": 80.0,
        "steps_y": 80.0,
        "invert_x": False,
        "invert_y": False,
        "laser_mode": True,
    },
    {
        "name": "Generic GRBL",
        "work_x": 300.0,
        "work_y": 300.0,
        "max_speed": 6000.0,
        "max_power": 1000,
        "steps_x": 80.0,
        "steps_y": 80.0,
        "invert_x": False,
        "invert_y": False,
        "laser_mode": True,
    },
]


@dataclass
class MachineProfile:
    """A saved machine configuration."""

    name: str = "Untitled"
    work_x: float = 300.0
    work_y: float = 300.0
    max_speed: float = 6000.0
    max_power: int = 1000
    steps_x: float = 80.0
    steps_y: float = 80.0
    invert_x: bool = False
    invert_y: bool = False
    laser_mode: bool = True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "work_x": self.work_x,
            "work_y": self.work_y,
            "max_speed": self.max_speed,
            "max_power": self.max_power,
            "steps_x": self.steps_x,
            "steps_y": self.steps_y,
            "invert_x": self.invert_x,
            "invert_y": self.invert_y,
            "laser_mode": self.laser_mode,
        }

    @classmethod
    def from_dict(cls, d: dict) -> MachineProfile:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_grbl_detect(cls, cfg: dict) -> MachineProfile:
        """Create profile from grbl.detect_machine() result."""
        return cls(
            name="Detected Machine",
            work_x=cfg.get("work_x", 300.0),
            work_y=cfg.get("work_y", 300.0),
            max_speed=cfg.get("max_speed", 6000.0),
            max_power=int(cfg.get("max_power", 1000)),
            steps_x=cfg.get("steps_x", 80.0),
            steps_y=cfg.get("steps_y", 80.0),
            invert_x=cfg.get("invert_x", False),
            invert_y=cfg.get("invert_y", False),
            laser_mode=cfg.get("laser_mode", True),
        )

    def save(self, directory: Path | None = None) -> Path:
        """Save profile to JSON file."""
        d = directory or PROFILES_DIR
        d.mkdir(parents=True, exist_ok=True)
        slug = self.name.lower().replace(" ", "_").replace("/", "_")
        path = d / f"{slug}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path

    @classmethod
    def load(cls, path: Path) -> MachineProfile:
        """Load profile from JSON file."""
        data = json.loads(path.read_text())
        return cls.from_dict(data)


def list_profiles(directory: Path | None = None) -> list[MachineProfile]:
    """List all saved profiles + builtins."""
    profiles = [MachineProfile.from_dict(b) for b in BUILTIN_PROFILES]

    d = directory or PROFILES_DIR
    if d.exists():
        for f in sorted(d.glob("*.json")):
            try:
                p = MachineProfile.load(f)
                # Avoid duplicates by name
                if not any(bp.name == p.name for bp in profiles):
                    profiles.append(p)
            except Exception:
                pass

    return profiles


def save_profile(profile: MachineProfile, directory: Path | None = None) -> Path:
    """Save a machine profile."""
    return profile.save(directory)
