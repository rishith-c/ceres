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

## Defect found 2026-08-28 while building the mock assembly (cad/mock_assembly.py)

**The deck's feature axes conflict with the designed track.** The deck is
200 × 140 with the probe notch centered on a 200 mm edge and the turret on the
opposite 200 mm edge — i.e. the features treat the 140 axis as fore-aft. But
the motor clamps at (±56, ±62) put the wheels at X ≈ ±85 (track 170 as
designed), and a Ø65 wheel (top at Z = 65) at X 72–98 passes straight through
the deck plate corners (deck sits at Z ≈ 40–50, spanning X ±100). Track 170 /
overall width 196 is only possible if the deck is ~140 wide at the wheel
stations — the 200 axis must run fore-aft, which contradicts the probe/turret
edge placement. Corroborating signs of the same axis mix-up in `make_deck()`:
half of each motor-clamp bolt pair lands at y = ±74, off the ±70 plate edge;
and `TRACK` is derived from `DECK_W` while the clamp X positions also use
`DECK_W`. Separate 4–5 mm issue: gearbox top sits at Z = 44, so the deck
bottom must be at 45 (per the code's own `DECK_Z` formula) — the README's
"top face at Z = 45" would put the deck bottom at 40, inside the gearboxes.

**Do not print `01_deck` until this is resolved.** Fix in chassis_module.py:
keep the 200 axis fore-aft, move the probe slot/flange to one 140 edge and
the turret pattern to the other, put the wheelbase (±62) along the long axis,
then re-run QC and re-render. The mock viewer shows the clip honestly —
explode it and look at the wheel corners.

## 2026-08-29 — shield died, architecture pivoted

The Inland L298P shield took the 3S pack reverse-polarity (BAT + to −) and
its motor stage is dead: logic LED lives, no channel moves. Uno, motors,
and pack survived. New electrical architecture, replacing HANDOFF §3's
open decision with a hybrid of both options:

- **Wheels:** TWO L298N modules, one per side, all 12 control pins wired
  independently (per the LastMinuteEngineers diagram, at the builder's
  request), now on an **Arduino Mega 2560** (pin map also works on an Uno).
  Board 1 = LEFT: ENA 9, IN1 8, IN2 7, IN3 5, IN4 4, ENB 3 (verified working
  with the LME demo). Board 2 = RIGHT: ENA 10, IN1 11, IN2 12, IN3 13,
  IN4 2, ENB 6.
  Battery daisy-chain: pack + → board1 +12V → jumper → board2 +12V; pack −
  → board1 GND → jumper → board2 GND; one wire board1 GND → Uno GND.
  Per-motor direction flips live in FWD_HIGH[] in the firmware.
- **Servos:** PCA9685 on the Pi's I²C. Roster changed from 3× MG996R:
  ch0 probe = MG996R (mandatory — force calc), ch1 pan = **SG90** (OK only
  because the thrust collar carries the moment; NOTE the printed turret
  base pocket is MG996R-sized — needs re-parameterizing, fold into the
  deck-fix task), ch2 tilt = MG996R.
- **Firmware v2** (`rover_motion.ino`): wheels-only, PROBE/PAN/TILT/HOME
  removed, STATUS is now `OK <drive> <pwm> <uptime>`, MAX_PWM 160 for
  direct-3S operation. `pi/actuators.py` owns the servos (slew, never-park-
  loaded via `sample()`), and the **probe-vs-motion interlock now lives on
  the Pi**: check `ProbeTurret.probe_deployed` before any drive command.
- Bench sketches: `firmware/motor_test/` (old shield, 4-channel),
  `firmware/motor_test_l298n/` (interactive), `firmware/motor_demo_4x/`
  (auto-looping LME-style), `pi/servo_test.py` (PCA9685). All compile for
  Mega and Uno.

## Still open (HANDOFF §7 — answers needed, don't guess)

Pot spacing, wheel diameter, TT gearbox gauge, MG996R gauge, and the
A/B-pairing vs PCA9685 wiring decision. Plus §8 task 5 (row sequencing) —
blocked on the stop-at-plant sensing decision.

**LiPo answered 2026-08-29** (Amazon listing, Tosiicop 2-pack): 3S 11.1 V
2000 mAh **30C** (not 10C as HANDOFF §2 said — 60 A short-circuit capable,
the inline fuse is not optional), 106 × 18 × 20 mm, 73 g, SM-2P discharge
plug + XH-4P balance, mini-Tamiya adapter included. Fits the strap-tray
cradle easily. All four TT motors are currently wired to shield channels
A–D for bench testing with firmware/motor_test/motor_test.ino.
