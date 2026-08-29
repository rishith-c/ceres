"""ProbeTurret tests against a fake ServoKit — no hardware, no real sleeps."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import actuators  # noqa: E402
from actuators import PAN_CH, PROBE_CH, TILT_CH, ProbeTurret  # noqa: E402


class FakeServo:
    def __init__(self):
        self.history = []
        self.pulse_range = None
        self.actuation_range = None

    @property
    def angle(self):
        return self.history[-1] if self.history else None

    @angle.setter
    def angle(self, v):
        self.history.append(v)

    def set_pulse_width_range(self, lo, hi):
        self.pulse_range = (lo, hi)


class FakeKit:
    def __init__(self):
        self.servo = [FakeServo() for _ in range(16)]


@pytest.fixture
def turret(monkeypatch):
    monkeypatch.setattr(actuators.time, "sleep", lambda s: None)
    return ProbeTurret(kit=FakeKit())


def test_boot_commands_home(turret):
    assert turret._kit.servo[PROBE_CH].angle == 0.0
    assert turret._kit.servo[PAN_CH].angle == 90.0
    assert turret._kit.servo[TILT_CH].angle == 90.0


def test_probe_pulse_range_supports_150_deg_sweep(turret):
    assert turret._kit.servo[PROBE_CH].pulse_range == (600, 2400)
    assert turret._kit.servo[PROBE_CH].actuation_range == 150


def test_probe_maps_pct_to_sweep_and_slews(turret):
    turret.probe(100)
    hist = turret._kit.servo[PROBE_CH].history
    assert hist[-1] == 150.0
    assert len(hist) > 50                       # slewed, not snapped
    assert all(b >= a for a, b in zip(hist[1:], hist[2:]))  # monotonic descent-free


def test_probe_deployed_flag(turret):
    assert not turret.probe_deployed
    turret.probe(50)
    assert turret.probe_deployed
    turret.probe(0)
    assert not turret.probe_deployed


def test_sample_reads_at_depth_then_retracts(turret):
    depths = []
    result = turret.sample(lambda: depths.append(turret._pos[PROBE_CH]) or "wet",
                           dwell_s=0, depth_pct=80)
    assert result == "wet"
    assert depths == [120.0]                    # read happened at depth
    assert not turret.probe_deployed            # and it came back up


def test_sample_retracts_even_when_read_raises(turret):
    with pytest.raises(RuntimeError):
        turret.sample(lambda: (_ for _ in ()).throw(RuntimeError("i2c")), dwell_s=0)
    assert not turret.probe_deployed


def test_validation(turret):
    for bad in (lambda: turret.probe(101), lambda: turret.pan(-1),
                lambda: turret.tilt(181)):
        with pytest.raises(ValueError):
            bad()
