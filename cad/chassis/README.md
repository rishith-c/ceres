# Field Triage Rover — Chassis, Mounts and Turret, v1

Ten parts. Same standard as the probe module: every dimension traced to a
source, boolean-checked, rendered from six angles and inspected before release.

## Chassis geometry

| | |
|---|---|
| Deck | 200 × 140 × 5 mm, top face at Z = 45 mm |
| Wheelbase | 124 mm |
| Track | 170 mm |
| **Overall width with wheels** | **196 mm** |
| Axle height | 32.5 mm (65 mm wheels) |
| Under-deck clearance | 33 mm to the rib bottoms |
| Uno + shield stack top | Z = 87 mm |

**196 mm is the number to check against your row spacing.** You never gave me
pot spacing, so this is sized for a comfortable printed plate, not for your
demo bed. If your pots are closer than ~250 mm on centre, tell me and I'll
narrow the track — it costs one parameter.

The deck top at Z = 45 is not arbitrary: it's set by the 65 mm wheel radius plus
the TT gearbox height, and it's the same Z the probe frame's flange was designed
to bolt to. The two modules line up without adjustment.

## Parts

| File | Qty | Print orientation |
|---|---|---|
| `01_deck` | 1 | flat, ribs up (they print as walls, no support) |
| `02_motor_clamp` | **4** | mouth up |
| `03_motor_gauge` | 1 | flat — **print this first** |
| `04_pi_tray` | 1 | flat |
| `05_uno_tray` | 1 | flat |
| `06_powerbank_sling` | 1 | flat |
| `07_lipo_cradle` | 1 | flat |
| `08_turret_base` | 1 | open face up |
| `09_turret_yoke` | 1 | base down |
| `10_cam_cradle` | 1 | cradle face down |

PETG, 0.2 mm, 4 perimeters, 40% gyroid. Nothing needs support material.

## Three decisions that were made deliberately

**The motor clamp ignores the TT motor's own screw holes.** Vendors disagree on
that pattern and I have not measured yours, so the clamp grips the gearbox body
instead and pulls closed with two M3 bolts into captive hex nuts. It cannot be
wrong about a hole pattern it never uses. Print `03_motor_gauge` first — if the
gearbox does not slide in under light thumb pressure, measure it and tell me
before you print four clamps.

**The LiPo cradle is a strap tray, not a pocket.** You have never given me the
gel-blaster pack's case dimensions, and 3S 2000 mAh bricks range from about
95 × 30 × 20 to 115 × 40 × 28. A toleranced pocket would be a guess dressed up
as precision. The tray takes anything in that range and holds it with two velcro
straps.

**The camera mounts through the C920's 1/4"-20 tripod socket.** That thread is
the one dimensionally guaranteed feature on the camera; the clip's moulded shape
differs between revisions. A raised anti-rotation pad stops the camera pivoting
about the single screw.

**The turret uprights sit outboard at X = ±40.** The C920 is roughly 94 mm wide,
so an inboard yoke would have to be narrower than the camera it carries. Putting
them outboard also lets the tilt servo mount with its long axis horizontal, so
its 53.6 mm tab span fits a 60 mm upright instead of forcing a 66 mm post.

**The pan servo does not carry the camera's overturning moment.** The yoke has a
printed thrust collar that rides in a bore in the turret base. The servo spline
sees torque only. Without this, an MG996R's output bearing takes a bending load
it was never specified for, and the turret develops a wobble by the second hour.

## Assembly order

1. Motor gauge → verify → print four clamps.
2. Clamps to the deck underside, motors in, clamp bolts snug **but not crushed** —
   the gearbox is moulded plastic and will deform.
3. Wheels on. Roll it on the demo surface before adding anything else. If a
   65 mm plastic wheel won't get traction on your soil bed, everything above
   this line is wasted.
4. Power bank sling and LiPo cradle underneath, straps through the deck slots.
5. Pi tray and Uno tray on top. **Nothing may be mounted within 34 mm above the
   Uno tray** — the Inland shield stacks 30 mm and needs finger room above that.
6. Probe frame bolts to the front-edge flange holes; its throat drops through
   the slot in the deck's front edge.
7. Turret base at the rear, yoke on the pan horn, cradle between the uprights.

## Still open

- **Row / pot spacing.** Drives the 196 mm overall width.
- **Motor wiring:** four motors paired onto shield channels A and B, or servos
  moved to a PCA9685 on the Pi so all four channels stay free. This does not
  change any printed part, but it changes what goes on the deck.
- **Wheel choice.** Modelled at the standard 65 × 26 mm TT wheel. A different
  diameter moves the deck height and breaks alignment with the probe frame.

## QC performed

All ten parts watertight, winding-consistent, single-solid, and inside the
Neptune 4 envelope printed flat. Two defects were caught by rendering and fixed:
the turret yoke was two disconnected lumps because the tilt servo pocket cut
clean through the upright, and the original yoke geometry was narrower than the
camera it was supposed to hold.
