"""Driver tests against a scripted fake serial port — no hardware needed."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rover import Rover, RoverCommandError, RoverError, RoverTimeout  # noqa: E402


class FakeSerial:
    """Answers written commands like the firmware would."""

    def __init__(self, responses=None, boot_lines=("READY rover_motion 1.1",)):
        self.rx = [l.encode() + b"\n" for l in boot_lines]
        self.written = []
        self.responses = responses or {}
        self.closed = False

    def write(self, data):
        line = data.decode().strip()
        self.written.append(line)
        cmd = line.split()[0]
        for reply in self.responses.get(cmd, [f"OK {cmd}"]):
            r = reply(self) if callable(reply) else reply
            self.rx.append(r.encode() + b"\n")

    def readline(self):
        return self.rx.pop(0) if self.rx else b""  # empty = timeout

    def close(self):
        self.closed = True


def make_rover(**kw):
    fake = FakeSerial(**kw)
    r = Rover(transport=fake, cmd_timeout=0.5, ready_timeout=0.5)
    r.connect()
    return r, fake


def test_connect_syncs_on_ready_banner():
    r, fake = make_rover(boot_lines=("", "\x00garbage", "READY rover_motion 1.1"))
    r.ping()
    assert fake.written == ["PING"]


def test_connect_times_out_without_ready():
    r = Rover(transport=FakeSerial(boot_lines=()), ready_timeout=0.2)
    with pytest.raises(RoverTimeout):
        r.connect()


def test_ping_and_drive_commands_send_protocol_lines():
    r, fake = make_rover(responses={"PING": ["OK PONG"]})
    r.ping()
    r.forward(800, 150)
    r.reverse(500, 120)
    r.spin(300, 140, "L")
    r.stop()
    assert fake.written == ["PING", "FWD 800 150", "REV 500 120", "SPIN 300 140 L", "STOP"]


def test_err_reply_raises_with_reason():
    r, _ = make_rover(responses={"PROBE": ["ERR moving"]})
    with pytest.raises(RoverCommandError) as ei:
        r.probe(100)
    assert ei.value.reason == "moving"


def test_status_parses_all_fields():
    r, _ = make_rover(responses={"STATUS": ["OK FWD 150 0 90 90 1 12345"]})
    st = r.status()
    assert (st.drive, st.pwm, st.probe, st.pan, st.tilt, st.settled, st.uptime_ms) == \
        ("FWD", 150, 0, 90, 90, True, 12345)


def test_malformed_status_raises():
    r, _ = make_rover(responses={"STATUS": ["OK FWD 150 nonsense"]})
    with pytest.raises(RoverError):
        r.status()


def test_command_timeout_raises():
    r, _ = make_rover(responses={"PROBE": []})  # firmware never answers
    with pytest.raises(RoverTimeout):
        r.probe(50)


def test_unexpected_ready_means_mcu_reset():
    r, _ = make_rover(responses={"PING": ["READY rover_motion 1.1"]})
    with pytest.raises(RoverError, match="reset"):
        r.ping()


def test_wait_for_stop_polls_until_idle():
    replies = iter(["OK FWD 150 0 90 90 1 100", "OK FWD 150 0 90 90 1 200",
                    "OK IDLE 0 0 90 90 1 300"])
    r, fake = make_rover(responses={"STATUS": [lambda f: next(replies)]})
    st = r.wait_for_stop(timeout=2.0, poll=0.01)
    assert st.drive == "IDLE"
    assert fake.written.count("STATUS") == 3  # the polling is the keepalive


def test_client_side_validation():
    r, fake = make_rover()
    for bad in (lambda: r.forward(0, 100), lambda: r.forward(800, 300),
                lambda: r.probe(101), lambda: r.pan(181),
                lambda: r.spin(300, 100, "X")):
        with pytest.raises(ValueError):
            bad()
    assert fake.written == []  # nothing invalid reached the wire


def test_context_manager_stops_and_closes():
    fake = FakeSerial()
    with Rover(transport=fake, cmd_timeout=0.5, ready_timeout=0.5) as r:
        r.ping()
    assert fake.written[-1] == "STOP"
    assert fake.closed
