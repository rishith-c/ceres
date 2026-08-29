"""
Field Triage Rover - chassis, mounts and 2-DOF turret.  v1

Same coordinate convention as probe_module.py:
    Z up, Z=0 = ground.  +Y = forward.  X = across the rover.

Sources for every dimension:
  Pi 4B          85.0 x 56.0, M2.5 on a 58 x 49 rectangle, 3.5 mm inset  (RPi mech drawing)
  Uno R3         68.6 x 53.4, 4 holes at the standard Arduino coordinates
  Inland shield  65 x 50 x 30 stacked, 3x M3 fixing holes                 (Micro Center)
  Power bank     148.59 x 68.33 x 17.53                                   (Micro Center listing)
  TT gearmotor   70 x 37 x 22.5, dual shaft                               (vendor spec)
  TT wheel       65 dia x 26 wide                                         (standard TT wheel)
  MG996R         40.7 x 19.7 x 42.9, tabs 53.6 span / 49.5 pitch          (TowerPro)
  C920           1/4"-20 UNC tripod socket on the clip                    (Logitech)

DELIBERATE DESIGN CHOICE: nothing here depends on the TT motor's moulded hole
pattern or on the LiPo's case size. Both vary between vendors and I have not
measured either, so the motor mount is a friction clamp on the gearbox body and
the battery cradle is a strap tray. Both come with a gauge coupon to verify the
fit before committing to four copies.
"""
import math
import cadquery as cq

# ---------------------------------------------------------------- tolerances
FIT, HOLE_COMP = 0.35, 0.20
M3_CLEAR = 3.4 + HOLE_COMP
M3_TAP   = 2.6
M25_TAP  = 2.2
M25_CLR  = 2.7 + HOLE_COMP
WALL     = 2.4
EPS      = 0.01

# ---------------------------------------------------------------- components
PI_L, PI_W          = 85.0, 56.0
PI_HX, PI_HY        = 58.0, 49.0
PI_INSET            = 3.5
UNO_L, UNO_W        = 68.6, 53.4
UNO_HOLES = [(14.0, 2.5), (15.3, 50.8), (66.1, 35.6), (66.1, 7.6)]  # from board origin
SHIELD_H            = 30.0
PB_L, PB_W, PB_H    = 148.59, 68.33, 17.53
TT_L, TT_H, TT_W    = 70.0, 37.0, 22.5
TT_SHAFT_FROM_TOP   = 11.5     # shaft axis below the gearbox top face
WHEEL_D, WHEEL_W    = 65.0, 26.0
SV_L, SV_W, SV_H    = 40.7, 19.7, 42.9
SV_TAB_SPAN, SV_HOLE_PITCH = 53.6, 49.5

# ---------------------------------------------------------------- chassis
DECK_L, DECK_W, DECK_T = 200.0, 140.0, 5.0
WHEELBASE  = 124.0
AXLE_Z     = WHEEL_D / 2.0                 # 32.5
DECK_Z     = AXLE_Z + TT_SHAFT_FROM_TOP + 1.0   # 45.0 - matches probe_module.DECK_Z
TRACK      = DECK_W + 2 * (WHEEL_W / 2 + 2.0)   # wheels just outboard of the deck

CLAMP_T    = 4.0                 # clamp wall thickness around the gearbox
CLAMP_LEN  = 34.0                # how much of the gearbox the clamp grips


# ================================================================ helpers
def m3_holes(wp, pts, depth=30.0, dia=M3_CLEAR):
    for (x, y) in pts:
        wp = wp.cut(cq.Workplane("XY").center(x, y).circle(dia / 2)
                    .extrude(depth).translate((0, 0, -depth / 2)))
    return wp


def strap_slots(solid, cx, cy, span, w=4.0, h=14.0, t=40.0):
    """Pair of through-slots for a velcro strap."""
    for sx in (-1, 1):
        solid = solid.cut(cq.Workplane("XY")
                          .center(cx + sx * span / 2, cy)
                          .slot2D(h, w, 90).extrude(t).translate((0, 0, -t / 2)))
    return solid


# ================================================================ parts
def make_deck():
    """Main chassis plate. PRINT FLAT. 200 x 140 fits the Neptune 4 bed with
    12 mm to spare on each side.

    Everything bolts to this: four motor clamps underneath, the Pi and Uno
    trays on top, the power bank sling underneath, the probe frame at the front
    edge, and the turret at the rear."""
    d = cq.Workplane("XY").box(DECK_L, DECK_W, DECK_T, centered=(True, True, False))

    # stiffening ribs on the underside - a bare 5 mm printed plate this size
    # will bow under the battery mass
    for yy in (-42.0, 0.0, 42.0):
        d = d.union(cq.Workplane("XY")
                    .box(DECK_L - 8.0, 4.0, 6.0, centered=(True, True, False))
                    .translate((0, yy, -6.0)))
    for xx in (-60.0, 0.0, 60.0):
        d = d.union(cq.Workplane("XY")
                    .box(4.0, DECK_W - 8.0, 6.0, centered=(True, True, False))
                    .translate((xx, 0, -6.0)))

    # motor clamp bolt pattern, four corners
    mp = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx = sx * (DECK_W / 2 - 14.0)
            cy = sy * WHEELBASE / 2
            mp += [(cx, cy - 12.0), (cx, cy + 12.0)]
    d = m3_holes(d, mp)

    # Pi tray + Uno tray bolt patterns
    d = m3_holes(d, [(-52.0, 34.0), (-52.0, -34.0), (12.0, 34.0), (12.0, -34.0)])
    d = m3_holes(d, [(46.0, 30.0), (46.0, -30.0), (86.0, 30.0), (86.0, -30.0)])

    # power bank sling underneath
    d = m3_holes(d, [(-80.0, 0.0), (-20.0, 0.0), (40.0, 0.0)])
    d = strap_slots(d, -30.0, 0.0, 110.0)

    # probe frame flange, front edge (matches probe_module deck flange)
    d = m3_holes(d, [(-13.575 - 6.5, DECK_W / 2 - 12.0),
                     (13.575 + 6.5, DECK_W / 2 - 12.0)])
    # slot the front edge so the probe throat can hang below the deck
    d = d.cut(cq.Workplane("XY")
              .box(34.0, 30.0, 20.0, centered=(True, False, True))
              .translate((0, DECK_W / 2 - 24.0, 0)))

    # turret base bolt pattern, rear
    d = m3_holes(d, [(-22.0, -DECK_W / 2 + 18.0), (22.0, -DECK_W / 2 + 18.0),
                     (-22.0, -DECK_W / 2 + 46.0), (22.0, -DECK_W / 2 + 46.0)])

    # cable pass-throughs
    for (cx, cy) in [(-95.0, 0.0), (0.0, 52.0), (0.0, -52.0), (95.0, 0.0)]:
        d = d.cut(cq.Workplane("XY").center(cx, cy).slot2D(26.0, 9.0,
                  0 if abs(cy) > 10 else 90).extrude(20.0).translate((0, 0, -5.0)))
    return d


def make_motor_clamp():
    """TT gearmotor clamp. Grips the moulded gearbox body - deliberately does
    NOT use the motor's own screw holes, whose spacing varies between vendors
    and which I have not measured.

    PRINT with the open mouth facing up, no supports. Two M3 bolts pull the
    jaws together; two more bolt it to the deck."""
    W = TT_W + 2 * CLAMP_T + FIT
    H = TT_H + CLAMP_T + FIT
    c = cq.Workplane("XY").box(W, CLAMP_LEN, H, centered=(True, True, False))

    # gearbox cavity, open at the top
    c = c.cut(cq.Workplane("XY")
              .box(TT_W + FIT, CLAMP_LEN + 2, TT_H + FIT,
                   centered=(True, True, False))
              .translate((0, 0, CLAMP_T)))
    # split the jaws so the clamp can actually close on the body
    c = c.cut(cq.Workplane("XY")
              .box(1.6, CLAMP_LEN + 2, H - CLAMP_T - 6.0, centered=(True, True, False))
              .translate((0, 0, H - (H - CLAMP_T - 6.0))))

    # clamping bolts, through both jaws
    for yy in (-10.0, 10.0):
        c = c.cut(cq.Workplane("YZ").center(yy, H - 7.0)
                  .circle(M3_CLEAR / 2).extrude(W + 4).translate((-W / 2 - 2, 0, 0)))
        # captive nut pocket on one jaw
        c = c.cut(cq.Workplane("YZ").center(yy, H - 7.0)
                  .polygon(6, 6.4).extrude(3.2).translate((W / 2 - 3.2, 0, 0)))

    # deck bolts
    for yy in (-12.0, 12.0):
        c = c.cut(cq.Workplane("XY").center(0, yy).circle(M3_CLEAR / 2)
                  .extrude(CLAMP_T + 2).translate((0, 0, -1.0)))
    # shaft relief so the clamp never touches the output shaft
    c = c.cut(cq.Workplane("XZ").center(0, H - TT_SHAFT_FROM_TOP - CLAMP_T)
              .circle(4.0).extrude(-(CLAMP_LEN + 4)).translate((0, CLAMP_LEN / 2 + 2, 0)))
    return c


def make_motor_gauge():
    """5-minute coupon. Verifies the TT gearbox cross-section before you commit
    to four clamps. If the motor does not slide into this with light thumb
    pressure, measure it and tell me - do not force it."""
    g = cq.Workplane("XY").box(TT_W + 2 * CLAMP_T + FIT, 12.0, TT_H + CLAMP_T + FIT,
                               centered=(True, True, False))
    g = g.cut(cq.Workplane("XY")
              .box(TT_W + FIT, 20.0, TT_H + FIT, centered=(True, True, False))
              .translate((0, 0, CLAMP_T)))
    return g


def make_pi_tray():
    """Raspberry Pi 4B tray. M2.5 self-tapping bosses on the 58 x 49 pattern,
    6 mm tall so the board clears the deck bolt heads. PRINT FLAT."""
    L, W = PI_L + 10.0, PI_W + 10.0
    t = cq.Workplane("XY").box(L, W, 3.0, centered=(True, True, False))
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * PI_HX / 2, sy * PI_HY / 2
            t = t.union(cq.Workplane("XY").center(x, y).circle(3.2)
                        .extrude(6.0).translate((0, 0, 3.0)))
            t = t.cut(cq.Workplane("XY").center(x, y).circle(M25_TAP / 2)
                      .extrude(8.0).translate((0, 0, 2.0)))
    # deck bolts - matches the deck pattern (64 x 68 rectangle)
    for sx in (-1, 1):
        for sy in (-1, 1):
            t = m3_holes(t, [(sx * 32.0, sy * 34.0)], depth=10.0)
    # airflow / weight relief under the board
    t = t.cut(cq.Workplane("XY").rect(46.0, 30.0).extrude(10.0).translate((0, 0, -1)))
    return t


def make_uno_tray():
    """Arduino Uno R3 tray, on the standard Arduino hole pattern.
    The Inland shield stacks 30 mm above the Uno PCB, so nothing may be mounted
    within 34 mm above this tray. PRINT FLAT."""
    L, W = UNO_L + 12.0, UNO_W + 12.0
    t = cq.Workplane("XY").box(L, W, 3.0, centered=(True, True, False))
    for (hx, hy) in UNO_HOLES:
        x, y = hx - UNO_L / 2, hy - UNO_W / 2
        t = t.union(cq.Workplane("XY").center(x, y).circle(3.3)
                    .extrude(6.0).translate((0, 0, 3.0)))
        t = t.cut(cq.Workplane("XY").center(x, y).circle(M25_TAP / 2)
                  .extrude(8.0).translate((0, 0, 2.0)))
    for sx in (-1, 1):
        for sy in (-1, 1):
            t = m3_holes(t, [(sx * 20.0, sy * 30.0)], depth=10.0)
    # USB-B and barrel-jack end left completely open: the Uno's USB-B shell
    # projects ~2 mm past the PCB edge and the cable needs 40 mm of straight run
    t = t.cut(cq.Workplane("XY")
              .box(16.0, 34.0, 12.0, centered=(True, True, False))
              .translate((-L / 2 + 6.0, 4.0, -1.0)))
    return t


def make_powerbank_sling():
    """Under-deck cradle for the Energizer 10,000 mAh pack (148.59 x 68.33 x
    17.53). Strap-retained, so a swollen or swapped pack still fits.
    PRINT FLAT."""
    L, W = PB_L + 8.0, PB_W + 8.0
    s = cq.Workplane("XY").box(L, W, 3.0, centered=(True, True, False))
    for sx in (-1, 1):
        s = s.union(cq.Workplane("XY")
                    .box(3.0, W, 10.0, centered=(True, True, False))
                    .translate((sx * (L / 2 - 1.5), 0, 3.0)))
    for sy in (-1, 1):
        s = s.union(cq.Workplane("XY")
                    .box(L, 3.0, 10.0, centered=(True, True, False))
                    .translate((0, sy * (W / 2 - 1.5), 3.0)))
    s = m3_holes(s, [(-60.0, 0.0), (0.0, 0.0), (60.0, 0.0)], depth=10.0)
    s = strap_slots(s, 0.0, 0.0, 100.0, w=4.0, h=16.0, t=10.0)
    # weight relief
    for xx in (-45.0, 0.0, 45.0):
        s = s.cut(cq.Workplane("XY").center(xx, 0).rect(30.0, 38.0).extrude(10.0)
                  .translate((0, 0, -1.0)))
    return s


def make_lipo_cradle():
    """11.1 V 3S pack cradle. Adjustable: the pack is retained by two straps
    against a floor with raised end stops, so it fits any 3S brick from roughly
    95 x 30 x 20 up to 115 x 40 x 28. The gel-blaster pack has not been
    measured, so nothing here is toleranced to it. PRINT FLAT."""
    L, W = 122.0, 46.0
    c = cq.Workplane("XY").box(L, W, 3.0, centered=(True, True, False))
    for sx in (-1, 1):
        c = c.union(cq.Workplane("XY").box(4.0, W, 16.0, centered=(True, True, False))
                    .translate((sx * (L / 2 - 2.0), 0, 3.0)))
    c = strap_slots(c, 0.0, 0.0, 74.0, w=4.5, h=18.0, t=10.0)
    c = m3_holes(c, [(-46.0, 16.0), (46.0, 16.0), (-46.0, -16.0), (46.0, -16.0)],
                 depth=10.0)
    c = c.cut(cq.Workplane("XY").rect(56.0, 24.0).extrude(10.0).translate((0, 0, -1.0)))
    return c


def make_turret_base():
    """Pan stage. Holds the pan MG996R vertically so its output shaft points up.
    PRINT with the open face up, no supports.

    The pan servo is the one that carries the whole camera mass as a bending
    load on its output shaft, so the yoke rides on a printed thrust collar that
    takes the moment instead of the spline."""
    L, W, H = 52.0, 40.0, SV_H + 8.0
    b = cq.Workplane("XY").box(L, W, H, centered=(True, True, False))
    # servo pocket, shaft end up
    b = b.cut(cq.Workplane("XY").box(SV_L + 0.8, SV_W + 0.8, SV_H + 2,
                                     centered=(True, True, False))
              .translate((0, 0, 6.0)))
    # tab slots
    for sx in (-1, 1):
        b = b.cut(cq.Workplane("XY")
                  .center(sx * SV_HOLE_PITCH / 2, 0)
                  .slot2D(6.0 + M3_CLEAR, M3_CLEAR, 90).extrude(30.0)
                  .translate((0, 0, H - 12.0)))
    # thrust collar bore: the yoke's boss rides here so the servo spline
    # carries torque only, never the camera's overturning moment
    b = b.cut(cq.Workplane("XY").circle(15.0).extrude(4.0).translate((0, 0, H - 4.0)))
    # deck bolts
    b = m3_holes(b, [(-22.0, 14.0), (22.0, 14.0), (-22.0, -14.0), (22.0, -14.0)],
                 depth=12.0)
    # wire exit
    b = b.cut(cq.Workplane("XY").center(0, -W / 2 + 3.0).slot2D(16.0, 7.0, 0)
              .extrude(12.0).translate((0, 0, 2.0)))
    return b


def make_turret_yoke():
    """Tilt stage. Bolts to the pan servo horn and carries the tilt MG996R.

    The uprights sit OUTBOARD of the camera (X = +/-40) because the C920 is
    ~94 mm wide - an inboard yoke would have to be narrower than the camera it
    holds. The tilt servo bolts to the outer face of the +X upright with its
    long axis horizontal, so its 53.6 mm tab span fits in the upright's 60 mm
    width instead of forcing a 66 mm tall post.

    PRINT FLAT, base down. No supports."""
    BX, BY, BT = 88.0, 40.0, 4.0
    UX, UY, UZ = 4.0, 60.0, 52.0
    TILT_Z = 34.0

    y = cq.Workplane("XY").box(BX, BY, BT, centered=(True, True, False))
    # thrust collar that rides in the turret base bore - the pan servo spline
    # then sees torque only, never the camera's overturning moment
    y = y.union(cq.Workplane("XY").circle(14.6).extrude(3.8).translate((0, 0, -3.8)))
    # horn pocket, same universal slot interface as the probe pinion
    y = y.cut(cq.Workplane("XY").circle(12.0).extrude(3.4).translate((0, 0, 0.6)))
    y = y.cut(cq.Workplane("XY").circle(4.5).extrude(12.0).translate((0, 0, -6.0)))
    for k in range(4):
        a = 90.0 * k
        y = y.cut(cq.Workplane("XY")
                  .center(8.0 * math.cos(math.radians(a)), 8.0 * math.sin(math.radians(a)))
                  .slot2D(6.0 + 2.4, 2.4, a).extrude(12.0).translate((0, 0, -6.0)))

    for sx in (-1, 1):
        y = y.union(cq.Workplane("XY").box(UX, UY, UZ, centered=(True, True, False))
                    .translate((sx * (BX / 2 - UX / 2), 0, 0.0)))
        # gusset so the upright is not a bare cantilever off a 4 mm plate
        y = y.union(cq.Workplane("YZ")
                    .polyline([(0, BT), (0, BT + 16.0), (16.0, BT)]).close()
                    .extrude(UX).translate((sx * (BX / 2 - UX) - (UX if sx < 0 else 0), 0, 0)))

    # +X upright: tilt servo shaft clearance + tab holes (servo hangs outboard)
    y = y.cut(cq.Workplane("YZ").center(0, TILT_Z).circle(5.5)
              .extrude(10.0).translate((BX / 2 - UX - 1, 0, 0)))
    for sy in (-1, 1):
        y = y.cut(cq.Workplane("YZ").center(sy * SV_HOLE_PITCH / 2, TILT_Z)
                  .circle(M3_CLEAR / 2).extrude(10.0)
                  .translate((BX / 2 - UX - 1, 0, 0)))
    # -X upright: M6 idler pivot
    y = y.cut(cq.Workplane("YZ").center(0, TILT_Z).circle(3.15)
              .extrude(10.0).translate((-BX / 2 - 1, 0, 0)))
    return y


def make_cam_cradle():
    """C920 cradle. Mounts through the webcam's own 1/4"-20 tripod socket - the
    only dimensionally guaranteed interface on that camera - so nothing depends
    on the clip's moulded shape, which differs between C920 revisions.

    An anti-rotation pad stops the camera pivoting about the single screw.
    PRINT FLAT, cradle face down. No supports."""
    PL, PW, PT = 74.0, 30.0, 4.0
    ARM_X, ARM_T = 37.0, 4.0
    TILT_Z = 34.0 - 4.0          # relative to the cradle's own base

    c = cq.Workplane("XY").box(PL, PW, PT, centered=(True, True, False))
    # 1/4-20 clearance + captive nut pocket underneath
    c = c.cut(cq.Workplane("XY").circle(6.8 / 2).extrude(12.0).translate((0, 0, -1.0)))
    c = c.cut(cq.Workplane("XY").polygon(6, 12.4).extrude(3.2).translate((0, 0, -0.6)))
    # anti-rotation pad
    c = c.union(cq.Workplane("XY").box(34.0, 20.0, 2.0, centered=(True, True, False))
                .translate((0, 0, PT)))
    c = c.cut(cq.Workplane("XY").circle(6.8 / 2).extrude(12.0).translate((0, 0, -1.0)))

    for sx in (-1, 1):
        c = c.union(cq.Workplane("XY")
                    .box(ARM_T, PW, TILT_Z + 10.0, centered=(True, True, False))
                    .translate((sx * ARM_X, 0, 0.0)))
    # +X arm carries the tilt servo horn; -X arm rides the idler pivot
    c = c.cut(cq.Workplane("YZ").center(0, TILT_Z).circle(12.0)
              .extrude(3.4).translate((ARM_X - ARM_T / 2 - 3.4, 0, 0)))
    c = c.cut(cq.Workplane("YZ").center(0, TILT_Z).circle(4.5)
              .extrude(12.0).translate((ARM_X - 6.0, 0, 0)))
    for k in range(4):
        a = 90.0 * k
        c = c.cut(cq.Workplane("YZ")
                  .center(8.0 * math.cos(math.radians(a)),
                          TILT_Z + 8.0 * math.sin(math.radians(a)))
                  .slot2D(6.0 + 2.4, 2.4, a).extrude(12.0)
                  .translate((ARM_X - 6.0, 0, 0)))
    c = c.cut(cq.Workplane("YZ").center(0, TILT_Z).circle(3.15)
              .extrude(12.0).translate((-ARM_X - 6.0, 0, 0)))
    return c
