"""Every cell of the fusion table, its boundaries, and the judge question."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from triage import (Flag, LeafReading, TABLE, fuse, format_table,  # noqa: E402
                    leaf_band, moisture_band)

HEALTHY = LeafReading("healthy", 0.9)
ANOMALOUS = LeafReading("anomalous", 0.9)
UNSURE = LeafReading("anomalous", 0.5)
ABSTAIN = LeafReading("abstain", 0.0)


def test_the_four_core_cells():
    assert fuse(0.6, HEALTHY).flag is Flag.FINE
    assert fuse(0.1, HEALTHY).flag is Flag.UNDERWATERED
    assert fuse(0.6, ANOMALOUS).flag is Flag.DISEASED
    assert fuse(0.1, ANOMALOUS).flag is Flag.WATER_THEN_RECHECK


def test_the_differentiator_cell_names_the_cause():
    r = fuse(0.6, ANOMALOUS)
    assert r.flag is Flag.DISEASED
    assert "not water" in r.cause


def test_judge_question_moisture_042_confidence_055():
    # The exact case from HANDOFF §8: a table lookup, not an inference.
    r = fuse(0.42, UNSURE)
    assert (r.moisture_band, r.leaf_band) == ("NORMAL", "UNKNOWN")
    assert r.flag is Flag.NEEDS_HUMAN


def test_moisture_threshold_boundary():
    assert moisture_band(0.349) == "LOW"
    assert moisture_band(0.35) == "NORMAL"


def test_leaf_confidence_boundary():
    assert leaf_band(LeafReading("anomalous", 0.699)) == "UNKNOWN"
    assert leaf_band(LeafReading("anomalous", 0.70)) == "ANOMALOUS"


def test_low_moisture_survives_leaf_abstention():
    # Moisture is a direct measurement; a blind camera doesn't block watering.
    assert fuse(0.1, ABSTAIN).flag is Flag.UNDERWATERED
    assert fuse(0.1, None).flag is Flag.UNDERWATERED


def test_normal_moisture_with_no_leaf_answer_abstains():
    assert fuse(0.6, ABSTAIN).flag is Flag.NEEDS_HUMAN
    assert fuse(0.6, None).flag is Flag.NEEDS_HUMAN


def test_sensor_fault_never_reads_as_drought():
    for leaf in (HEALTHY, ANOMALOUS, ABSTAIN, None):
        r = fuse(None, leaf)
        assert r.flag is Flag.NEEDS_HUMAN
        assert r.moisture_band == "FAULT"


def test_table_is_total():
    # 3 moisture bands x 3 leaf bands, no blank cells.
    assert set(TABLE) == {(m, l) for m in ("LOW", "NORMAL", "FAULT")
                          for l in ("HEALTHY", "ANOMALOUS", "UNKNOWN")}


def test_unknown_verdict_raises():
    with pytest.raises(ValueError):
        leaf_band(LeafReading("wilted", 0.9))


def test_format_table_prints_every_flag():
    text = format_table()
    for flag in Flag:
        assert flag.value in text
