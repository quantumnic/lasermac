"""G-code toolpath preview for LaserMac.

Renders G-code toolpaths on a matplotlib canvas for visual preview.
"""

from __future__ import annotations

import re

import matplotlib

matplotlib.use("TkAgg")

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


def parse_gcode_for_preview(gcode_lines: list[str]) -> list[dict]:
    """Parse G-code lines into move segments for preview.

    Returns list of dicts: {"x": float, "y": float, "type": "rapid"|"cut", "power": int}
    """
    segments: list[dict] = []
    current_x = 0.0
    current_y = 0.0
    current_power = 0

    x_pat = re.compile(r"X([-+]?\d*\.?\d+)")
    y_pat = re.compile(r"Y([-+]?\d*\.?\d+)")
    s_pat = re.compile(r"S(\d+)")

    for line in gcode_lines:
        line = line.strip()
        if not line or line.startswith(";") or line.startswith("("):
            continue

        # Track power
        s_match = s_pat.search(line)
        if s_match:
            current_power = int(s_match.group(1))

        if line.startswith("M5"):
            current_power = 0

        x_match = x_pat.search(line)
        y_match = y_pat.search(line)

        if x_match or y_match:
            new_x = float(x_match.group(1)) if x_match else current_x
            new_y = float(y_match.group(1)) if y_match else current_y

            move_type = "cut" if (line.startswith("G1") and current_power > 0) else "rapid"

            segments.append({
                "x0": current_x, "y0": current_y,
                "x1": new_x, "y1": new_y,
                "type": move_type,
                "power": current_power,
            })

            current_x = new_x
            current_y = new_y

    return segments


class PreviewCanvas:
    """Matplotlib canvas for G-code preview in a Tkinter frame."""

    def __init__(self, parent) -> None:
        self.figure = Figure(figsize=(5, 5), dpi=100, facecolor="#1a1a1a")
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor("#1a1a1a")
        self.ax.tick_params(colors="#888888")
        self.ax.spines["bottom"].set_color("#444444")
        self.ax.spines["top"].set_color("#444444")
        self.ax.spines["left"].set_color("#444444")
        self.ax.spines["right"].set_color("#444444")

        self.canvas = FigureCanvasTkAgg(self.figure, master=parent)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def draw_gcode(self, gcode_lines: list[str]) -> None:
        """Render G-code toolpath."""
        self.ax.clear()
        self.ax.set_facecolor("#1a1a1a")
        self.ax.set_aspect("equal")
        self.ax.set_xlabel("X (mm)", color="#888888")
        self.ax.set_ylabel("Y (mm)", color="#888888")
        self.ax.set_title("Toolpath Preview", color="#cccccc")

        segments = parse_gcode_for_preview(gcode_lines)

        for seg in segments:
            if seg["type"] == "cut":
                color = "#00ff88"
                alpha = min(0.3 + seg["power"] / 1000 * 0.7, 1.0)
                lw = 0.5
            else:
                color = "#444444"
                alpha = 0.3
                lw = 0.3

            self.ax.plot(
                [seg["x0"], seg["x1"]],
                [seg["y0"], seg["y1"]],
                color=color, alpha=alpha, linewidth=lw,
            )

        self.ax.grid(True, color="#333333", alpha=0.5)
        self.figure.tight_layout()
        self.canvas.draw()

    def clear(self) -> None:
        """Clear the preview."""
        self.ax.clear()
        self.ax.set_facecolor("#1a1a1a")
        self.canvas.draw()
