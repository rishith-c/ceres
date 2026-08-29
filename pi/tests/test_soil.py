"""Calibration math and the broken-probe-is-not-a-drought self-check."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from soil import SoilCalibration, self_check  # noqa: E402

CAL = SoilCalibration(raw_dry=350, raw_wet=1750)  # span 1400


def test_normalization_endpoints_and_midpoint():
    assert CAL.moisture(350) == 0.0
    assert CAL.moisture(1750) == 1.0
    assert CAL.moisture(1050) == pytest.approx(0.5)


def test_normalization_clamps_inside_plausible_range():
    assert CAL.moisture(300) == 0.0    # slightly drier than the dry point
    assert CAL.moisture(1900) == 1.0   # slightly wetter than the wet point


def test_implausible_raw_reads_as_fault_not_drought():
    assert CAL.moisture(0) is None       # disconnected
    assert CAL.moisture(99) is None
    assert CAL.moisture(2201) is None    # shorted / garbage


def test_too_narrow_calibration_is_rejected():
    with pytest.raises(ValueError):
        SoilCalibration(raw_dry=500, raw_wet=700)


def test_self_check_passes_near_dry_point():
    ok, msg = self_check(400, CAL)
    assert ok, msg


def test_self_check_fails_when_air_reads_wet():
    ok, msg = self_check(1200, CAL)  # probe in "air" reading wet = fault
    assert not ok
    assert "recalibrate" in msg


def test_self_check_fails_on_implausible_raw():
    ok, msg = self_check(20, CAL)
    assert not ok
    assert "wiring" in msg
