"""G-code file parser and sender for LaserMac.

Loads G-code files, tracks progress, and streams lines to GRBL.
Enhanced with time estimation and G-code export headers.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class GcodeJob:
    """Represents a loaded G-code job."""

    lines: list[str] = field(default_factory=list)
    filename: str = ""
    total_lines: int = 0
    current_line: int = 0
    running: bool = False
    paused: bool = False
    bounds: tuple[float, float, float, float] = (0, 0, 0, 0)  # min_x, min_y, max_x, max_y

    @property
    def progress(self) -> float:
        """Return progress as 0.0–1.0."""
        if self.total_lines == 0:
            return 0.0
        return self.current_line / self.total_lines

    @property
    def progress_percent(self) -> float:
        """Return progress as 0–100."""
        return self.progress * 100.0

    @property
    def bounds_size(self) -> tuple[float, float]:
        """Return width and height of bounding box in mm."""
        return (self.bounds[2] - self.bounds[0], self.bounds[3] - self.bounds[1])

    @property
    def estimated_time(self) -> float:
        """Return estimated job time in seconds."""
        return estimate_time(self.lines)

    @property
    def estimated_time_str(self) -> str:
        """Return estimated time as human-readable string."""
        t = self.estimated_time
        if t < 60:
            return f"{t:.0f}s"
        mins = int(t // 60)
        secs = int(t % 60)
        if mins < 60:
            return f"{mins}m{secs:02d}s"
        hours = mins // 60
        mins = mins % 60
        return f"{hours}h{mins:02d}m"


GCODE_EXTENSIONS = {".nc", ".gcode", ".gc", ".ngc", ".tap"}


def load_gcode(filepath: str) -> GcodeJob:
    """Load a G-code file and return a GcodeJob."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    ext = path.suffix.lower()
    if ext not in GCODE_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}. Expected: {GCODE_EXTENSIONS}")

    with open(path) as f:
        raw_lines = f.readlines()

    # Clean and filter lines
    lines = []
    for line in raw_lines:
        line = line.strip()
        # Remove comments
        line = re.sub(r"\(.*?\)", "", line)  # parenthetical comments
        line = re.sub(r";.*$", "", line)  # semicolon comments
        line = line.strip()
        if line:
            lines.append(line)

    # Calculate bounds
    bounds = _calculate_bounds(lines)

    return GcodeJob(
        lines=lines,
        filename=path.name,
        total_lines=len(lines),
        bounds=bounds,
    )


def load_gcode_from_string(gcode: str, name: str = "generated") -> GcodeJob:
    """Load G-code from a string."""
    lines = []
    for line in gcode.splitlines():
        line = line.strip()
        line = re.sub(r"\(.*?\)", "", line)
        line = re.sub(r";.*$", "", line)
        line = line.strip()
        if line:
            lines.append(line)

    bounds = _calculate_bounds(lines)

    return GcodeJob(
        lines=lines,
        filename=name,
        total_lines=len(lines),
        bounds=bounds,
    )


def _calculate_bounds(lines: list[str]) -> tuple[float, float, float, float]:
    """Calculate bounding box from G-code lines."""
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    found = False

    x_pattern = re.compile(r"X([-+]?\d*\.?\d+)")
    y_pattern = re.compile(r"Y([-+]?\d*\.?\d+)")

    for line in lines:
        x_match = x_pattern.search(line)
        y_match = y_pattern.search(line)
        if x_match:
            x = float(x_match.group(1))
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            found = True
        if y_match:
            y = float(y_match.group(1))
            min_y = min(min_y, y)
            max_y = max(max_y, y)
            found = True

    if not found:
        return (0, 0, 0, 0)
    return (min_x, min_y, max_x, max_y)


def estimate_time(lines: list[str], default_feed: float = 1000.0) -> float:
    """Estimate job time in seconds from G-code lines."""
    total_time = 0.0
    current_x = current_y = 0.0
    feed = default_feed

    x_pattern = re.compile(r"X([-+]?\d*\.?\d+)")
    y_pattern = re.compile(r"Y([-+]?\d*\.?\d+)")
    f_pattern = re.compile(r"F([-+]?\d*\.?\d+)")

    for line in lines:
        f_match = f_pattern.search(line)
        if f_match:
            feed = float(f_match.group(1))

        x_match = x_pattern.search(line)
        y_match = y_pattern.search(line)

        new_x = float(x_match.group(1)) if x_match else current_x
        new_y = float(y_match.group(1)) if y_match else current_y

        if x_match or y_match:
            dist = ((new_x - current_x) ** 2 + (new_y - current_y) ** 2) ** 0.5
            if feed > 0:
                total_time += (dist / feed) * 60  # feed is mm/min → seconds
            current_x = new_x
            current_y = new_y

    return total_time


class GcodeSender:
    """Streams G-code lines to a GRBL controller."""

    def __init__(self, grbl_controller) -> None:
        self.grbl = grbl_controller
        self.job: GcodeJob | None = None
        self.on_progress: Callable[[float], None] | None = None
        self.on_complete: Callable[[], None] | None = None
        self._stop_flag = False

    def start(self, job: GcodeJob) -> None:
        """Start sending a job."""
        self.job = job
        self.job.running = True
        self.job.paused = False
        self.job.current_line = 0
        self._stop_flag = False

        import threading

        t = threading.Thread(target=self._send_loop, daemon=True)
        t.start()

    def pause(self) -> None:
        """Pause the current job."""
        if self.job:
            self.job.paused = True
            self.grbl.feed_hold()

    def resume(self) -> None:
        """Resume the current job."""
        if self.job:
            self.job.paused = False
            self.grbl.resume()

    def stop(self) -> None:
        """Stop the current job."""
        self._stop_flag = True
        if self.job:
            self.job.running = False
        self.grbl.soft_reset()

    def _send_loop(self) -> None:
        """Send G-code lines one by one."""
        if not self.job:
            return

        for i, line in enumerate(self.job.lines):
            if self._stop_flag:
                break

            while self.job.paused and not self._stop_flag:
                time.sleep(0.1)

            self.grbl.send_command(line)
            self.job.current_line = i + 1

            if self.on_progress:
                self.on_progress(self.job.progress)

            # Simple flow control: wait a bit between lines
            time.sleep(0.01)

        self.job.running = False
        if self.on_complete and not self._stop_flag:
            self.on_complete()


def export_gcode_with_header(
    gcode_lines: list[str],
    machine_name: str = "Unknown",
    job_name: str = "Untitled",
) -> str:
    """Wrap G-code with a descriptive header comment block."""
    bounds = _calculate_bounds(gcode_lines)
    est = estimate_time(gcode_lines)
    mins = int(est // 60)
    secs = int(est % 60)

    header = [
        "; ── LaserMac G-code Export ──",
        f"; Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"; Machine: {machine_name}",
        f"; Job: {job_name}",
        f"; Lines: {len(gcode_lines)}",
        f"; Bounds: X[{bounds[0]:.1f} .. {bounds[2]:.1f}] Y[{bounds[1]:.1f} .. {bounds[3]:.1f}]",
        f"; Size: {bounds[2] - bounds[0]:.1f} x {bounds[3] - bounds[1]:.1f} mm",
        f"; Est. time: {mins}m{secs:02d}s",
        "; ──────────────────────────────",
        "",
    ]
    return "\n".join(header + gcode_lines)
