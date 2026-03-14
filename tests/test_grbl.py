"""Tests for GRBL controller (no hardware needed)."""

from lasermac.grbl import GrblController, GrblStatus


class TestGrblStatusParsing:
    """Test GRBL status response parsing."""

    def test_parse_idle_mpos(self):
        s = GrblStatus.parse("<Idle|MPos:10.000,20.000,0.000|FS:0,0>")
        assert s.state == "Idle"
        assert s.x == 10.0
        assert s.y == 20.0
        assert s.z == 0.0

    def test_parse_run_wpos(self):
        s = GrblStatus.parse("<Run|WPos:5.500,3.200,0.000|FS:1000,500>")
        assert s.state == "Run"
        assert s.x == 5.5
        assert s.y == 3.2
        assert s.feed == 1000.0
        assert s.speed == 500.0

    def test_parse_alarm(self):
        s = GrblStatus.parse("<Alarm|MPos:0.000,0.000,0.000>")
        assert s.state == "Alarm"

    def test_parse_with_buffer(self):
        s = GrblStatus.parse("<Idle|MPos:0.000,0.000,0.000|Bf:15,128>")
        assert s.buffer_available == 15

    def test_parse_feed_only(self):
        s = GrblStatus.parse("<Idle|MPos:1.0,2.0,3.0|F:500>")
        assert s.feed == 500.0

    def test_parse_dict_convenience(self):
        d = GrblController.parse_status_response("<Idle|MPos:1.0,2.0,3.0>")
        assert d == {"state": "Idle", "x": 1.0, "y": 2.0, "z": 3.0}


class TestJogGeneration:
    """Test jog G-code generation."""

    def test_jog_x_positive(self):
        cmd = GrblController.generate_jog_gcode("X", 10.0, 1000)
        assert cmd == "$J=G91 X10.000 F1000"

    def test_jog_y_negative(self):
        cmd = GrblController.generate_jog_gcode("Y", -5.5, 500)
        assert cmd == "$J=G91 Y-5.500 F500"

    def test_jog_z(self):
        cmd = GrblController.generate_jog_gcode("Z", 0.1, 200)
        assert cmd == "$J=G91 Z0.100 F200"


class TestCommandQueue:
    """Test command queue behavior (without serial)."""

    def test_controller_init(self):
        ctrl = GrblController()
        assert not ctrl.connected
        assert ctrl.serial is None

    def test_send_command_queues(self):
        ctrl = GrblController()
        ctrl.send_command("G0 X10")
        assert not ctrl._command_queue.empty()

    def test_send_empty_ignored(self):
        ctrl = GrblController()
        ctrl.send_command("")
        assert ctrl._command_queue.empty()

    def test_list_ports_returns_list(self):
        ports = GrblController.list_ports()
        assert isinstance(ports, list)
