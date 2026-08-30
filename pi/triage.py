"""Per-plant triage fusion (HANDOFF §8 task 2) — the never-cut layer.

Fuses one calibrated moisture reading and one leaf-vision result into a
single cause-tagged flag. Every input lands in exactly one cell of an
explicit table — when a judge asks "what happens at moisture 0.42 and
leaf confidence 0.55", the answer is a table lookup, not an inference:
0.42 is NORMAL (threshold 0.35), 0.55 is below the 0.70 confidence floor
so the leaf is UNKNOWN, and (NORMAL, UNKNOWN) -> NEEDS_HUMAN.

Abstention is a first-class outcome. A sensor fault or an unconfident
leaf call becomes "needs human inspection", never a forced guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# A plant is LOW below this calibrated moisture (0 = dry air, 1 = water).
MOISTURE_LOW = 0.35
# Leaf verdicts below this confidence are treated as UNKNOWN.
LEAF_MIN_CONFIDENCE = 0.70


class Flag(Enum):
    FINE = "fine"
    UNDERWATERED = "underwatered"
    DISEASED = "diseased"
    WATER_THEN_RECHECK = "water_then_recheck"
    NEEDS_HUMAN = "needs_human"


@dataclass
class LeafReading:
    verdict: str       # "healthy" | "anomalous" | "abstain"
    confidence: float  # 0-1; ignored when verdict is "abstain"
    note: str = ""
    cause: str = "none"   # "disease" | "pest" | "none" — detail, not fused


@dataclass
class TriageResult:
    flag: Flag
    cause: str
    moisture_band: str  # LOW | NORMAL | FAULT
    leaf_band: str      # HEALTHY | ANOMALOUS | UNKNOWN


# The complete rule table. FAULT rows are listed for completeness even though
# fuse() short-circuits them — the printed table must have no blank cells.
TABLE: dict[tuple[str, str], tuple[Flag, str]] = {
    ("LOW", "HEALTHY"): (
        Flag.UNDERWATERED,
        "soil dry, leaves look fine — water it"),
    ("LOW", "ANOMALOUS"): (
        Flag.WATER_THEN_RECHECK,
        "soil dry AND leaves anomalous — water first, re-inspect leaves after recovery"),
    ("LOW", "UNKNOWN"): (
        Flag.UNDERWATERED,
        "soil dry (direct measurement) — water it; leaves could not be verified"),
    ("NORMAL", "HEALTHY"): (
        Flag.FINE,
        "moisture normal, leaves healthy"),
    ("NORMAL", "ANOMALOUS"): (
        Flag.DISEASED,
        "moisture normal but leaves anomalous — likely disease, not water"),
    ("NORMAL", "UNKNOWN"): (
        Flag.NEEDS_HUMAN,
        "moisture normal but leaf check inconclusive — needs human inspection"),
    ("FAULT", "HEALTHY"): (
        Flag.NEEDS_HUMAN,
        "moisture sensor fault — refusing to report a drought from a broken probe"),
    ("FAULT", "ANOMALOUS"): (
        Flag.NEEDS_HUMAN,
        "moisture sensor fault; leaves anomalous — needs human inspection"),
    ("FAULT", "UNKNOWN"): (
        Flag.NEEDS_HUMAN,
        "moisture sensor fault and leaf check inconclusive — needs human inspection"),
}


def moisture_band(moisture: float | None) -> str:
    if moisture is None:
        return "FAULT"
    return "LOW" if moisture < MOISTURE_LOW else "NORMAL"


def leaf_band(leaf: LeafReading | None) -> str:
    if leaf is None or leaf.verdict == "abstain":
        return "UNKNOWN"
    if leaf.verdict not in ("healthy", "anomalous"):
        raise ValueError(f"unknown leaf verdict {leaf.verdict!r}")
    if leaf.confidence < LEAF_MIN_CONFIDENCE:
        return "UNKNOWN"
    return leaf.verdict.upper()


def fuse(moisture: float | None, leaf: LeafReading | None) -> TriageResult:
    """moisture: calibrated 0-1, or None for a sensor fault.
    leaf: vision result, or None if the leaf image was never captured."""
    m = moisture_band(moisture)
    l = leaf_band(leaf)
    flag, cause = TABLE[(m, l)]
    return TriageResult(flag=flag, cause=cause, moisture_band=m, leaf_band=l)


def format_table() -> str:
    """The rule table as text — print this when a judge asks."""
    lines = [
        f"moisture LOW < {MOISTURE_LOW}; leaf UNKNOWN below confidence "
        f"{LEAF_MIN_CONFIDENCE} or on abstain/fault",
        "",
        f"{'moisture':10} {'leaf':10} {'flag':20} cause",
    ]
    for (m, l), (flag, cause) in TABLE.items():
        lines.append(f"{m:10} {l:10} {flag.value:20} {cause}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_table())
