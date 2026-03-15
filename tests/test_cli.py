"""Tests for LaserMac CLI — all commands with mocked serial."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from lasermac.cli_main import _generate_text_gcode, cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def tmp_state(tmp_path, monkeypatch):
    """Use a temp state file so tests don't touch ~/.lasermac."""
    state_file = tmp_path / "cli_state.json"
    monkeypatch.setattr("lasermac.cli_main.STATE_FILE", state_file)
    monkeypatch.setattr("lasermac.cli_main.STATE_DIR", tmp_path)
    return state_file


def _write_state(state_file: Path, data: dict):
    state_file.write_text(json.dumps(data))


class MockSerial:
    """Mock serial.Serial for testing without hardware."""

    def __init__(self, *args, **kwargs):
        self.is_open = True
        self.in_waiting = 0
        self._response_queue: list[bytes] = []
        self._written: list[bytes] = []

    def write(self, data: bytes):
        self._written.append(data)
        cmd = data.decode().strip()
        # Auto-respond to known commands
        if cmd == "?":
            self._response_queue.append(b"<Idle|MPos:10.000,20.000,0.000|FS:0,0>\n")
            self.in_waiting = len(self._response_queue[0]) if self._response_queue else 0
        elif cmd == "$$":
            lines = b"$0=10\n$1=25\n$30=1000\n$110=3000\n$111=3000\n$130=300\n$131=300\n$32=1\nok\n"
            self._response_queue.append(lines)
            self.in_waiting = len(lines)
        elif cmd:
            self._response_queue.append(b"ok\n")
            self.in_waiting = 3

    def readline(self) -> bytes:
        if self._response_queue:
            data = self._response_queue[0]
            # Return line by line
            if b"\n" in data:
                line, rest = data.split(b"\n", 1)
                if rest:
                    self._response_queue[0] = rest
                    self.in_waiting = len(rest)
                else:
                    self._response_queue.pop(0)
                    self.in_waiting = sum(len(r) for r in self._response_queue)
                return line + b"\n"
            self._response_queue.pop(0)
            self.in_waiting = 0
            return data
        return b""

    def read(self, size=1) -> bytes:
        if self._response_queue:
            data = self._response_queue.pop(0)
            self.in_waiting = 0
            return data
        return b""

    def flushInput(self):
        self._response_queue.clear()
        self.in_waiting = 0

    def close(self):
        self.is_open = False


# ── Basic CLI tests ─────────────────────────────────────────────────


class TestCLIBasics:
    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "LaserMac CLI" in result.output

    def test_connect_help(self, runner):
        result = runner.invoke(cli, ["connect", "--help"])
        assert result.exit_code == 0
        assert "--port" in result.output

    def test_ports_command(self, runner, tmp_state):
        with patch("lasermac.grbl.GrblController.list_ports_detail", return_value=[
            {"device": "/dev/cu.test", "name": "test", "description": "Test Port",
             "chip": "CH340", "vid": 0x1A86, "pid": 0x7523}
        ]):
            result = runner.invoke(cli, ["ports"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert len(data["ports"]) == 1
            assert data["ports"][0]["chip"] == "CH340"

    def test_ports_empty(self, runner, tmp_state):
        with patch("lasermac.grbl.GrblController.list_ports_detail", return_value=[]):
            result = runner.invoke(cli, ["ports"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert data["ports"] == []


# ── Connection tests ────────────────────────────────────────────────


class TestConnection:
    def test_connect_success(self, runner, tmp_state):
        with patch("lasermac.grbl.GrblController.connect", return_value=True), \
             patch("lasermac.grbl.GrblController.disconnect"):
            result = runner.invoke(cli, ["connect", "--port", "/dev/cu.test"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert data["port"] == "/dev/cu.test"

    def test_connect_saves_state(self, runner, tmp_state):
        with patch("lasermac.grbl.GrblController.connect", return_value=True), \
             patch("lasermac.grbl.GrblController.disconnect"):
            runner.invoke(cli, ["connect", "--port", "/dev/cu.test", "--baud", "9600"])
            state = json.loads(tmp_state.read_text())
            assert state["port"] == "/dev/cu.test"
            assert state["baud"] == 9600

    def test_connect_failure(self, runner, tmp_state):
        with patch("lasermac.grbl.GrblController.connect", return_value=False):
            result = runner.invoke(cli, ["connect", "--port", "/dev/cu.fake"])
            assert result.exit_code == 1
            data = json.loads(result.output)
            assert data["ok"] is False
            assert "CONNECTION_FAILED" in data["code"]

    def test_connect_auto_detect(self, runner, tmp_state):
        with patch("lasermac.grbl.GrblController.list_ports", return_value=["/dev/cu.auto"]), \
             patch("lasermac.grbl.GrblController.connect", return_value=True), \
             patch("lasermac.grbl.GrblController.disconnect"):
            result = runner.invoke(cli, ["connect"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["port"] == "/dev/cu.auto"

    def test_connect_no_ports(self, runner, tmp_state):
        with patch("lasermac.grbl.GrblController.list_ports", return_value=[]):
            result = runner.invoke(cli, ["connect"])
            assert result.exit_code == 1
            data = json.loads(result.output)
            assert data["code"] == "NO_PORTS"

    def test_disconnect(self, runner, tmp_state):
        _write_state(tmp_state, {"port": "/dev/cu.test", "connected": True})
        result = runner.invoke(cli, ["disconnect"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        state = json.loads(tmp_state.read_text())
        assert state["connected"] is False


# ── Status tests ────────────────────────────────────────────────────


class TestStatus:
    def test_status_not_connected(self, runner, tmp_state):
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["code"] == "NOT_CONNECTED"

    @patch("lasermac.cli_main.time.sleep")
    def test_status_connected(self, mock_sleep, runner, tmp_state):
        _write_state(tmp_state, {"port": "/dev/cu.test", "baud": 115200})
        mock_serial = MockSerial()
        with patch("serial.Serial", return_value=mock_serial):
            result = runner.invoke(cli, ["status"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert data["connected"] is True
            assert data["state"] == "Idle"
            assert data["x"] == 10.0
            assert data["y"] == 20.0


# ── Machine control tests ──────────────────────────────────────────


class TestMachineControl:
    @patch("lasermac.cli_main.time.sleep")
    def test_home(self, mock_sleep, runner, tmp_state):
        _write_state(tmp_state, {"port": "/dev/cu.test", "baud": 115200})
        mock_serial = MockSerial()
        with patch("serial.Serial", return_value=mock_serial):
            result = runner.invoke(cli, ["home"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert data["command"] == "$H"

    @patch("lasermac.cli_main.time.sleep")
    def test_unlock(self, mock_sleep, runner, tmp_state):
        _write_state(tmp_state, {"port": "/dev/cu.test", "baud": 115200})
        mock_serial = MockSerial()
        with patch("serial.Serial", return_value=mock_serial):
            result = runner.invoke(cli, ["unlock"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert data["command"] == "$X"

    @patch("lasermac.cli_main.time.sleep")
    def test_reset(self, mock_sleep, runner, tmp_state):
        _write_state(tmp_state, {"port": "/dev/cu.test", "baud": 115200})
        mock_serial = MockSerial()
        with patch("serial.Serial", return_value=mock_serial):
            result = runner.invoke(cli, ["reset"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True

    @patch("lasermac.cli_main.time.sleep")
    def test_origin(self, mock_sleep, runner, tmp_state):
        _write_state(tmp_state, {"port": "/dev/cu.test", "baud": 115200})
        mock_serial = MockSerial()
        with patch("serial.Serial", return_value=mock_serial):
            result = runner.invoke(cli, ["origin"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert "G92" in data["command"]

    @patch("lasermac.cli_main.time.sleep")
    def test_goto(self, mock_sleep, runner, tmp_state):
        _write_state(tmp_state, {"port": "/dev/cu.test", "baud": 115200})
        mock_serial = MockSerial()
        with patch("serial.Serial", return_value=mock_serial):
            result = runner.invoke(cli, ["goto", "--x", "10", "--y", "20", "--feed", "500"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert "X10.000" in data["command"]
            assert "Y20.000" in data["command"]

    @patch("lasermac.cli_main.time.sleep")
    def test_jog(self, mock_sleep, runner, tmp_state):
        _write_state(tmp_state, {"port": "/dev/cu.test", "baud": 115200})
        mock_serial = MockSerial()
        with patch("serial.Serial", return_value=mock_serial):
            result = runner.invoke(cli, ["jog", "--axis", "X", "--distance", "10"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert "$J=" in data["command"]


# ── Laser tests ─────────────────────────────────────────────────────


class TestLaser:
    @patch("lasermac.cli_main.time.sleep")
    def test_laser_on(self, mock_sleep, runner, tmp_state):
        _write_state(tmp_state, {"port": "/dev/cu.test", "baud": 115200})
        mock_serial = MockSerial()
        with patch("serial.Serial", return_value=mock_serial):
            result = runner.invoke(cli, ["laser-on", "--power", "500"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert data["command"] == "M3 S500"

    @patch("lasermac.cli_main.time.sleep")
    def test_laser_off(self, mock_sleep, runner, tmp_state):
        _write_state(tmp_state, {"port": "/dev/cu.test", "baud": 115200})
        mock_serial = MockSerial()
        with patch("serial.Serial", return_value=mock_serial):
            result = runner.invoke(cli, ["laser-off"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert data["command"] == "M5"

    @patch("lasermac.cli_main.time.sleep")
    def test_laser_test(self, mock_sleep, runner, tmp_state):
        _write_state(tmp_state, {"port": "/dev/cu.test", "baud": 115200})
        mock_serial = MockSerial()
        with patch("serial.Serial", return_value=mock_serial):
            result = runner.invoke(cli, ["laser-test", "--power", "100", "--duration", "0.01"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True


# ── Send / Job tests ───────────────────────────────────────────────


class TestSend:
    @patch("lasermac.cli_main.time.sleep")
    def test_send_gcode_string(self, mock_sleep, runner, tmp_state):
        _write_state(tmp_state, {"port": "/dev/cu.test", "baud": 115200})
        mock_serial = MockSerial()
        with patch("serial.Serial", return_value=mock_serial):
            result = runner.invoke(cli, ["send", "--gcode", "G0 X10 Y10"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert data["lines_sent"] == 1

    @patch("lasermac.cli_main.time.sleep")
    def test_send_gcode_file(self, mock_sleep, runner, tmp_state, tmp_path):
        _write_state(tmp_state, {"port": "/dev/cu.test", "baud": 115200})
        gcode_file = tmp_path / "test.gcode"
        gcode_file.write_text("G0 X0 Y0\nG1 X10 Y10 F500\nM5\n")
        mock_serial = MockSerial()
        with patch("serial.Serial", return_value=mock_serial):
            result = runner.invoke(cli, ["send", "--file", str(gcode_file)])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert data["lines_sent"] == 3

    def test_send_no_args(self, runner, tmp_state):
        _write_state(tmp_state, {"port": "/dev/cu.test", "baud": 115200})
        result = runner.invoke(cli, ["send"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["code"] == "MISSING_ARG"

    def test_send_file_not_found(self, runner, tmp_state):
        _write_state(tmp_state, {"port": "/dev/cu.test", "baud": 115200})
        with patch("serial.Serial", return_value=MockSerial()), \
             patch("lasermac.cli_main.time.sleep"):
            result = runner.invoke(cli, ["send", "--file", "/nonexistent.gcode"])
            assert result.exit_code == 1


# ── Burn shape tests ───────────────────────────────────────────────


class TestBurnShapes:
    @patch("lasermac.cli_main.time.sleep")
    def test_burn_rect(self, mock_sleep, runner, tmp_state):
        _write_state(tmp_state, {"port": "/dev/cu.test", "baud": 115200})
        mock_serial = MockSerial()
        with patch("serial.Serial", return_value=mock_serial):
            result = runner.invoke(cli, [
                "burn-rect", "--x1", "0", "--y1", "0", "--x2", "50", "--y2", "50",
                "--operation", "cut", "--power", "1000", "--speed", "300"
            ])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert data["lines_sent"] == 8

    @patch("lasermac.cli_main.time.sleep")
    def test_burn_circle(self, mock_sleep, runner, tmp_state):
        _write_state(tmp_state, {"port": "/dev/cu.test", "baud": 115200})
        mock_serial = MockSerial()
        with patch("serial.Serial", return_value=mock_serial):
            result = runner.invoke(cli, [
                "burn-circle", "--cx", "25", "--cy", "25", "--radius", "20",
                "--segments", "36"
            ])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            # 1(G90) + 1(G0 move) + 1(M3) + 36(segments) + 1(M5) = 40
            assert data["lines_sent"] == 40

    @patch("lasermac.cli_main.time.sleep")
    def test_frame(self, mock_sleep, runner, tmp_state):
        _write_state(tmp_state, {"port": "/dev/cu.test", "baud": 115200})
        mock_serial = MockSerial()
        with patch("serial.Serial", return_value=mock_serial):
            result = runner.invoke(cli, [
                "frame", "--x1", "0", "--y1", "0", "--x2", "100", "--y2", "100"
            ])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert data["lines_sent"] == 7


# ── Text generation tests ──────────────────────────────────────────


class TestTextGeneration:
    def test_generate_simple_text(self):
        gcode = _generate_text_gcode("HI", 0, 0, 10, 800, 600)
        assert len(gcode) > 5
        assert gcode[0] == "G90"
        assert gcode[-1] == "M5"
        # Should contain movement commands
        has_g1 = any("G1" in line for line in gcode)
        assert has_g1

    def test_generate_empty_text(self):
        gcode = _generate_text_gcode("", 0, 0, 10, 800, 600)
        # Just header + M5
        assert gcode[-1] == "M5"

    def test_generate_with_spaces(self):
        gcode = _generate_text_gcode("A B", 0, 0, 10, 800, 600)
        assert gcode[-1] == "M5"
        assert len(gcode) > 3


# ── Profile tests ──────────────────────────────────────────────────


class TestProfiles:
    def test_profile_list(self, runner, tmp_state):
        result = runner.invoke(cli, ["profile", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert len(data["profiles"]) >= 3  # 3 builtins

    def test_profile_save(self, runner, tmp_state, tmp_path):
        with patch("lasermac.cli_main._get_controller") as mock_ctrl:
            mock_ctrl.side_effect = SystemExit(1)
            with patch("lasermac.profiles.PROFILES_DIR", tmp_path / "profiles"):
                result = runner.invoke(cli, ["profile", "save", "--name", "Test Profile"])
                assert result.exit_code == 0
                data = json.loads(result.output)
                assert data["ok"] is True
                assert data["name"] == "Test Profile"

    def test_profile_load_builtin(self, runner, tmp_state):
        result = runner.invoke(cli, ["profile", "load", "--name", "Generic GRBL"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["profile"]["name"] == "Generic GRBL"

    def test_profile_load_not_found(self, runner, tmp_state):
        result = runner.invoke(cli, ["profile", "load", "--name", "Nonexistent"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["code"] == "PROFILE_NOT_FOUND"


# ── Output format tests ────────────────────────────────────────────


class TestOutputFormat:
    def test_json_output_format(self, runner, tmp_state):
        with patch("lasermac.grbl.GrblController.list_ports_detail", return_value=[]):
            result = runner.invoke(cli, ["ports"])
            data = json.loads(result.output)
            assert "ok" in data

    def test_plain_output(self, runner, tmp_state):
        result = runner.invoke(cli, ["--plain", "disconnect"])
        assert result.exit_code == 0
        # Should not be JSON
        try:
            json.loads(result.output)
            is_json = True
        except json.JSONDecodeError:
            is_json = False
        assert not is_json


# ── Settings tests ──────────────────────────────────────────────────


class TestSettings:
    @patch("lasermac.cli_main.time.sleep")
    def test_settings(self, mock_sleep, runner, tmp_state):
        _write_state(tmp_state, {"port": "/dev/cu.test", "baud": 115200})
        mock_serial = MockSerial()
        with patch("serial.Serial", return_value=mock_serial):
            result = runner.invoke(cli, ["settings"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert "settings" in data

    @patch("lasermac.cli_main.time.sleep")
    def test_set_setting(self, mock_sleep, runner, tmp_state):
        _write_state(tmp_state, {"port": "/dev/cu.test", "baud": 115200})
        mock_serial = MockSerial()
        with patch("serial.Serial", return_value=mock_serial):
            result = runner.invoke(cli, ["set", "--key", "110", "--value", "3000"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert data["command"] == "$110=3000"

    @patch("lasermac.cli_main.time.sleep")
    def test_detect(self, mock_sleep, runner, tmp_state):
        _write_state(tmp_state, {"port": "/dev/cu.test", "baud": 115200})
        mock_serial = MockSerial()
        with patch("serial.Serial", return_value=mock_serial):
            result = runner.invoke(cli, ["detect"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert "work_x" in data
