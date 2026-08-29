# Field Triage Rover — Project Handoff

You are picking up an in-progress hardware project. This document is the single
source of truth. Everything below has been verified against a real source —
datasheets, official CAD files, or vendor spec pages. **Do not silently replace
any number here with a guess.** If a dimension is missing, it is missing on
purpose and is listed under "Open questions" — ask, don't invent.

---

## 1. What this is

A small autonomous rover for the **Berkeley Robotics Hackathon** (two people,
one build day: Rishith Chennupati and Varun Chilukuri).

It drives along a row of potted plants and stops at each one. At every stop it
drives a soil probe into the pot, reads soil moisture and temperature, retracts,
then aims a webcam at the canopy and captures a leaf image. Both signals are
fused **per plant** into one cause-tagged flag — *underwatered* vs *diseased* vs
*fine* — instead of reporting raw numbers a human has to interpret.

**The triage/fusion layer is the differentiator and the last thing to cut.**
A rover that reports four numbers has been built many times; one that says
"plant 14: moisture normal, leaf spotted → likely disease, not water" has not.

Cut order if the schedule slips, worst first:
1. Presentation dashboard — cut first
2. Turret / leaf vision
3. Probe subsystem
4. **Per-plant fusion — never cut**

Judging panel includes people from frontier robotics labs. **Claim only what is
actually built.** A smaller fully-real system beats a larger partly-narrated one.

---

## 2. Hardware inventory — all verified

| Component | Verified dimensions / spec | Source |
|---|---|---|
| Raspberry Pi 4B | 85.0 × 56.0 mm, M2.5 holes on a 58 × 49 rectangle, 3.5 mm inset | RPi mechanical drawing |
| Arduino Uno R3 | 68.6 × 53.4 mm, standard Arduino 4-hole pattern | Arduino |
| Inland L298P 4-ch motor shield | 65 × 50 × 30 mm stacked, 3× M3 fixing holes, PH2.0-2P motor connectors, onboard slide switch, BAT input 7–12 V, <4 A total | Micro Center KB article 678 |
| Adafruit 4026 STEMMA soil sensor | 76.20 × 13.97 × 6.37 mm, 1.57 mm FR4, components occupy 0–19.53 mm from the connector end, **56.67 mm of bare blade** | measured from Adafruit's own STEP file |
| MG996R servo ×3 | 40.7 × 19.7 × 42.9 mm, tab span 53.6, hole pitch 49.5, stall 9.4 kgf·cm @4.8 V / 11.0 @6.0 V, stall current 2.5 A | TowerPro, cross-checked Waveshare + Handson |
| Yellow TT gearmotor ×4 | 70 × 37 × 22.5 mm, dual shaft, 1:48 | vendor spec — **hole pattern NOT verified** |
| TT wheel ×4 | assumed 65 mm dia × 26 mm — **not confirmed** | assumption |
| Logitech C920 webcam | mounts via its 1/4"-20 UNC tripod socket | Logitech |
| Energizer power bank | 148.59 × 68.33 × 17.53 mm, 10,000 mAh, 22.5 W | Micro Center listing |
| 3S LiPo (gel-blaster pack) | 11.1 V 2000 mAh 10C, SM-2P plug — **case dimensions NOT measured** | user |
| Printer | Elegoo Neptune 4, 225 × 225 × 265 mm, 0.4 mm nozzle | — |

### Corrections to bad vendor data — do not regress these

- Micro Center lists the 4026 as **"Temperature, Humidity"** with **"Range 100mm
  to 2000mm."** Both wrong. It is a capacitive soil-moisture sensor; 200–2000 is
  the **raw capacitance count** (dry→wet), not millimetres. Temperature is the
  ATSAMD10's internal die sensor, ±2 °C.
- **There is no humidity sensor in this build.** The project write-up says
  "moisture, temperature, humidity." Only the first two exist. Either add an
  SHT31/DHT22 or drop the humidity claim from the pitch.
- The Inland KB article's example sketch has broken `pinMode` calls (it sets
  `MAPin` four times and never `MBPin`/`MCPin`/`MDPin`). Don't use it as a reference.

---

## 3. Electrical architecture

### Motor shield pinout (verified)

| Channel | Direction pin | PWM pin | AVR timer |
|---|---|---|---|
| A | D3 | D6 | Timer0 |
| B | D4 | D5 | Timer0 |
| C | D7 | D10 | **Timer1** |
| D | D8 | D9 | **Timer1** |

### HARD CONSTRAINT — read this before touching motor code

On an Uno R3 the **Servo library owns Timer1**, which is the timer that generates
PWM on **D9 and D10**. The moment any servo is attached, channels C and D lose
speed control and become on/off only.

There are four TT motors and three servos. They cannot coexist on this shield.

Two acceptable resolutions:
1. **Pair the wheels.** Left two motors into channel A, right two into channel B.
   Skid-steer 4WD cannot use independent per-wheel speed anyway. C and D stay
   empty and the conflict disappears. Cost: ~2.4 A stall through a 2 A channel,
   so cap PWM and never let them stall.
2. **Move all three servos to a PCA9685** on the Pi's I²C bus (~$8). Arduino does
   wheels only; the Pi drives the turret and probe. Cleanest split, and it puts
   the camera and the turret on the same machine. Cost: one extra part.

**This decision is still open.** It does not change any printed part.

### Board choice: Uno R3, not R4

R3 was chosen deliberately. The Servo/Timer1 interaction on AVR is documented
with a known workaround; the equivalent behaviour on the R4's Renesas timers is
not. The R4 also has a core bug where `digitalWrite()` on a pin that previously
saw `analogWrite()` does not restore a clean rail. The firmware respects that
anyway: **DIR pins are only ever `digitalWrite`, PWM pins only ever `analogWrite`,
and motor stop is `analogWrite(pin, 0)`.** Keep it that way.

### Free pins after the shield

Shield occupies D3–D10. Free: **D2, D11, D12, D13, A0–A5.**
Servos go on **D11, D12, D2**. Avoid D13 (onboard LED + resistor) and D0/D1
(hardware UART — also where the shield's HM-10 header sits, and the same UART
the Pi's USB connection uses; leave that header unpopulated).

### Power rails

The pack is a 3S LiPo at 10C — 20 A available. Steady-state draw is ~1.1–1.3 A,
worst case ~3.5 A. Capacity is not the constraint; rail separation is.

| Rail | Feeds | Notes |
|---|---|---|
| 8.5 V buck | Shield **BAT** terminal | Shield spec is 7–12 V; 8.5 V puts ~6 V on the motors after the L298 bridge drop. Raw 11.1 V would put ~8.6 V on 3–6 V motors. |
| 5.5 V buck, **5 A minimum** | 3× servo V+ only | MG996R stalls at 2.5 A each. A 3 A buck is undersized. |
| 5.1 V buck | Raspberry Pi | Pi then powers the Uno over USB. |

Non-negotiables: inline fuse on the pack positive, 3S low-voltage alarm on the
balance lead, common ground star point, 1000 µF at the servo rail and 470 µF at
the shield BAT input. The shield's onboard slide switch **is** the master switch —
don't add a second one. The Uno auto-selects VIN over USB, so having the Pi
plugged in at the same time is safe.

**Never power servos from the Arduino 5 V pin or the shield's regulator.**
That regulator is good for maybe 500 mA against a ~2 A servo peak. This is the
single most common way this exact build dies.

---

## 4. Firmware — already written

`rover_motion.ino` is complete and compiles for the Uno R3. It is a serial slave;
the Pi owns sequencing, vision and triage, the Arduino owns anything with a
deadline.

### Protocol (ASCII, newline-terminated)

```
PING                   -> OK PONG
FWD <ms> <pwm>         -> OK FWD      drive forward, auto-stops after <ms>
REV <ms> <pwm>         -> OK REV
SPIN <ms> <pwm> <L|R>  -> OK SPIN
STOP                   -> OK STOP
PROBE <0-100>          -> OK PROBE    0 = retracted, 100 = fully inserted
PAN <deg> / TILT <deg> -> OK PAN|TILT
HOME                   -> OK HOME
STATUS                 -> OK <drive> <pwm> <probe> <pan> <tilt> <settled> <uptime>
error                  -> ERR <reason>
```

Safety behaviours already implemented, keep them:
- **No untimed motion.** Every drive command carries its own duration.
- **Host watchdog.** If the Pi goes silent while wheels turn, motors cut.
- **`PROBE` is refused while the chassis is moving.** A probe part-way down while
  the rover rolls is a snapped probe.
- **Servos slew at ~83 °/s** rather than snapping.
- A `READY` banner is emitted after init because opening the serial port resets
  the MCU — the Pi should sync on that instead of guessing.

Firmware rules that must hold in any Pi-side driver you write:
- **Never park the probe loaded.** Insert, dwell, retract. Full stall torque is
  fine for a 1–2 s insertion; holding position against soil will cook the servo.
- **Dwell before reading temperature** — the die sensor needs seconds to settle.
- **Two-point calibrate moisture** (dry in air, submerged in water) so the number
  is defensible when a judge asks what the units are.

---

## 5. CAD — already designed and verified

All parametric CadQuery. Two source modules regenerate everything:

- `probe_module.py` — soil probe actuator (5 parts)
- `chassis_module.py` — chassis, mounts, turret (10 parts)
- `design_calcs.py` — every number the probe geometry derives from

### Probe actuator — locked design values

| Quantity | Value | Reasoning |
|---|---|---|
| Insertion depth | 35.0 mm | capped by 56.67 mm bare blade − 20 mm dry margin |
| Throat ground clearance | 12.0 mm | blade tip parks here |
| Stroke | 47.0 mm | clearance + depth |
| Gearing | module 2, z=18 pinion, Ø36 pitch, 12 mm face | smallest set clearing 47 mm at a conservative 150° servo sweep |
| Backlash | 0.30 mm, taken from rack tooth thickness | |
| Linear force at stall | 56.3 N | MG996R derated to the 5.5 V rail |
| Design load | 21.9 N | moist garden soil: tip bearing + skin friction |
| Safety factor | 2.57 (6.43 in loose potting mix) | |
| Gear tooth stress | 7.59 MPa (Lewis) | SF 2.37 in PETG |
| Blade buckling | SF > 100 guided, 3.2 unguided | why the throat exists |
| Dry margin at full insertion | 21.7 mm | |

**Graceful degradation:** the design assumes 150° of servo sweep, which needs a
600–2400 µs pulse range rather than the default 1000–2000 µs. At a worst-case
120° the insertion depth drops to 25.7 mm — shallower but still a valid reading.

**Out of scope:** packed clay needs 52.6 N, above what's reliably available.
Use loose potting mix in the demo pots. That's a variable you control.

### Chassis geometry

| | |
|---|---|
| Deck | 200 × 140 × 5 mm, top face at **Z = 45 mm** |
| Wheelbase | 124 mm |
| Track | 170 mm |
| Overall width with wheels | **196 mm** |
| Axle height | 32.5 mm (65 mm wheels) |
| Uno + shield stack top | Z = 87 mm |

Z = 45 is not arbitrary — it's the 65 mm wheel radius plus the TT gearbox height,
and it's the same Z the probe frame's mounting flange targets. The two modules
bolt together with no adjustment. **If the wheel diameter changes, both modules
must be regenerated.**

### Part list

**Probe module** — `01_frame`, `02_carriage`, `03_pinion`, `04_clamp`, `05_servo_gauge`
**Chassis** — `01_deck`, `02_motor_clamp` (×4), `03_motor_gauge`, `04_pi_tray`,
`05_uno_tray`, `06_powerbank_sling`, `07_lipo_cradle`, `08_turret_base`,
`09_turret_yoke`, `10_cam_cradle`

All 15 parts: watertight, winding-consistent, single-solid, and fit the Neptune 4
envelope printed flat. Boolean interference checks are clear between frame and
carriage at both stroke ends, and between frame and pinion.

### Print settings

PETG, 0.2 mm layers, 4 perimeters, 40% gyroid. No supports on any part.
PLA works but cracks instead of yielding when the probe hits a stone.

**Two orientations are load-bearing, not preferences:**
- `02_carriage` and `03_pinion` must print **flat**, teeth in the layer plane.
  Printed upright the teeth load across layer lines and the Lewis stress
  calculation above is void.
- `01_frame` prints with its −Y face on the bed so all channel walls come out
  vertical and the throat mouth (a loft, not a chamfer) needs no support.

### Design decisions made deliberately — don't "improve" these

- **No printed servo spline anywhere.** A printed 25T spline strips on the first
  stall. The metal horn carries torque; printed parts have a 24 mm horn pocket
  with four radial slots that accept any horn hole between r=5 and r=11, so
  nothing needs drilling.
- **The motor clamp ignores the TT motor's own screw holes.** Vendors disagree
  on that pattern and it hasn't been measured. The clamp grips the gearbox body
  and pulls closed on captive M3 nuts. It can't be wrong about a pattern it
  never uses.
- **The LiPo cradle is a strap tray, not a pocket.** 3S bricks range from about
  95×30×20 to 115×40×28 and this one hasn't been measured.
- **The camera mounts through the C920's 1/4"-20 socket**, with a raised
  anti-rotation pad. That thread is the only dimensionally guaranteed feature;
  the clip's moulded shape varies between revisions.
- **The pan servo carries no overturning moment.** The yoke rides on a printed
  thrust collar in the turret base bore, so the MG996R spline sees torque only.
  Without it the turret develops a wobble within an hour.
- **Turret uprights sit outboard at X = ±40** because the C920 is ~94 mm wide.
- **Two gauge coupons exist for a reason.** `05_servo_gauge` (8 min) and
  `03_motor_gauge` (5 min) verify the two component fits that are based on
  disputed vendor data. Print both before committing to the full parts.

---

## 6. Expected files on disk

```
field-triage-rover/
├── firmware/
│   └── rover_motion.ino
├── cad/
│   ├── design_calcs.py          # regenerates every probe number
│   ├── design_calcs.txt         # last run output
│   ├── probe_module.py
│   ├── chassis_module.py
│   ├── probe_module/{step,stl,render}/
│   └── chassis/{step,stl,render}/
└── HANDOFF.md                   # this file
```

Rebuild everything with CadQuery 2.8 (`pip install cadquery --break-system-packages`).
QC harnesses `build_and_inspect.py` and `build_chassis.py` re-export, re-run the
interference and envelope checks, and re-render six views per part.

---

## 7. Open questions — ask, do not guess

1. **Row / pot spacing.** Drives the 196 mm overall width. If pots are closer
   than ~250 mm on centre, the track has to narrow.
2. **Wheel diameter.** Modelled at 65 mm. Any change moves the deck height and
   breaks probe/chassis alignment.
3. **TT gearbox cross-section.** Print `03_motor_gauge` and confirm before
   printing four clamps.
4. **MG996R tab pattern.** Print `05_servo_gauge` and confirm.
5. **3S LiPo case dimensions.**
6. **Motor wiring:** wheels paired on channels A/B, or servos moved to a PCA9685?

---

## 8. Suggested next tasks, in order

1. **Pi-side Python driver** for the serial protocol in §4 — a `Rover` class with
   connection handling (tolerate the reset-on-open), command/ack parsing, and
   timeouts. No sequencing logic yet.
2. **Fusion rule table.** Four cells: {low, normal moisture} × {leaf healthy,
   anomalous}, each mapping to a flag, plus abstention as a fifth outcome. This
   is testable with no hardware, so it can be built in parallel with mechanical
   debugging. It's also the thing a judge will ask about — "what happens at
   moisture 0.42 and leaf confidence 0.55" needs a table, not an inference.
3. **Moisture calibration routine** — two-point normalisation, plus a boot-time
   self-check so a broken probe reads as a fault rather than as a drought.
4. **Leaf vision call** with confidence-aware abstention ("needs human
   inspection") instead of a forced guess.
5. **Row sequencing** — see the open risk below.

### Known unsolved problems, honestly stated

- **Stopping at the right plant is open-loop.** `FWD 800 120` covers a different
  distance on a table than on soil, and TT motors are badly mismatched
  pair-to-pair. Over six plants the error compounds until the probe hits dirt
  between pots. Cheapest fix: don't measure distance at all — put a reflectance
  sensor or limit switch at each pot and drive until it fires.
- **The leaf model doesn't exist yet.** PlantVillage-trained classifiers report
  ~99% on that dataset and fall apart on real leaves under real lighting.
  Either use a hosted VLM with a constrained prompt, or restrict the claim to
  something classical CV can actually support.
- **The turret has no idea whether the leaf is in frame.** It pans to a fixed
  angle and captures whatever is there.
- **Traction on soil is untested.** TT motors, plastic wheels, a LiPo, a Pi and
  a probe rack is a heavy low-torque platform. Test the drivetrain on the actual
  demo surface before building anything on top of it.

---

## 9. How to work on this

- Don't replace a verified dimension with a plausible-looking one. Every number
  in §2 has a source; if you need one that isn't there, ask.
- Regenerate CAD from the parametric modules — don't hand-edit STLs.
- After any geometry change, re-run the QC harness and **look at the renders**.
  Five real defects in this project were caught by rendering and inspecting from
  six angles, not by the numbers: a throat that trapped the carriage at full
  insertion, a gusset built on the wrong workplane, a pinion placement that drove
  the gear through a side wall, a turret yoke that came out as two disconnected
  lumps, and a yoke narrower than the camera it was meant to hold.
- Prefer a smaller working system over a larger described one. See §1.
