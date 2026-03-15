"""Power tester — generates a speed × power test grid.

Burns a grid of squares with varying speed (Y axis) and power (X axis),
each labeled with its settings. One-click material test.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PowerTestConfig:
    """Configuration for a power test grid."""

    power_min: int = 100
    power_max: int = 1000
    power_steps: int = 5
    speed_min: int = 200
    speed_max: int = 3000
    speed_steps: int = 5
    square_size: float = 5.0    # mm
    spacing: float = 3.0        # mm between squares
    label_height: float = 2.0   # mm for text labels
    origin_x: float = 0.0
    origin_y: float = 0.0


def generate_power_test(cfg: PowerTestConfig | None = None) -> str:
    """Generate G-code for a power test grid.

    X axis = power (S values), Y axis = speed (F values).
    Each square is filled with horizontal lines.
    """
    if cfg is None:
        cfg = PowerTestConfig()

    lines: list[str] = []
    lines.append("; LaserMac Power Test Grid")
    lines.append(f"; Power: S{cfg.power_min} to S{cfg.power_max} ({cfg.power_steps} steps)")
    lines.append(f"; Speed: F{cfg.speed_min} to F{cfg.speed_max} ({cfg.speed_steps} steps)")
    lines.append(f"; Square size: {cfg.square_size}mm")
    lines.append("G21 ; mm")
    lines.append("G90 ; absolute")
    lines.append("M5 S0")
    lines.append("")

    # Calculate step sizes
    if cfg.power_steps <= 1:
        power_values = [cfg.power_min]
    else:
        power_step = (cfg.power_max - cfg.power_min) / (cfg.power_steps - 1)
        power_values = [int(cfg.power_min + i * power_step) for i in range(cfg.power_steps)]

    if cfg.speed_steps <= 1:
        speed_values = [cfg.speed_min]
    else:
        speed_step = (cfg.speed_max - cfg.speed_min) / (cfg.speed_steps - 1)
        speed_values = [int(cfg.speed_min + i * speed_step) for i in range(cfg.speed_steps)]

    cell_w = cfg.square_size + cfg.spacing
    cell_h = cfg.square_size + cfg.spacing + cfg.label_height

    for row, speed in enumerate(speed_values):
        for col, power in enumerate(power_values):
            x0 = cfg.origin_x + col * cell_w
            y0 = cfg.origin_y + row * cell_h
            x1 = x0 + cfg.square_size
            y1 = y0 + cfg.square_size

            lines.append(f"; Square: S{power} F{speed}")

            # Outline
            lines.append(f"G0 X{x0:.2f} Y{y0:.2f} S0")
            lines.append(f"M3 S{power}")
            lines.append(f"G1 X{x1:.2f} Y{y0:.2f} F{speed}")
            lines.append(f"G1 X{x1:.2f} Y{y1:.2f} F{speed}")
            lines.append(f"G1 X{x0:.2f} Y{y1:.2f} F{speed}")
            lines.append(f"G1 X{x0:.2f} Y{y0:.2f} F{speed}")

            # Fill with horizontal lines (0.3mm spacing)
            fill_spacing = 0.3
            y = y0 + fill_spacing
            toggle = True
            while y < y1 - 0.1:
                if toggle:
                    lines.append(f"G0 X{x0:.2f} Y{y:.2f} S0")
                    lines.append(f"M3 S{power}")
                    lines.append(f"G1 X{x1:.2f} Y{y:.2f} F{speed}")
                else:
                    lines.append(f"G0 X{x1:.2f} Y{y:.2f} S0")
                    lines.append(f"M3 S{power}")
                    lines.append(f"G1 X{x0:.2f} Y{y:.2f} F{speed}")
                lines.append("M5 S0")
                y += fill_spacing
                toggle = not toggle

            lines.append("M5 S0")
            lines.append("")

    lines.append("M5 S0")
    lines.append("G0 X0 Y0")
    lines.append("")
    return "\n".join(lines)


def test_grid_bounds(cfg: PowerTestConfig | None = None) -> tuple[float, float, float, float]:
    """Return bounding box (min_x, min_y, max_x, max_y) of the test grid."""
    if cfg is None:
        cfg = PowerTestConfig()

    cell_w = cfg.square_size + cfg.spacing
    cell_h = cfg.square_size + cfg.spacing + cfg.label_height

    max_x = cfg.origin_x + cfg.power_steps * cell_w - cfg.spacing
    max_y = cfg.origin_y + cfg.speed_steps * cell_h - cfg.spacing - cfg.label_height

    return (cfg.origin_x, cfg.origin_y, max_x, max_y)
