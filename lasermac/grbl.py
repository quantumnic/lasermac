"""GRBL serial controller for LaserMac.

Handles serial communication with GRBL-based CNC/laser machines.
Provides command queuing, status polling, and real-time control.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from queue import Queue

import serial
import serial.tools.list_ports


@dataclass
class GrblStatus:
    """Current machine status."""

    state: str = "Unknown"
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    feed: float = 0.0
    speed: float = 0.0
    buffer_available: int = 15

    @classmethod
    def parse(cls, response: str) -> GrblStatus:
        """Parse GRBL status response like <Idle|MPos:0.000,0.000,0.000|...>."""
        status = cls()
        response = response.strip("<>")
        parts = response.split("|")
        if parts:
            status.state = parts[0]
        for part in parts[1:]:
            if part.startswith("MPos:") or part.startswith("WPos:"):
                coords = part.split(":")[1].split(",")
                if len(coords) >= 2:
                    status.x = float(coords[0])
                    status.y = float(coords[1])
                if len(coords) >= 3:
                    status.z = float(coords[2])
            elif part.startswith("FS:") or part.startswith("F:"):
                vals = part.split(":")[1].split(",")
                status.feed = float(vals[0])
                if len(vals) > 1:
                    status.speed = float(vals[1])
            elif part.startswith("Bf:"):
                vals = part.split(":")[1].split(",")
                status.buffer_available = int(vals[0])
        return status


class GrblController:
    """Controls a GRBL device over serial."""

    def __init__(self) -> None:
        self.serial: serial.Serial | None = None
        self.connected = False
        self._read_thread: threading.Thread | None = None
        self._status_thread: threading.Thread | None = None
        self._running = False
        self._command_queue: Queue[str] = Queue()
        self._pending_commands: list[str] = []
        self._lock = threading.Lock()

        # Current status
        self.status = GrblStatus()

        # Callbacks
        self.on_status: Callable[[GrblStatus], None] | None = None
        self.on_message: Callable[[str], None] | None = None
        self.on_alarm: Callable[[str], None] | None = None
        self.on_ok: Callable[[], None] | None = None
        self.on_error: Callable[[str], None] | None = None
        self.on_connect: Callable[[bool], None] | None = None

    @staticmethod
    def list_ports() -> list[str]:
        """List available serial ports (macOS: /dev/cu.*)."""
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports if "cu." in p.device or "tty." in p.device]

    def connect(self, port: str, baud: int = 115200) -> bool:
        """Connect to GRBL device."""
        try:
            self.serial = serial.Serial(port, baud, timeout=0.1)
            time.sleep(2)  # GRBL reset delay
            self.serial.flushInput()
            self.connected = True
            self._running = True

            # Start read thread
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()

            # Start status polling
            self._status_thread = threading.Thread(target=self._status_loop, daemon=True)
            self._status_thread.start()

            if self.on_connect:
                self.on_connect(True)
            if self.on_message:
                self.on_message(f"Connected to {port} @ {baud}")
            return True
        except (serial.SerialException, OSError) as e:
            if self.on_message:
                self.on_message(f"Connection failed: {e}")
            if self.on_connect:
                self.on_connect(False)
            return False

    def disconnect(self) -> None:
        """Disconnect from GRBL device."""
        self._running = False
        self.connected = False
        if self.serial and self.serial.is_open:
            self.serial.close()
        self.serial = None
        if self.on_connect:
            self.on_connect(False)
        if self.on_message:
            self.on_message("Disconnected")

    def send_command(self, cmd: str) -> None:
        """Queue a G-code command for sending."""
        cmd = cmd.strip()
        if not cmd:
            return
        self._command_queue.put(cmd)

    def send_realtime(self, char: str) -> None:
        """Send a real-time GRBL character (no queue)."""
        if self.serial and self.serial.is_open:
            self.serial.write(char.encode())

    def home(self) -> None:
        """Run homing cycle."""
        self.send_command("$H")

    def unlock(self) -> None:
        """Unlock GRBL ($X)."""
        self.send_command("$X")

    def soft_reset(self) -> None:
        """Send soft reset (Ctrl+X)."""
        self.send_realtime("\x18")

    def jog(self, axis: str, distance: float, feed_rate: int = 1000) -> None:
        """Send jog command. axis: 'X', 'Y', or 'Z'."""
        cmd = f"$J=G91 {axis}{distance:.3f} F{feed_rate}"
        self.send_command(cmd)

    def jog_cancel(self) -> None:
        """Cancel current jog."""
        self.send_realtime("\x85")

    def set_origin(self) -> None:
        """Set current position as work origin."""
        self.send_command("G92 X0 Y0 Z0")

    def go_to_origin(self, feed: int = 1000) -> None:
        """Move to work origin."""
        self.send_command(f"G90 G0 X0 Y0 F{feed}")

    def run_frame(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        feed: int = 1000,
    ) -> None:
        """Trace bounding box with laser off."""
        commands = [
            "M5 S0",  # Laser off
            "G90",  # Absolute positioning
            f"G0 X{min_x:.3f} Y{min_y:.3f} F{feed}",
            f"G1 X{max_x:.3f} Y{min_y:.3f} F{feed}",
            f"G1 X{max_x:.3f} Y{max_y:.3f} F{feed}",
            f"G1 X{min_x:.3f} Y{max_y:.3f} F{feed}",
            f"G1 X{min_x:.3f} Y{min_y:.3f} F{feed}",
        ]
        for cmd in commands:
            self.send_command(cmd)

    def feed_hold(self) -> None:
        """Pause execution (!)."""
        self.send_realtime("!")

    def resume(self) -> None:
        """Resume execution (~)."""
        self.send_realtime("~")

    def get_status(self) -> GrblStatus:
        """Return current status."""
        return self.status

    def _read_loop(self) -> None:
        """Background thread: read serial data and process commands."""
        while self._running and self.serial and self.serial.is_open:
            try:
                # Send queued commands
                if not self._command_queue.empty() and self.status.buffer_available > 0:
                    cmd = self._command_queue.get_nowait()
                    line = cmd + "\n"
                    self.serial.write(line.encode())
                    with self._lock:
                        self._pending_commands.append(cmd)
                    if self.on_message:
                        self.on_message(f">>> {cmd}")

                # Read response
                if self.serial.in_waiting:
                    line = self.serial.readline().decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    self._process_response(line)
            except (serial.SerialException, OSError):
                self._running = False
                self.connected = False
                if self.on_message:
                    self.on_message("Serial connection lost")
                break
            except Exception:
                pass
            time.sleep(0.01)

    def _status_loop(self) -> None:
        """Background thread: poll GRBL status every 200ms."""
        while self._running and self.serial and self.serial.is_open:
            try:
                self.serial.write(b"?")
            except (serial.SerialException, OSError):
                break
            time.sleep(0.2)

    def _process_response(self, line: str) -> None:
        """Process a line of GRBL output."""
        if line.startswith("<") and line.endswith(">"):
            self.status = GrblStatus.parse(line)
            if self.on_status:
                self.on_status(self.status)
        elif line == "ok":
            with self._lock:
                if self._pending_commands:
                    self._pending_commands.pop(0)
            if self.on_ok:
                self.on_ok()
        elif line.startswith("ALARM:"):
            if self.on_alarm:
                self.on_alarm(line)
            if self.on_message:
                self.on_message(f"⚠️ {line}")
        elif line.startswith("error:"):
            if self.on_error:
                self.on_error(line)
            if self.on_message:
                self.on_message(f"❌ {line}")
        else:
            if self.on_message:
                self.on_message(line)

    @staticmethod
    def generate_jog_gcode(axis: str, distance: float, feed_rate: int = 1000) -> str:
        """Generate jog G-code string (useful for testing)."""
        return f"$J=G91 {axis}{distance:.3f} F{feed_rate}"

    @staticmethod
    def parse_status_response(response: str) -> dict:
        """Parse a status response into a dict (convenience for testing)."""
        s = GrblStatus.parse(response)
        return {"state": s.state, "x": s.x, "y": s.y, "z": s.z}
