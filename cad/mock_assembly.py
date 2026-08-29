"""Assemble the surviving chassis STLs + clearly-marked mock placeholders into
a playable mock-up of the whole rover.

NOT engineering geometry. The 9 printed parts are the real verified STLs,
placed per the deck's own bolt patterns. Everything orange is a placeholder
(the probe module CAD is lost; wheels/motors/boards/camera are bought parts).

Known, deliberate visual truths (see STATUS.md):
- Wheels sit at the designed track 170 (X=+/-85) and CLIP the 200-wide deck
  corners — that is a real defect in the deck feature layout, shown, not hidden.
- Deck bottom placed at Z=45 so the gearboxes fit under it (the code's DECK_Z
  formula); the README's "top face at Z=45" is inconsistent with that by 5 mm.

Outputs: render/rover_mock.glb + render/rover_mock_parts.json (for the viewer).

Run with a Python that has trimesh + numpy.
"""

import base64
import json
from pathlib import Path

import numpy as np
import trimesh
from trimesh.creation import box as Box, cylinder as Cyl
from trimesh.transformations import rotation_matrix

HERE = Path(__file__).parent
STL = HERE / "chassis" / "stl"
OUT = HERE / "render"

DECK_BOT = 45.0          # gearbox top 44 + 1 clearance (chassis_module DECK_Z)
AXLE_Z = 32.5
PARTS = []               # (name, mesh, hex_color, kind)  kind: real|mock|part

C_PRINT = "8a9bb8"       # printed PETG (real STLs)
C_MOCK = "e08a3c"        # placeholder geometry
C_BOARD = "3f7d4e"
C_SHIELD = "b03a3a"
C_DARK = "3a3d45"
C_TIRE = "26282e"
C_PACK = "2f5f9e"


def add(name, mesh, color, kind="mock"):
    PARTS.append((name, mesh, color, kind))


def stl(name, dx=0, dy=0, dz=0, color=C_PRINT):
    m = trimesh.load(STL / f"{name}.stl")
    m.apply_translation((dx, dy, dz))
    return m


def bx(sx, sy, sz, cx, cy, cz):
    m = Box(extents=(sx, sy, sz))
    m.apply_translation((cx, cy, cz))
    return m


def cyl_x(r, h, cx, cy, cz, sections=48):
    m = Cyl(radius=r, height=h, sections=sections)
    m.apply_transform(rotation_matrix(np.pi / 2, (0, 1, 0)))
    m.apply_translation((cx, cy, cz))
    return m


# ---- real printed parts, placed on the deck's own bolt patterns -------------
add("deck", stl("01_deck", 0, 0, DECK_BOT), C_PRINT, "real")
for sx in (-1, 1):
    for sy in (-1, 1):
        tag = f"{'L' if sx < 0 else 'R'}{'F' if sy > 0 else 'R'}"
        add(f"motor clamp {tag}", stl("02_motor_clamp", sx * 56, sy * 62, 3.0),
            C_PRINT, "real")
add("pi tray", stl("04_pi_tray", -20, 0, DECK_BOT + 5), C_PRINT, "real")
add("uno tray", stl("05_uno_tray", 66, 0, DECK_BOT + 5), C_PRINT, "real")
add("powerbank sling", stl("06_powerbank_sling", -20, 0, 24.5), C_PRINT, "real")
add("turret base", stl("08_turret_base", 0, -38, DECK_BOT + 5), C_PRINT, "real")
add("turret yoke", stl("09_turret_yoke", 0, -38, DECK_BOT + 5 + 50.9), C_PRINT, "real")
add("camera cradle", stl("10_cam_cradle", 0, -38, DECK_BOT + 5 + 50.9 + 34 - 30),
    C_PRINT, "real")
# spare parts parked beside the rover
add("lipo cradle (spare)", stl("07_lipo_cradle", 150, 25, 0), C_PRINT, "real")
add("motor gauge (spare)", stl("03_motor_gauge", 150, -35, 0), C_PRINT, "real")
add("lipo pack (on cradle)", bx(105, 34, 24, 150, 25, 3 + 12), C_PACK)

# ---- mock drivetrain --------------------------------------------------------
for sx in (-1, 1):
    for sy in (-1, 1):
        tag = f"{'L' if sx < 0 else 'R'}{'F' if sy > 0 else 'R'}"
        add(f"TT motor {tag} (mock)",
            bx(22.5, 70, 37, sx * 56, sy * 62 - sy * 10, 7 + 18.5), C_MOCK)
        add(f"axle {tag} (mock)",
            cyl_x(2.5, 30, sx * 70, sy * 62, AXLE_Z, 16), C_DARK)
        wheel = cyl_x(32.5, 26, sx * 85, sy * 62, AXLE_Z)
        add(f"wheel {tag} (mock)", wheel, C_TIRE)
        add(f"hub {tag} (mock)", cyl_x(12, 28, sx * 85, sy * 62, AXLE_Z, 24), C_MOCK)

# ---- mock electronics -------------------------------------------------------
add("Pi 4B (mock)", bx(85, 56, 1.6, -20, 0, DECK_BOT + 11 + 0.8), C_BOARD)
add("Pi ports (mock)", bx(20, 52, 12, -20 + 36, 0, DECK_BOT + 12 + 6), C_DARK)
add("Uno R3 (mock)", bx(68.6, 53.4, 1.6, 66, 0, DECK_BOT + 11 + 0.8), C_BOARD)
add("L298P shield (mock)", bx(65, 50, 28, 66, 0, DECK_BOT + 13 + 14), C_SHIELD)
add("power bank (mock)", bx(148.6, 68.3, 17.5, -20, 0, 27.5 + 8.75), C_DARK)

# ---- mock turret payload ----------------------------------------------------
TUR_Y, TILT_Z = -38.0, DECK_BOT + 5 + 50.9 + 34    # tilt axis height
add("C920 camera (mock)", bx(94, 25, 29, 0, TUR_Y, TILT_Z - 3), C_DARK)
lens = Cyl(radius=9, height=6, sections=32)
lens.apply_transform(rotation_matrix(np.pi / 2, (1, 0, 0)))
lens.apply_translation((0, TUR_Y - 15, TILT_Z - 3))
add("C920 lens (mock)", lens, "17181c")
add("tilt servo (mock)", bx(30, 40.7, 19.7, 50, TUR_Y, TILT_Z), C_DARK)

# ---- mock probe module (the LOST subsystem — placeholder only) --------------
PY = 60.0   # probe station, front notch center
add("probe frame (MOCK, CAD lost)", bx(30, 16, 120, 0, PY, 20 + 60), C_MOCK)
add("probe throat (MOCK)", bx(16, 10, 10, 0, PY + 4, 12 + 5), C_MOCK)
add("probe flange (MOCK)", bx(48, 22, 4, 0, PY - 2, DECK_BOT + 5 + 2), C_MOCK)
add("probe carriage (MOCK)", bx(24, 8, 60, 0, PY + 12, 60 + 30), C_MOCK)
add("probe rack (MOCK)", bx(8, 5, 70, 0, PY + 18.5, 55 + 35), C_MOCK)
add("probe pinion (MOCK)", cyl_x(18, 12, 6, PY + 26, 100, 36), C_MOCK)
add("probe servo (MOCK)", bx(40.7, 19.7, 42.9, 32, PY + 26, 100), C_DARK)
add("soil sensor blade (mock)", bx(13.97, 2.5, 56.7, 0, PY + 17, 12 + 28.3), C_BOARD)
add("soil sensor head (mock)", bx(16, 7, 19.5, 0, PY + 17, 68.7 + 9.7), C_BOARD)

# ---- export -----------------------------------------------------------------
OUT.mkdir(exist_ok=True)
scene = trimesh.Scene()
parts_json = []
for name, mesh, color, kind in PARTS:
    rgba = [int(color[i:i + 2], 16) for i in (0, 2, 4)] + [255]
    mesh.visual.face_colors = rgba
    scene.add_geometry(mesh, node_name=name, geom_name=name)
    tris = mesh.triangles.astype(np.float32)  # (n, 3, 3) — flat, no index needed
    parts_json.append({
        "name": name, "color": "#" + color, "kind": kind,
        "pos": base64.b64encode(tris.tobytes()).decode(),
    })

scene.export(OUT / "rover_mock.glb")
(OUT / "rover_mock_parts.json").write_text(json.dumps(parts_json))
total = sum(len(m.faces) for _, m, _, _ in PARTS)
print(f"{len(PARTS)} parts, {total} triangles")
print(f"glb  {(OUT/'rover_mock.glb').stat().st_size/1e6:.1f} MB")
print(f"json {(OUT/'rover_mock_parts.json').stat().st_size/1e6:.1f} MB")
