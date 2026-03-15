"""LaserMac CLI — control laser engravers from the command line.

Designed for AI tool use: all output is JSON by default.

Usage:
  lasermac-cli <command> [options]
  lasermac-cli --help
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import click

STATE_DIR = Path.home() / ".lasermac"
STATE_FILE = STATE_DIR / "cli_state.json"


# ── State persistence ───────────────────────────────────────────────


def _load_state() -> dict:
    """Load CLI state from disk."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_state(state: dict) -> None:
    """Save CLI state to disk."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ── Output helpers ──────────────────────────────────────────────────


def _output(data: dict, plain: bool = False, verbose: bool = False) -> None:
    """Print result and exit with appropriate code."""
    ok = data.get("ok", True)
    if plain:
        if ok:
            for k, v in data.items():
                if k == "ok":
                    continue
                click.echo(f"{k}: {v}")
        else:
            click.echo(f"Error: {data.get('error', 'unknown')}", err=True)
    else:
        click.echo(json.dumps(data, indent=2))
    sys.exit(0 if ok else 1)


def _error(message: str, code: str = "ERROR", plain: bool = False) -> None:
    """Output an error and exit 1."""
    _output({"ok": False, "error": message, "code": code}, plain=plain)


def _get_controller(state: dict, plain: bool = False, timeout: float = 5.0):
    """Create a GrblController and connect using saved state."""
    from lasermac.grbl import GrblController

    port = state.get("port")
    baud = state.get("baud", 115200)
    if not port:
        _error("Not connected to any device. Run: lasermac-cli connect", "NOT_CONNECTED", plain)

    ctrl = GrblController()
    try:
        import serial as _serial

        ctrl.serial = _serial.Serial(port, baud, timeout=0.1)
        # Brief wait for GRBL to initialize
        time.sleep(0.5)
        ctrl.serial.flushInput()
        ctrl.connected = True
    except Exception as e:
        _error(f"Cannot open {port}: {e}", "CONNECTION_FAILED", plain)

    return ctrl


def _send_and_wait(ctrl, command: str, timeout: float = 10.0) -> tuple[str, float]:
    """Send a command and wait for 'ok' or 'error' response.

    Returns (response_line, elapsed_ms).
    """
    start = time.monotonic()
    ctrl.serial.flushInput()
    ctrl.serial.write((command.strip() + "\n").encode())

    deadline = start + timeout
    while time.monotonic() < deadline:
        if ctrl.serial.in_waiting:
            line = ctrl.serial.readline().decode("utf-8", errors="replace").strip()
            if line == "ok" or line.startswith("error:"):
                elapsed = (time.monotonic() - start) * 1000
                return line, elapsed
            # Skip status lines
            if line.startswith("<") and line.endswith(">"):
                continue
        time.sleep(0.01)

    elapsed = (time.monotonic() - start) * 1000
    return "timeout", elapsed


def _query_status(ctrl, timeout: float = 3.0) -> dict:
    """Send ? and parse status response."""
    ctrl.serial.flushInput()
    ctrl.serial.write(b"?")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if ctrl.serial.in_waiting:
            line = ctrl.serial.readline().decode("utf-8", errors="replace").strip()
            if line.startswith("<") and line.endswith(">"):
                from lasermac.grbl import GrblStatus

                s = GrblStatus.parse(line)
                return {
                    "state": s.state,
                    "x": s.x,
                    "y": s.y,
                    "z": s.z,
                    "feed": s.feed,
                    "spindle": s.speed,
                }
        time.sleep(0.01)
    return {"state": "Unknown", "x": 0.0, "y": 0.0, "z": 0.0, "feed": 0, "spindle": 0}


# ── CLI group ───────────────────────────────────────────────────────


@click.group()
@click.option("--plain", is_flag=True, help="Human-readable output instead of JSON.")
@click.option("--verbose", is_flag=True, help="Show debug information.")
@click.pass_context
def cli(ctx: click.Context, plain: bool, verbose: bool) -> None:
    """LaserMac CLI — AI-friendly laser engraver control.

    All commands output JSON by default. Use --plain for human-readable output.
    """
    ctx.ensure_object(dict)
    ctx.obj["plain"] = plain
    ctx.obj["verbose"] = verbose


# ── Connection commands ─────────────────────────────────────────────


@cli.command()
@click.option("--port", default=None, help="Serial port (e.g. /dev/cu.usbserial-0001).")
@click.option("--baud", default=115200, type=int, help="Baud rate (default: 115200).")
@click.pass_context
def connect(ctx: click.Context, port: str | None, baud: int) -> None:
    """Connect to a GRBL laser engraver."""
    plain = ctx.obj["plain"]

    if not port:
        # Auto-detect
        from lasermac.grbl import GrblController

        ports = GrblController.list_ports()
        if not ports:
            _error("No serial ports found", "NO_PORTS", plain)
        port = ports[0]

    # Try connecting
    from lasermac.grbl import GrblController

    ctrl = GrblController()
    success = ctrl.connect(port, baud)

    if success:
        _save_state({"port": port, "baud": baud, "connected": True})
        ctrl.disconnect()
        _output({"ok": True, "port": port, "baud": baud, "message": f"Connected to {port}"}, plain)
    else:
        _error(f"Failed to connect to {port}", "CONNECTION_FAILED", plain)


@cli.command()
@click.pass_context
def disconnect(ctx: click.Context) -> None:
    """Disconnect and clear saved connection."""
    plain = ctx.obj["plain"]
    state = _load_state()
    state["connected"] = False
    _save_state(state)
    _output({"ok": True, "message": "Disconnected"}, plain)


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Get current machine status (JSON)."""
    plain = ctx.obj["plain"]
    state = _load_state()

    if not state.get("port"):
        _error("Not connected to any device", "NOT_CONNECTED", plain)

    ctrl = _get_controller(state, plain)
    try:
        s = _query_status(ctrl)
        result = {
            "ok": True,
            "connected": True,
            "port": state.get("port"),
            **s,
        }
        _output(result, plain)
    finally:
        if ctrl.serial and ctrl.serial.is_open:
            ctrl.serial.close()


@cli.command()
@click.pass_context
def ports(ctx: click.Context) -> None:
    """List available serial ports."""
    plain = ctx.obj["plain"]
    from lasermac.grbl import GrblController

    port_list = GrblController.list_ports_detail()
    _output({"ok": True, "ports": port_list}, plain)


# ── Machine control ─────────────────────────────────────────────────


@cli.command()
@click.pass_context
def home(ctx: click.Context) -> None:
    """Run homing cycle ($H)."""
    plain = ctx.obj["plain"]
    state = _load_state()
    ctrl = _get_controller(state, plain)
    try:
        resp, ms = _send_and_wait(ctrl, "$H", timeout=30.0)
        _output({"ok": resp == "ok", "command": "$H", "response": resp, "elapsed_ms": round(ms)}, plain)
    finally:
        if ctrl.serial and ctrl.serial.is_open:
            ctrl.serial.close()


@cli.command()
@click.pass_context
def unlock(ctx: click.Context) -> None:
    """Soft unlock ($X)."""
    plain = ctx.obj["plain"]
    state = _load_state()
    ctrl = _get_controller(state, plain)
    try:
        resp, ms = _send_and_wait(ctrl, "$X")
        _output({"ok": resp == "ok", "command": "$X", "response": resp, "elapsed_ms": round(ms)}, plain)
    finally:
        if ctrl.serial and ctrl.serial.is_open:
            ctrl.serial.close()


@cli.command()
@click.pass_context
def reset(ctx: click.Context) -> None:
    """Soft reset (Ctrl-X)."""
    plain = ctx.obj["plain"]
    state = _load_state()
    ctrl = _get_controller(state, plain)
    try:
        ctrl.serial.write(b"\x18")
        time.sleep(0.5)
        _output({"ok": True, "command": "soft-reset", "message": "Reset sent"}, plain)
    finally:
        if ctrl.serial and ctrl.serial.is_open:
            ctrl.serial.close()


@cli.command()
@click.pass_context
def origin(ctx: click.Context) -> None:
    """Set current position as work origin (G92 X0 Y0)."""
    plain = ctx.obj["plain"]
    state = _load_state()
    ctrl = _get_controller(state, plain)
    try:
        resp, ms = _send_and_wait(ctrl, "G92 X0 Y0 Z0")
        _output({"ok": resp == "ok", "command": "G92 X0 Y0 Z0", "response": resp, "elapsed_ms": round(ms)}, plain)
    finally:
        if ctrl.serial and ctrl.serial.is_open:
            ctrl.serial.close()


@cli.command("goto")
@click.option("--x", "x_pos", type=float, required=True, help="X position (mm).")
@click.option("--y", "y_pos", type=float, required=True, help="Y position (mm).")
@click.option("--feed", default=1000, type=int, help="Feed rate mm/min (default: 1000).")
@click.pass_context
def goto_cmd(ctx: click.Context, x_pos: float, y_pos: float, feed: int) -> None:
    """Move to absolute position."""
    plain = ctx.obj["plain"]
    state = _load_state()
    ctrl = _get_controller(state, plain)
    cmd = f"G90 G0 X{x_pos:.3f} Y{y_pos:.3f} F{feed}"
    try:
        resp, ms = _send_and_wait(ctrl, cmd, timeout=30.0)
        _output({"ok": resp == "ok", "command": cmd, "response": resp, "elapsed_ms": round(ms)}, plain)
    finally:
        if ctrl.serial and ctrl.serial.is_open:
            ctrl.serial.close()


@cli.command()
@click.option("--axis", required=True, type=click.Choice(["X", "Y", "Z"], case_sensitive=False), help="Axis to jog.")
@click.option("--distance", required=True, type=float, help="Distance in mm (negative = reverse).")
@click.option("--feed", default=1000, type=int, help="Feed rate mm/min (default: 1000).")
@click.pass_context
def jog(ctx: click.Context, axis: str, distance: float, feed: int) -> None:
    """Relative jog movement."""
    plain = ctx.obj["plain"]
    state = _load_state()
    ctrl = _get_controller(state, plain)
    axis = axis.upper()
    cmd = f"$J=G91G21 {axis}{distance:.3f} F{feed}"
    try:
        resp, ms = _send_and_wait(ctrl, cmd)
        _output({"ok": resp == "ok", "command": cmd, "response": resp, "elapsed_ms": round(ms)}, plain)
    finally:
        if ctrl.serial and ctrl.serial.is_open:
            ctrl.serial.close()


# ── Laser commands ──────────────────────────────────────────────────


@cli.command("laser-on")
@click.option("--power", required=True, type=int, help="Spindle power (0-1000).")
@click.pass_context
def laser_on(ctx: click.Context, power: int) -> None:
    """Turn laser on (M3 Sxxx)."""
    plain = ctx.obj["plain"]
    state = _load_state()
    ctrl = _get_controller(state, plain)
    cmd = f"M3 S{power}"
    try:
        resp, ms = _send_and_wait(ctrl, cmd)
        _output({"ok": resp == "ok", "command": cmd, "response": resp, "elapsed_ms": round(ms)}, plain)
    finally:
        if ctrl.serial and ctrl.serial.is_open:
            ctrl.serial.close()


@cli.command("laser-off")
@click.pass_context
def laser_off(ctx: click.Context) -> None:
    """Turn laser off (M5)."""
    plain = ctx.obj["plain"]
    state = _load_state()
    ctrl = _get_controller(state, plain)
    try:
        resp, ms = _send_and_wait(ctrl, "M5")
        _output({"ok": resp == "ok", "command": "M5", "response": resp, "elapsed_ms": round(ms)}, plain)
    finally:
        if ctrl.serial and ctrl.serial.is_open:
            ctrl.serial.close()


@cli.command("laser-test")
@click.option("--power", required=True, type=int, help="Spindle power (0-1000).")
@click.option("--duration", required=True, type=float, help="Duration in seconds.")
@click.pass_context
def laser_test(ctx: click.Context, power: int, duration: float) -> None:
    """Pulse laser for N seconds then turn off."""
    plain = ctx.obj["plain"]
    state = _load_state()
    ctrl = _get_controller(state, plain)
    try:
        resp_on, _ = _send_and_wait(ctrl, f"M3 S{power}")
        if resp_on != "ok":
            _error(f"Failed to turn laser on: {resp_on}", "LASER_ERROR", plain)
        time.sleep(duration)
        resp_off, ms = _send_and_wait(ctrl, "M5")
        _output({
            "ok": resp_off == "ok",
            "command": f"laser-test power={power} duration={duration}s",
            "response": "ok",
            "elapsed_ms": round(duration * 1000),
        }, plain)
    finally:
        # Safety: always try to turn laser off
        try:
            ctrl.serial.write(b"M5\n")
        except Exception:
            pass
        if ctrl.serial and ctrl.serial.is_open:
            ctrl.serial.close()


# ── Job control ─────────────────────────────────────────────────────


@cli.command()
@click.option("--file", "filepath", default=None, help="G-code file to send.")
@click.option("--gcode", default=None, help="Raw G-code string to send.")
@click.pass_context
def send(ctx: click.Context, filepath: str | None, gcode: str | None) -> None:
    """Send G-code file or raw command."""
    plain = ctx.obj["plain"]

    if not filepath and not gcode:
        _error("Provide --file or --gcode", "MISSING_ARG", plain)

    state = _load_state()
    ctrl = _get_controller(state, plain)

    try:
        if gcode:
            # Single command or multi-line
            lines = [ln.strip() for ln in gcode.splitlines() if ln.strip()]
        else:
            path = Path(filepath)
            if not path.exists():
                _error(f"File not found: {filepath}", "FILE_NOT_FOUND", plain)
            lines = [ln.strip() for ln in path.read_text().splitlines() if ln.strip() and not ln.startswith(";")]

        results = []
        start = time.monotonic()
        for line in lines:
            resp, ms = _send_and_wait(ctrl, line)
            results.append({"command": line, "response": resp})
            if resp.startswith("error:"):
                total_ms = (time.monotonic() - start) * 1000
                _output({
                    "ok": False,
                    "error": f"G-code error on '{line}': {resp}",
                    "code": "GCODE_ERROR",
                    "line": line,
                    "results": results,
                    "elapsed_ms": round(total_ms),
                }, plain)

        total_ms = (time.monotonic() - start) * 1000
        _output({
            "ok": True,
            "lines_sent": len(lines),
            "command": gcode if gcode and len(lines) == 1 else f"{len(lines)} lines",
            "response": "ok",
            "elapsed_ms": round(total_ms),
        }, plain)
    finally:
        if ctrl.serial and ctrl.serial.is_open:
            ctrl.serial.close()


@cli.command("burn-text")
@click.option("--text", required=True, help="Text to engrave.")
@click.option("--x", "x_pos", type=float, default=0, help="Start X position.")
@click.option("--y", "y_pos", type=float, default=0, help="Start Y position.")
@click.option("--size", type=float, default=10, help="Font size in mm.")
@click.option("--power", type=int, default=800, help="Laser power (0-1000).")
@click.option("--speed", type=int, default=600, help="Feed rate mm/min.")
@click.pass_context
def burn_text(ctx: click.Context, text: str, x_pos: float, y_pos: float,
              size: float, power: int, speed: int) -> None:
    """Engrave text using single-stroke font."""
    plain = ctx.obj["plain"]
    gcode_lines = _generate_text_gcode(text, x_pos, y_pos, size, power, speed)
    state = _load_state()
    ctrl = _get_controller(state, plain)
    try:
        start = time.monotonic()
        for line in gcode_lines:
            resp, _ = _send_and_wait(ctrl, line, timeout=30.0)
            if resp.startswith("error:"):
                _error(f"Error during burn-text: {resp}", "GCODE_ERROR", plain)
        total_ms = (time.monotonic() - start) * 1000
        _output({
            "ok": True,
            "command": f"burn-text '{text}'",
            "lines_sent": len(gcode_lines),
            "elapsed_ms": round(total_ms),
        }, plain)
    finally:
        try:
            ctrl.serial.write(b"M5\n")
        except Exception:
            pass
        if ctrl.serial and ctrl.serial.is_open:
            ctrl.serial.close()


@cli.command("burn-rect")
@click.option("--x1", type=float, required=True)
@click.option("--y1", type=float, required=True)
@click.option("--x2", type=float, required=True)
@click.option("--y2", type=float, required=True)
@click.option("--operation", type=click.Choice(["cut", "engrave"]), default="cut")
@click.option("--power", type=int, default=1000)
@click.option("--speed", type=int, default=300)
@click.pass_context
def burn_rect(ctx: click.Context, x1: float, y1: float, x2: float, y2: float,
              operation: str, power: int, speed: int) -> None:
    """Burn a rectangle (cut or engrave outline)."""
    plain = ctx.obj["plain"]
    gcode_lines = [
        "G90",
        f"G0 X{x1:.3f} Y{y1:.3f} F{speed}",
        f"M3 S{power}",
        f"G1 X{x2:.3f} Y{y1:.3f} F{speed}",
        f"G1 X{x2:.3f} Y{y2:.3f} F{speed}",
        f"G1 X{x1:.3f} Y{y2:.3f} F{speed}",
        f"G1 X{x1:.3f} Y{y1:.3f} F{speed}",
        "M5",
    ]
    state = _load_state()
    ctrl = _get_controller(state, plain)
    try:
        start = time.monotonic()
        for line in gcode_lines:
            resp, _ = _send_and_wait(ctrl, line, timeout=30.0)
            if resp.startswith("error:"):
                _error(f"Error during burn-rect: {resp}", "GCODE_ERROR", plain)
        total_ms = (time.monotonic() - start) * 1000
        _output({
            "ok": True,
            "command": f"burn-rect {x1},{y1} → {x2},{y2} ({operation})",
            "lines_sent": len(gcode_lines),
            "elapsed_ms": round(total_ms),
        }, plain)
    finally:
        try:
            ctrl.serial.write(b"M5\n")
        except Exception:
            pass
        if ctrl.serial and ctrl.serial.is_open:
            ctrl.serial.close()


@cli.command("burn-circle")
@click.option("--cx", type=float, required=True, help="Center X.")
@click.option("--cy", type=float, required=True, help="Center Y.")
@click.option("--radius", type=float, required=True, help="Radius in mm.")
@click.option("--operation", type=click.Choice(["cut", "engrave"]), default="engrave")
@click.option("--power", type=int, default=600)
@click.option("--speed", type=int, default=1000)
@click.option("--segments", type=int, default=72, help="Number of line segments for circle.")
@click.pass_context
def burn_circle(ctx: click.Context, cx: float, cy: float, radius: float,
                operation: str, power: int, speed: int, segments: int) -> None:
    """Burn a circle (approximated with line segments)."""
    plain = ctx.obj["plain"]
    gcode_lines = ["G90"]

    # Move to start point (0 degrees)
    start_x = cx + radius
    start_y = cy
    gcode_lines.append(f"G0 X{start_x:.3f} Y{start_y:.3f} F{speed}")
    gcode_lines.append(f"M3 S{power}")

    for i in range(1, segments + 1):
        angle = 2 * math.pi * i / segments
        px = cx + radius * math.cos(angle)
        py = cy + radius * math.sin(angle)
        gcode_lines.append(f"G1 X{px:.3f} Y{py:.3f} F{speed}")

    gcode_lines.append("M5")

    state = _load_state()
    ctrl = _get_controller(state, plain)
    try:
        start = time.monotonic()
        for line in gcode_lines:
            resp, _ = _send_and_wait(ctrl, line, timeout=30.0)
            if resp.startswith("error:"):
                _error(f"Error during burn-circle: {resp}", "GCODE_ERROR", plain)
        total_ms = (time.monotonic() - start) * 1000
        _output({
            "ok": True,
            "command": f"burn-circle cx={cx} cy={cy} r={radius} ({operation})",
            "lines_sent": len(gcode_lines),
            "elapsed_ms": round(total_ms),
        }, plain)
    finally:
        try:
            ctrl.serial.write(b"M5\n")
        except Exception:
            pass
        if ctrl.serial and ctrl.serial.is_open:
            ctrl.serial.close()


@cli.command()
@click.option("--x1", type=float, required=True)
@click.option("--y1", type=float, required=True)
@click.option("--x2", type=float, required=True)
@click.option("--y2", type=float, required=True)
@click.option("--feed", type=int, default=1000)
@click.pass_context
def frame(ctx: click.Context, x1: float, y1: float, x2: float, y2: float, feed: int) -> None:
    """Trace bounding box with laser off (for alignment)."""
    plain = ctx.obj["plain"]
    gcode_lines = [
        "M5 S0",
        "G90",
        f"G0 X{x1:.3f} Y{y1:.3f} F{feed}",
        f"G1 X{x2:.3f} Y{y1:.3f} F{feed}",
        f"G1 X{x2:.3f} Y{y2:.3f} F{feed}",
        f"G1 X{x1:.3f} Y{y2:.3f} F{feed}",
        f"G1 X{x1:.3f} Y{y1:.3f} F{feed}",
    ]
    state = _load_state()
    ctrl = _get_controller(state, plain)
    try:
        start = time.monotonic()
        for line in gcode_lines:
            resp, _ = _send_and_wait(ctrl, line, timeout=30.0)
            if resp.startswith("error:"):
                _error(f"Error during frame: {resp}", "GCODE_ERROR", plain)
        total_ms = (time.monotonic() - start) * 1000
        _output({
            "ok": True,
            "command": f"frame {x1},{y1} → {x2},{y2}",
            "lines_sent": len(gcode_lines),
            "elapsed_ms": round(total_ms),
        }, plain)
    finally:
        if ctrl.serial and ctrl.serial.is_open:
            ctrl.serial.close()


# ── Machine info ────────────────────────────────────────────────────


@cli.command()
@click.pass_context
def settings(ctx: click.Context) -> None:
    """Read all GRBL $$ settings."""
    plain = ctx.obj["plain"]
    state = _load_state()
    ctrl = _get_controller(state, plain)
    try:
        ctrl._running = False  # prevent background threads
        s = ctrl.read_settings()
        _output({"ok": True, "settings": {str(k): v for k, v in s.items()}}, plain)
    finally:
        if ctrl.serial and ctrl.serial.is_open:
            ctrl.serial.close()


@cli.command("set")
@click.option("--key", required=True, type=int, help="GRBL setting number (e.g. 110).")
@click.option("--value", required=True, type=float, help="New value.")
@click.pass_context
def set_setting(ctx: click.Context, key: int, value: float) -> None:
    """Set a GRBL $$ setting."""
    plain = ctx.obj["plain"]
    state = _load_state()
    ctrl = _get_controller(state, plain)
    # Format value: use int if whole number
    val_str = str(int(value)) if value == int(value) else str(value)
    cmd = f"${key}={val_str}"
    try:
        resp, ms = _send_and_wait(ctrl, cmd)
        _output({
            "ok": resp == "ok",
            "command": cmd,
            "response": resp,
            "elapsed_ms": round(ms),
        }, plain)
    finally:
        if ctrl.serial and ctrl.serial.is_open:
            ctrl.serial.close()


@cli.command()
@click.pass_context
def detect(ctx: click.Context) -> None:
    """Auto-detect machine configuration from GRBL settings."""
    plain = ctx.obj["plain"]
    state = _load_state()
    ctrl = _get_controller(state, plain)
    try:
        ctrl._running = False
        cfg = ctrl.detect_machine()
        # Remove raw settings for cleaner output
        raw = cfg.pop("raw", {})
        _output({"ok": True, **cfg, "raw_settings_count": len(raw)}, plain)
    finally:
        if ctrl.serial and ctrl.serial.is_open:
            ctrl.serial.close()


# ── Profile commands ────────────────────────────────────────────────


@cli.group()
def profile() -> None:
    """Manage machine profiles."""
    pass


@profile.command("list")
@click.pass_context
def profile_list(ctx: click.Context) -> None:
    """List saved machine profiles."""
    plain = ctx.obj["plain"]
    from lasermac.profiles import list_profiles

    profiles = list_profiles()
    result = {
        "ok": True,
        "profiles": [p.to_dict() for p in profiles],
    }
    _output(result, plain)


@profile.command("save")
@click.option("--name", required=True, help="Profile name.")
@click.pass_context
def profile_save(ctx: click.Context, name: str) -> None:
    """Save current machine config as a profile."""
    plain = ctx.obj["plain"]
    state = _load_state()

    # Try to detect from connected machine, fallback to defaults
    try:
        ctrl = _get_controller(state, plain)
        ctrl._running = False
        cfg = ctrl.detect_machine()
        if ctrl.serial and ctrl.serial.is_open:
            ctrl.serial.close()
    except SystemExit:
        # Not connected — save with defaults
        cfg = {}

    from lasermac.profiles import MachineProfile, save_profile

    p = MachineProfile.from_grbl_detect(cfg) if cfg else MachineProfile()
    p.name = name
    path = save_profile(p)
    _output({"ok": True, "name": name, "path": str(path)}, plain)


@profile.command("load")
@click.option("--name", required=True, help="Profile name to load.")
@click.pass_context
def profile_load(ctx: click.Context, name: str) -> None:
    """Load a saved machine profile."""
    plain = ctx.obj["plain"]
    from lasermac.profiles import list_profiles

    profiles = list_profiles()
    match = None
    for p in profiles:
        if p.name.lower() == name.lower():
            match = p
            break

    if not match:
        _error(f"Profile '{name}' not found", "PROFILE_NOT_FOUND", plain)

    _output({"ok": True, "profile": match.to_dict()}, plain)


# ── Text G-code generation (simple single-stroke) ──────────────────


def _generate_text_gcode(text: str, x: float, y: float, size: float,
                         power: int, speed: int) -> list[str]:
    """Generate G-code for simple text engraving.

    Uses a basic single-stroke font approximation. Each character is
    rendered as simple line segments within a bounding box of (size × size).
    """
    # Simple block letter definitions: list of (x, y) line segments
    # Coordinates normalized to 0-1 range
    FONT: dict[str, list[list[tuple[float, float]]]] = {
        "A": [[(0, 0), (0.5, 1), (1, 0)], [(0.2, 0.4), (0.8, 0.4)]],
        "B": [[(0, 0), (0, 1), (0.7, 1), (0.8, 0.9), (0.8, 0.6), (0.7, 0.5), (0, 0.5)],
              [(0.7, 0.5), (0.8, 0.4), (0.8, 0.1), (0.7, 0), (0, 0)]],
        "C": [[(1, 0.1), (0.8, 0), (0.2, 0), (0, 0.1), (0, 0.9), (0.2, 1), (0.8, 1), (1, 0.9)]],
        "D": [[(0, 0), (0, 1), (0.7, 1), (1, 0.8), (1, 0.2), (0.7, 0), (0, 0)]],
        "E": [[(1, 0), (0, 0), (0, 1), (1, 1)], [(0, 0.5), (0.7, 0.5)]],
        "F": [[(0, 0), (0, 1), (1, 1)], [(0, 0.5), (0.7, 0.5)]],
        "G": [[(1, 0.9), (0.8, 1), (0.2, 1), (0, 0.8), (0, 0.2), (0.2, 0), (0.8, 0), (1, 0.2), (1, 0.5), (0.5, 0.5)]],
        "H": [[(0, 0), (0, 1)], [(1, 0), (1, 1)], [(0, 0.5), (1, 0.5)]],
        "I": [[(0.2, 0), (0.8, 0)], [(0.5, 0), (0.5, 1)], [(0.2, 1), (0.8, 1)]],
        "J": [[(0, 0.2), (0.2, 0), (0.6, 0), (0.8, 0.2), (0.8, 1)]],
        "K": [[(0, 0), (0, 1)], [(1, 1), (0, 0.5), (1, 0)]],
        "L": [[(0, 1), (0, 0), (1, 0)]],
        "M": [[(0, 0), (0, 1), (0.5, 0.5), (1, 1), (1, 0)]],
        "N": [[(0, 0), (0, 1), (1, 0), (1, 1)]],
        "O": [[(0.2, 0), (0, 0.2), (0, 0.8), (0.2, 1), (0.8, 1), (1, 0.8), (1, 0.2), (0.8, 0), (0.2, 0)]],
        "P": [[(0, 0), (0, 1), (0.8, 1), (1, 0.8), (1, 0.6), (0.8, 0.5), (0, 0.5)]],
        "Q": [[(0.2, 0), (0, 0.2), (0, 0.8), (0.2, 1), (0.8, 1), (1, 0.8), (1, 0.2), (0.8, 0), (0.2, 0)], [(0.7, 0.3), (1, 0)]],
        "R": [[(0, 0), (0, 1), (0.8, 1), (1, 0.8), (1, 0.6), (0.8, 0.5), (0, 0.5)], [(0.5, 0.5), (1, 0)]],
        "S": [[(1, 0.9), (0.8, 1), (0.2, 1), (0, 0.8), (0, 0.6), (0.2, 0.5), (0.8, 0.5), (1, 0.4), (1, 0.2), (0.8, 0), (0.2, 0), (0, 0.1)]],
        "T": [[(0, 1), (1, 1)], [(0.5, 0), (0.5, 1)]],
        "U": [[(0, 1), (0, 0.2), (0.2, 0), (0.8, 0), (1, 0.2), (1, 1)]],
        "V": [[(0, 1), (0.5, 0), (1, 1)]],
        "W": [[(0, 1), (0.25, 0), (0.5, 0.5), (0.75, 0), (1, 1)]],
        "X": [[(0, 0), (1, 1)], [(0, 1), (1, 0)]],
        "Y": [[(0, 1), (0.5, 0.5), (1, 1)], [(0.5, 0.5), (0.5, 0)]],
        "Z": [[(0, 1), (1, 1), (0, 0), (1, 0)]],
        " ": [],
        "0": [[(0.2, 0), (0, 0.2), (0, 0.8), (0.2, 1), (0.8, 1), (1, 0.8), (1, 0.2), (0.8, 0), (0.2, 0)]],
        "1": [[(0.3, 0.8), (0.5, 1), (0.5, 0)], [(0.2, 0), (0.8, 0)]],
        "2": [[(0, 0.8), (0.2, 1), (0.8, 1), (1, 0.8), (1, 0.6), (0, 0), (1, 0)]],
        "3": [[(0, 0.9), (0.2, 1), (0.8, 1), (1, 0.8), (1, 0.6), (0.8, 0.5), (0.5, 0.5)],
              [(0.8, 0.5), (1, 0.4), (1, 0.2), (0.8, 0), (0.2, 0), (0, 0.1)]],
        "4": [[(0, 1), (0, 0.4), (1, 0.4)], [(0.8, 1), (0.8, 0)]],
        "5": [[(1, 1), (0, 1), (0, 0.5), (0.8, 0.5), (1, 0.4), (1, 0.1), (0.8, 0), (0, 0)]],
        "6": [[(1, 0.9), (0.8, 1), (0.2, 1), (0, 0.8), (0, 0.2), (0.2, 0), (0.8, 0), (1, 0.2), (1, 0.5), (0.8, 0.5), (0, 0.5)]],
        "7": [[(0, 1), (1, 1), (0.3, 0)]],
        "8": [[(0.2, 0.5), (0, 0.3), (0, 0.1), (0.2, 0), (0.8, 0), (1, 0.1), (1, 0.3), (0.8, 0.5), (0.2, 0.5)],
              [(0.2, 0.5), (0, 0.7), (0, 0.9), (0.2, 1), (0.8, 1), (1, 0.9), (1, 0.7), (0.8, 0.5)]],
        "9": [[(0, 0.1), (0.2, 0), (0.8, 0), (1, 0.2), (1, 0.8), (0.8, 1), (0.2, 1), (0, 0.8), (0, 0.5), (0.2, 0.5), (1, 0.5)]],
        ".": [[(0.4, 0), (0.6, 0), (0.6, 0.1), (0.4, 0.1), (0.4, 0)]],
        "-": [[(0.2, 0.5), (0.8, 0.5)]],
        "!": [[(0.5, 0.3), (0.5, 1)], [(0.5, 0), (0.5, 0.1)]],
    }

    gcode = [
        "G90",
        "G21",  # mm mode
        "M3 S0",
    ]

    char_width = size * 0.7  # character spacing
    cursor_x = x

    for ch in text.upper():
        strokes = FONT.get(ch, [])
        for stroke in strokes:
            if not stroke:
                continue
            # Move to start of stroke (laser off)
            sx = cursor_x + stroke[0][0] * size
            sy = y + stroke[0][1] * size
            gcode.append(f"G0 X{sx:.3f} Y{sy:.3f}")
            gcode.append(f"M3 S{power}")
            for px, py in stroke[1:]:
                gx = cursor_x + px * size
                gy = y + py * size
                gcode.append(f"G1 X{gx:.3f} Y{gy:.3f} F{speed}")
            gcode.append("M3 S0")
        cursor_x += char_width

    gcode.append("M5")
    return gcode
