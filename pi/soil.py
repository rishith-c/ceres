"""Two-point moisture calibration + boot self-check (HANDOFF §8 task 3).

The Adafruit 4026 reports a raw capacitance count, roughly 200 (dry air)
to 2000 (submerged) — NOT millimetres, whatever Micro Center says. The
two-point calibration makes the number defensible: 0.0 is this sensor in
dry air, 1.0 is this sensor in water, measured on demo day.

The boot self-check exists so a broken probe reads as a FAULT (moisture
None -> triage abstains) instead of as a drought.
"""

from __future__ import annotations

from dataclasses import dataclass

# Raw counts outside this window are physically implausible for a working
# 4026 (nominal 200-2000) and mean a wiring/sensor fault, not dry soil.
RAW_PLAUSIBLE_MIN = 100
RAW_PLAUSIBLE_MAX = 2200

# A dry/wet calibration pair closer together than this is a bad calibration
# (sensor never actually went in the water, or never dried).
MIN_CAL_SPAN = 300

# At boot the retracted probe hangs in air: it must read near its own dry
# point, within this fraction of the calibrated span.
SELF_CHECK_TOLERANCE = 0.15


@dataclass
class SoilCalibration:
    raw_dry: int   # reading in dry air
    raw_wet: int   # reading submerged in water

    def __post_init__(self):
        if self.raw_wet - self.raw_dry < MIN_CAL_SPAN:
            raise ValueError(
                f"calibration span {self.raw_wet - self.raw_dry} < {MIN_CAL_SPAN}; "
                "redo the dry-air and in-water readings")

    def moisture(self, raw: int) -> float | None:
        """Raw count -> calibrated 0-1, or None if the reading is implausible
        (feed None straight into triage.fuse — it abstains)."""
        if not RAW_PLAUSIBLE_MIN <= raw <= RAW_PLAUSIBLE_MAX:
            return None
        m = (raw - self.raw_dry) / (self.raw_wet - self.raw_dry)
        return min(1.0, max(0.0, m))


def self_check(raw_in_air: int, cal: SoilCalibration) -> tuple[bool, str]:
    """Run at boot with the probe retracted. Returns (ok, message)."""
    if not RAW_PLAUSIBLE_MIN <= raw_in_air <= RAW_PLAUSIBLE_MAX:
        return False, (f"raw {raw_in_air} outside plausible range "
                       f"[{RAW_PLAUSIBLE_MIN}, {RAW_PLAUSIBLE_MAX}] — check wiring")
    span = cal.raw_wet - cal.raw_dry
    drift = abs(raw_in_air - cal.raw_dry)
    if drift > SELF_CHECK_TOLERANCE * span:
        return False, (f"in-air reading {raw_in_air} is {drift} counts from the "
                       f"dry point {cal.raw_dry} (limit {SELF_CHECK_TOLERANCE * span:.0f}) "
                       "— recalibrate or check the probe")
    return True, "soil sensor self-check passed"
