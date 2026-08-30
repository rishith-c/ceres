#!/usr/bin/env python3
"""Leaf turret-tracking — ALL processing on the Mac, rover just obeys.

Reads Ceres's live camera stream (Pi :8081/stream), finds the largest
leaf-green region, and steers the turret to keep it centered: smooth tilt
steps vertically, coarse pan nudges horizontally (the pan servo is a
continuous type — nudges are all it has). Shows a window with the tracking
overlay; press q to quit.

    python3 mac_tools/track_leaf.py [pi-address] [--flip-pan]

--flip-pan reverses the left/right nudges if the camera view moves the
wrong way (pan direction on the physical turret is unverified).
"""

import sys
import time
import urllib.request

import cv2
import numpy as np

PI = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "10.59.112.136"
FLIP_PAN = "--flip-pan" in sys.argv
BASE = f"http://{PI}:8081"

TILT_DEADBAND = 0.10     # fraction of frame height
PAN_DEADBAND = 0.22      # fraction of frame width
TILT_PERIOD = 0.35       # s between 2-deg tilt steps
PAN_COOLDOWN = 1.4       # s after each 300 ms nudge
MIN_AREA_FRAC = 0.02     # leaf must fill >=2% of the frame


def cmd(c):
    try:
        urllib.request.urlopen(f"{BASE}/cmd?c={c}", timeout=2).read()
    except Exception:
        pass


def find_leaf(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (25, 60, 40), (95, 255, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea)
    if cv2.contourArea(c) < MIN_AREA_FRAC * frame.shape[0] * frame.shape[1]:
        return None
    x, y, w, h = cv2.boundingRect(c)
    return (x, y, w, h)


def main():
    cap = cv2.VideoCapture(f"{BASE}/stream")
    if not cap.isOpened():
        print(f"cannot open {BASE}/stream — is the rover GUI service up?")
        return
    print(f"tracking from {BASE} — hold a leaf in front of Ceres. q quits.")
    last_tilt = last_pan = 0.0
    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.2)
            continue
        H, W = frame.shape[:2]
        box = find_leaf(frame)
        now = time.time()
        status = "no leaf"
        if box:
            x, y, w, h = box
            cx, cy = x + w / 2, y + h / 2
            ex, ey = (cx - W / 2) / W, (cy - H / 2) / H
            status = f"leaf  ex={ex:+.2f} ey={ey:+.2f}"
            if abs(ey) > TILT_DEADBAND and now - last_tilt > TILT_PERIOD:
                cmd("tiltup" if ey < 0 else "tiltdown")   # leaf high -> look up
                last_tilt = now
            if abs(ex) > PAN_DEADBAND and now - last_pan > PAN_COOLDOWN:
                left = ex < 0
                if FLIP_PAN:
                    left = not left
                cmd("panl" if left else "panr")
                last_pan = now
            cv2.rectangle(frame, (x, y), (x + w, y + h), (47, 143, 107), 3)
            cv2.circle(frame, (int(cx), int(cy)), 6, (36, 38, 186), -1)
        cv2.drawMarker(frame, (W // 2, H // 2), (26, 28, 31),
                       cv2.MARKER_CROSS, 30, 2)
        cv2.putText(frame, status, (14, 30), cv2.FONT_HERSHEY_SIMPLEX,
                    0.8, (26, 28, 31), 2)
        cv2.imshow("Ceres leaf tracking (q quits)", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
