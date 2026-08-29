"""Leaf vision with confidence-aware abstention (HANDOFF §8 task 4).

Sends one leaf photo to Claude (a hosted VLM with a constrained prompt —
the HANDOFF-recommended route, since PlantVillage-style classifiers fall
apart on real leaves under real lighting) and returns a triage.LeafReading.

Every failure mode — no API key, no network, refusal, garbage output,
leaf not visible — returns verdict "abstain", never a forced guess.
Triage then reports "needs human inspection" instead of a wrong flag.

Needs ANTHROPIC_API_KEY in the environment and `pip install anthropic`.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from triage import LeafReading

MODEL = "claude-opus-5"

PROMPT = """You are inspecting a single potted plant for a field triage rover.
Look only at the plant canopy in this photo and answer:

- "healthy": leaves look normal for the plant (color, texture, no lesions)
- "anomalous": visible spots, lesions, mildew, chlorosis, necrosis, curling,
  or other disease-consistent damage. Wilting ALONE is not anomalous — the
  rover measures soil moisture separately.
- "abstain": you cannot make that call — leaves are not clearly visible,
  the image is blurry or dark, or there is no plant in frame.

confidence is your 0-1 confidence in the verdict. If in doubt, abstain:
a wrong flag is worse than "needs human inspection"."""

SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["healthy", "anomalous", "abstain"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "note": {"type": "string", "description": "one short sentence of evidence"},
    },
    "required": ["verdict", "confidence", "note"],
    "additionalProperties": False,
}

_MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def _abstain(why: str) -> LeafReading:
    return LeafReading(verdict="abstain", confidence=0.0, note=why)


def classify_leaf(image_path: str | Path, client=None) -> LeafReading:
    """Classify one canopy photo. client is injectable for tests; by default
    an anthropic.Anthropic() is built from the environment."""
    path = Path(image_path)
    media_type = _MEDIA_TYPES.get(path.suffix.lower())
    if media_type is None:
        return _abstain(f"unsupported image type {path.suffix!r}")
    try:
        image_b64 = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    except OSError as e:
        return _abstain(f"could not read image: {e}")

    try:
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        response = client.with_options(timeout=60.0).messages.create(
            model=MODEL,
            max_tokens=1024,
            output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image",
                     "source": {"type": "base64", "media_type": media_type,
                                "data": image_b64}},
                    {"type": "text", "text": PROMPT},
                ],
            }],
        )
    except Exception as e:  # no key, no network, API error — all abstain
        return _abstain(f"vision call failed: {e}")

    if response.stop_reason != "end_turn":
        return _abstain(f"vision call stopped early ({response.stop_reason})")
    try:
        text = next(b.text for b in response.content if b.type == "text")
        data = json.loads(text)
        verdict = data["verdict"]
        confidence = float(data["confidence"])
        if verdict not in ("healthy", "anomalous", "abstain"):
            return _abstain(f"model returned unknown verdict {verdict!r}")
        if not 0.0 <= confidence <= 1.0:
            return _abstain(f"model returned confidence {confidence} outside 0-1")
    except (StopIteration, KeyError, ValueError, TypeError) as e:
        return _abstain(f"unparseable vision reply: {e}")

    return LeafReading(verdict=verdict, confidence=confidence,
                       note=str(data.get("note", "")))
