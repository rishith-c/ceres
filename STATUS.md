# Project status — 2026-08-28 session

## What happened to the files

Only the chassis half of the project survived on this machine, in
`~/Developer/files/` (copied here under `cad/`; the originals were left in
place — treat this repo as canonical from now on and delete `~/Developer/files`
when convenient). Searched the whole disk, Downloads archives, and git
history: **these HANDOFF §6 files are lost**, not misplaced:

- `firmware/rover_motion.ino` (original) — **rebuilt this session**, see below
- `cad/probe_module.py` + probe STEP/STL/renders — **still missing**
- `cad/design_calcs.py` / `design_calcs.txt` — **still missing**
- QC harnesses `build_and_inspect.py`, `build_chassis.py` — **still missing**

The probe module was NOT recreated on purpose: HANDOFF §5 records its locked
design values but not the full part geometry, and §9 forbids replacing
verified numbers with plausible ones. If the original session's outputs exist
anywhere (another machine, a download link, chat history), recover them.
Otherwise the probe CAD must be re-derived properly — through the
aero-mechatronics/cad pipeline, reproducing the §5 numbers exactly — before
printing probe parts. The chassis is fine: its source (`cad/chassis_module.py`)
survived.

## Rebuilt this session

**`firmware/rover_motion/rover_motion.ino`** — rewritten from the HANDOFF §4
spec. Compiles clean for `arduino:avr:uno` (7836 B flash / 492 B RAM). All
specified behaviours implemented: timed motion with auto-stop, 400 ms host
watchdog, PROBE refused while moving, ~83 °/s servo slew, READY banner,
STATUS fields, DIR=digitalWrite / PWM=analogWrite / stop=analogWrite(0).
Deltas from the (unseen) original — flagged, not silent:

- Wiring assumption: **§3 resolution 1** (wheels paired on channels A/B,
  servos on D11/D12/D2). If you pick the PCA9685 route instead, PROBE/PAN/
  TILT/HOME move to the Pi and the firmware shrinks to wheels-only.
- Added the reciprocal safety guard: drive commands are refused while the
  probe is deployed (`ERR probe_deployed`).
- PWM capped at 200/255 in firmware (paired motors ~2.4 A stall vs the 2 A
  L298 channel).
- Baud 115200. Drive durations capped at 10 s.
- The watchdog means the Pi **must keep talking during motion** — the driver's
  `wait_for_stop()` polls STATUS and is that keepalive. Not flashed to
  hardware yet; bench-test PWM polarity (A_FORWARD/B_FORWARD constants) first.

## New this session (HANDOFF §8 tasks 1–4) — 37 tests pass, no hardware needed

- `pi/rover.py` — serial driver: READY sync on connect (reset-on-open),
  OK/ERR/timeout parsing, STATUS dataclass, wait_for_stop/wait_for_settled,
  client-side validation. No sequencing logic, per the task spec.
- `pi/triage.py` — the never-cut fusion layer. Total 3×3 rule table
  (moisture LOW/NORMAL/FAULT × leaf HEALTHY/ANOMALOUS/UNKNOWN), abstention
  first-class. Thresholds: moisture LOW < 0.35, leaf confident ≥ 0.70.
  `python3 pi/triage.py` prints the judge-ready table. The §8 judge case
  (moisture 0.42, confidence 0.55 → NORMAL × UNKNOWN → needs_human) is a
  tested lookup.
- `pi/soil.py` — two-point calibration (raw 200–2000 counts → 0–1) with
  plausibility bounds and a boot self-check, so a broken probe reads as a
  FAULT (→ triage abstains), never as a drought.
- `pi/leaf.py` — hosted-VLM leaf call (Claude, `claude-opus-5`, constrained
  JSON schema). Every failure — no key, no network, refusal, garbage output,
  leaf not visible — returns abstain. Needs `ANTHROPIC_API_KEY` and
  `pip install anthropic` on the Pi. Untested against the live API; the
  parsing/abstention paths are unit-tested with a fake client.
- Run everything: `pytest pi/tests` (needs pytest; pyserial only on the Pi).

## Still open (HANDOFF §7 — answers needed, don't guess)

Pot spacing, wheel diameter, TT gearbox gauge, MG996R gauge, LiPo case
dimensions, and the A/B-pairing vs PCA9685 wiring decision. Plus §8 task 5
(row sequencing) — blocked on the stop-at-plant sensing decision.
