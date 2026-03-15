"""Project save/load for LaserMac (.lmc format).

.lmc files are JSON containing all shapes, layers, and settings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_VERSION = 1
PROJECT_EXTENSION = ".lmc"


@dataclass
class Project:
    """A LaserMac project."""

    version: int = PROJECT_VERSION
    name: str = "Untitled"
    shapes: list[dict] = field(default_factory=list)
    layers: list[dict] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "name": self.name,
            "shapes": self.shapes,
            "layers": self.layers,
            "settings": self.settings,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Project:
        return cls(
            version=d.get("version", 1),
            name=d.get("name", "Untitled"),
            shapes=d.get("shapes", []),
            layers=d.get("layers", []),
            settings=d.get("settings", {}),
        )

    def save(self, filepath: str) -> None:
        """Save project to .lmc file."""
        path = Path(filepath)
        if path.suffix.lower() != PROJECT_EXTENSION:
            path = path.with_suffix(PROJECT_EXTENSION)
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, filepath: str) -> Project:
        """Load project from .lmc file."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Project not found: {filepath}")
        data = json.loads(path.read_text())
        return cls.from_dict(data)


def recent_files_path() -> Path:
    """Path to recent files list."""
    return Path.home() / ".lasermac" / "recent_files.json"


def load_recent_files(max_count: int = 10) -> list[str]:
    """Load list of recently opened files."""
    path = recent_files_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data[:max_count]
    except Exception:
        return []


def add_recent_file(filepath: str, max_count: int = 10) -> None:
    """Add a file to the recent files list."""
    recents = load_recent_files(max_count)
    # Remove if already present, then prepend
    filepath = str(Path(filepath).resolve())
    recents = [f for f in recents if f != filepath]
    recents.insert(0, filepath)
    recents = recents[:max_count]

    path = recent_files_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(recents, indent=2))
