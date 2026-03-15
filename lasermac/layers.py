"""Layer & operation system for LaserMac.

Central concept: every shape has an operation type (cut / engrave / mark)
that determines its default settings and G-code generation behavior.

- CUT:     Slow + high power + multiple passes, outline only (no fill)
- ENGRAVE: Medium speed + medium power, supports fill patterns
- MARK:    Fast + low power, surface marking only
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── Operation type constants ────────────────────────────────────────

OPERATION_CUT = "cut"
OPERATION_ENGRAVE = "engrave"
OPERATION_MARK = "mark"

OPERATIONS = (OPERATION_CUT, OPERATION_ENGRAVE, OPERATION_MARK)

# Display metadata per operation
OPERATION_META = {
    OPERATION_CUT: {
        "label": "✂️ Cut",
        "color": "#FF3333",
        "fill_color": "#FF333322",
        "icon": "✂️",
        "line_width": 3,
        "description": "Slow + max power, outline only, multi-pass",
    },
    OPERATION_ENGRAVE: {
        "label": "✏️ Engrave",
        "color": "#3399FF",
        "fill_color": "#3399FF22",
        "icon": "✏️",
        "line_width": 2,
        "description": "Medium speed, supports fill patterns",
    },
    OPERATION_MARK: {
        "label": "🖊️ Mark",
        "color": "#33CC33",
        "fill_color": "#33CC3322",
        "icon": "🖊️",
        "line_width": 1,
        "description": "Fast + low power, surface marking",
    },
}


@dataclass
class OperationSettings:
    """Settings for a specific operation on a shape."""

    operation: str = OPERATION_ENGRAVE  # cut | engrave | mark

    # Outline settings
    speed: int = 1000          # mm/min
    power: int = 500           # S value (0-1000)
    passes: int = 1            # number of outline passes (mainly for cut)

    # Fill settings (ignored for cut)
    fill_mode: str = "none"    # none | lines | schraffur | kreuz | dots | concentric
    fill_speed: int = 1500     # mm/min — faster than outline
    fill_power: int = 400      # S value — typically lower than outline
    fill_spacing: float = 0.5  # mm between fill lines
    fill_angle: float = 45.0   # degrees for schraffur

    def to_dict(self) -> dict:
        return {
            "operation": self.operation,
            "speed": self.speed,
            "power": self.power,
            "passes": self.passes,
            "fill_mode": self.fill_mode,
            "fill_speed": self.fill_speed,
            "fill_power": self.fill_power,
            "fill_spacing": self.fill_spacing,
            "fill_angle": self.fill_angle,
        }

    @classmethod
    def from_dict(cls, d: dict) -> OperationSettings:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ── Default settings per operation ──────────────────────────────────

DEFAULTS: dict[str, OperationSettings] = {
    OPERATION_CUT: OperationSettings(
        operation=OPERATION_CUT,
        speed=200,
        power=1000,
        passes=3,
        fill_mode="none",       # CUT never fills
        fill_speed=0,
        fill_power=0,
        fill_spacing=0,
    ),
    OPERATION_ENGRAVE: OperationSettings(
        operation=OPERATION_ENGRAVE,
        speed=1500,
        power=500,
        passes=1,
        fill_mode="lines",
        fill_speed=2000,
        fill_power=400,
        fill_spacing=0.5,
        fill_angle=45.0,
    ),
    OPERATION_MARK: OperationSettings(
        operation=OPERATION_MARK,
        speed=4000,
        power=150,
        passes=1,
        fill_mode="none",
        fill_speed=5000,
        fill_power=100,
        fill_spacing=0.3,
    ),
}


def default_settings(operation: str) -> OperationSettings:
    """Return a fresh copy of default settings for the given operation."""
    template = DEFAULTS.get(operation, DEFAULTS[OPERATION_ENGRAVE])
    return OperationSettings(**template.to_dict())


def operation_color(operation: str) -> str:
    """Return the display color for an operation type."""
    return OPERATION_META.get(operation, OPERATION_META[OPERATION_ENGRAVE])["color"]


def gcode_sort_key(operation: str) -> int:
    """Sort key for G-code export order: mark first, then engrave, then cut LAST.

    Cut always goes last — the cut may shift/release the material,
    so all engraving and marking must be done before cutting.
    This is industry standard (LightBurn does the same).
    """
    order = {OPERATION_MARK: 0, OPERATION_ENGRAVE: 1, OPERATION_CUT: 2}
    return order.get(operation, 1)


def operation_line_width(operation: str) -> int:
    """Return the display line width for an operation type."""
    return OPERATION_META.get(operation, OPERATION_META[OPERATION_ENGRAVE])["line_width"]


def operation_fill_color(operation: str) -> str:
    """Return the semi-transparent fill color for canvas preview."""
    return OPERATION_META.get(operation, OPERATION_META[OPERATION_ENGRAVE])["fill_color"]


def operation_label(operation: str) -> str:
    """Return the display label (with icon) for an operation type."""
    return OPERATION_META.get(operation, OPERATION_META[OPERATION_ENGRAVE])["label"]


@dataclass
class Layer:
    """A layer groups shapes with the same operation type."""

    name: str
    operation: str  # cut | engrave | mark
    color: str
    visible: bool = True
    locked: bool = False

    # Default settings for new shapes added to this layer
    defaults: OperationSettings = field(default_factory=lambda: default_settings(OPERATION_ENGRAVE))

    def __post_init__(self):
        if self.defaults.operation != self.operation:
            self.defaults = default_settings(self.operation)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "operation": self.operation,
            "color": self.color,
            "visible": self.visible,
            "locked": self.locked,
            "defaults": self.defaults.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> Layer:
        defaults = OperationSettings.from_dict(d.get("defaults", {}))
        return cls(
            name=d["name"],
            operation=d["operation"],
            color=d["color"],
            visible=d.get("visible", True),
            locked=d.get("locked", False),
            defaults=defaults,
        )


# ── Default layer presets ───────────────────────────────────────────

DEFAULT_LAYERS = [
    Layer(name="Cut", operation=OPERATION_CUT, color="#FF3333"),
    Layer(name="Engrave", operation=OPERATION_ENGRAVE, color="#3399FF"),
    Layer(name="Mark", operation=OPERATION_MARK, color="#33CC33"),
]


def create_default_layers() -> list[Layer]:
    """Return fresh default layers."""
    return [Layer.from_dict(layer.to_dict()) for layer in DEFAULT_LAYERS]
