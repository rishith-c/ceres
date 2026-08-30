"""One plant station: aim -> capture -> classify -> fuse (HANDOFF §8 glue).

scan_plant() sweeps the camera through a small set of poses, captures a
frame at each, classifies every frame, and combines them into one honest
LeafReading (majority with abstention), then fuses with moisture.

Safety by construction:
- Every tilt pose sits well inside the measured 74-118 deg fence, and the
  firmware clamps anyway — the turret cannot hammer itself.
- Pan nudges fire only at the center tilt pose (big servos take turns; the
  simultaneous-peak case is what caused intermittent stalling on the bench).
- The wheels are never touched here; probe/moisture is the caller's job
  (pass moisture=None until the soil sensor is wired, and triage abstains
  from moisture-based flags honestly).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from leaf import classify_leaf
from triage import LEAF_MIN_CONFIDENCE, LeafReading, TriageResult, fuse

# (tilt_deg, pan_nudge) — nudges only at center tilt, all tilts within fence.
POSES = [
    (96, None),          # straight-ish on
    (82, None),          # low canopy
    (110, None),         # high canopy
    (96, ("L", 300)),    # nudge back left at center, one more frame
]
SETTLE_EXTRA_S = 0.4     # camera shake dies down after servos settle


def combine_readings(readings: list[LeafReading]) -> LeafReading:
    """Majority-with-abstention across frames.
    - >=2 confident 'anomalous' frames -> anomalous (max confidence; cause by
      majority among confident anomalous frames)
    - >=2 confident 'healthy' frames and 0 confident anomalous -> healthy
    - anything else -> abstain (not enough agreement to accuse or acquit)
    """
    conf_anom = [r for r in readings
                 if r.verdict == "anomalous" and r.confidence >= LEAF_MIN_CONFIDENCE]
    conf_ok = [r for r in readings
               if r.verdict == "healthy" and r.confidence >= LEAF_MIN_CONFIDENCE]
    if len(conf_anom) >= 2:
        causes = [r.cause for r in conf_anom if r.cause != "none"]
        cause = max(set(causes), key=causes.count) if causes else "none"
        best = max(conf_anom, key=lambda r: r.confidence)
        return LeafReading("anomalous", best.confidence,
                           f"{len(conf_anom)}/{len(readings)} frames agree: {best.note}",
                           cause=cause)
    if len(conf_ok) >= 2 and not conf_anom:
        avg = sum(r.confidence for r in conf_ok) / len(conf_ok)
        return LeafReading("healthy", round(avg, 3),
                           f"{len(conf_ok)}/{len(readings)} frames agree healthy")
    return LeafReading("abstain", 0.0,
                       f"frames disagree or are unsure "
                       f"({len(conf_anom)} anomalous / {len(conf_ok)} healthy "
                       f"of {len(readings)})")


@dataclass
class PlantReport:
    plant_id: str
    result: TriageResult
    leaf: LeafReading
    moisture: float | None
    frames: list[str] = field(default_factory=list)

    def line(self) -> str:
        detail = f" [{self.leaf.cause}]" if self.leaf.cause != "none" else ""
        return f"{self.plant_id}: {self.result.flag.value}{detail} — {self.result.cause}"

    def append_to(self, path: str | Path = "work/reports.jsonl") -> None:
        """One JSONL row per report — the live dashboard reads this file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            f.write(json.dumps({
                "plant_id": self.plant_id, "flag": self.result.flag.value,
                "cause": self.result.cause, "leaf_cause": self.leaf.cause,
                "moisture": self.moisture, "leaf_note": self.leaf.note,
                "frames": self.frames, "ts": time.time(),
            }) + "\n")


def scan_plant(rover, camera, plant_id: str, out_dir: str | Path = "work/frames",
               moisture: float | None = None, classify=classify_leaf,
               poses=POSES) -> PlantReport:
    """Full leaf inspection at one plant. rover: rover.Rover (connected).
    moisture: calibrated 0-1 from the soil probe, or None if not measured."""
    out_dir = Path(out_dir)
    readings, frames = [], []
    for i, (tilt, nudge) in enumerate(poses):
        rover.tilt(tilt)
        rover.wait_for_settled()
        if nudge is not None:
            side, ms = nudge[0], nudge[1]
            rover.pan_nudge(ms, side)
            time.sleep(ms / 1000 + 0.3)
        time.sleep(SETTLE_EXTRA_S)
        frame = camera.capture(out_dir / f"{plant_id}_pose{i}.jpg")
        frames.append(str(frame))
        readings.append(classify(frame))
    rover.tilt(96)
    rover.wait_for_settled()
    leaf = combine_readings(readings)
    return PlantReport(plant_id=plant_id, result=fuse(moisture, leaf),
                       leaf=leaf, moisture=moisture, frames=frames)
