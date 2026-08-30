"""Station scan: pose sequence, majority combining, honest abstention."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from station import combine_readings, scan_plant  # noqa: E402
from triage import Flag, LeafReading  # noqa: E402

H = lambda c=0.9: LeafReading("healthy", c)
A = lambda c=0.9, cause="disease": LeafReading("anomalous", c, "spots", cause)
AB = LeafReading("abstain", 0.0)


def test_combine_majority_anomalous_carries_cause():
    r = combine_readings([A(0.8, "pest"), A(0.9, "pest"), H(0.9), AB])
    assert r.verdict == "anomalous" and r.cause == "pest" and r.confidence == 0.9


def test_combine_healthy_needs_two_confident_and_no_confident_anomalous():
    assert combine_readings([H(), H(), AB, AB]).verdict == "healthy"
    assert combine_readings([H(), H(), A(0.9), AB]).verdict == "abstain"


def test_combine_single_or_unsure_frames_abstain():
    assert combine_readings([A(0.9), AB, AB, AB]).verdict == "abstain"
    assert combine_readings([A(0.5), A(0.6), H(0.5), AB]).verdict == "abstain"


class FakeRover:
    def __init__(self): self.calls = []
    def tilt(self, d): self.calls.append(("tilt", d))
    def wait_for_settled(self, **kw): self.calls.append(("settle",))
    def pan_nudge(self, ms, side): self.calls.append(("nudge", ms, side))


class FakeCamera:
    def __init__(self): self.n = 0
    def capture(self, path):
        self.n += 1
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"jpg")
        return Path(path)


def test_scan_plant_full_flow(tmp_path):
    rover, cam = FakeRover(), FakeCamera()
    verdicts = iter([A(0.85), A(0.9), H(0.9), AB])
    rep = scan_plant(rover, cam, "plant-3", out_dir=tmp_path,
                     moisture=0.6, classify=lambda p: next(verdicts))
    assert rep.result.flag is Flag.DISEASED
    assert rep.leaf.cause == "disease"
    assert cam.n == 4 and len(rep.frames) == 4
    tilts = [c[1] for c in rover.calls if c[0] == "tilt"]
    assert all(74 <= t <= 118 for t in tilts)          # every pose inside the fence
    nudges = [c for c in rover.calls if c[0] == "nudge"]
    assert len(nudges) == 1                             # staggered: center pose only
    assert "plant-3" in rep.line()


def test_scan_without_moisture_abstains_on_water(tmp_path):
    rep = scan_plant(FakeRover(), FakeCamera(), "p1", out_dir=tmp_path,
                     moisture=None, classify=lambda p: H())
    assert rep.result.moisture_band == "FAULT"
    assert rep.result.flag is Flag.NEEDS_HUMAN
