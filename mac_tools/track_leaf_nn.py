#!/usr/bin/env python3
"""Neural leaf/plant turret-tracking — prebuilt YOLOv5-nano via OpenCV DNN.

All inference on the Mac. Detects COCO's "potted plant" class in Ceres's
live stream and steers the turret to center the best detection; if the
network sees no plant, falls back to the green-region tracker so a bare
leaf in your hand still works. Overlay window shows what it believes.

    python3 mac_tools/track_leaf_nn.py [pi-address] [--flip-pan]
"""

import sys
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from track_leaf import find_leaf  # green fallback

PI = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "10.59.112.136"
FLIP_PAN = "--flip-pan" in sys.argv
BASE = f"http://{PI}:8081"
MODEL = Path(__file__).parent / "models" / "yolov5n.onnx"
PLANT_CLASS = 58            # COCO "potted plant"
CONF = 0.35
SIZE = 640

TILT_DEADBAND, PAN_DEADBAND = 0.10, 0.22
TILT_PERIOD, PAN_COOLDOWN = 0.35, 1.4


def cmd(c):
    try:
        urllib.request.urlopen(f"{BASE}/cmd?c={c}", timeout=2).read()
    except Exception:
        pass


def detect_plant(net, frame):
    """Best potted-plant box from YOLOv5n, or None."""
    H, W = frame.shape[:2]
    s = max(H, W)
    padded = np.zeros((s, s, 3), np.uint8)
    padded[:H, :W] = frame
    blob = cv2.dnn.blobFromImage(padded, 1 / 255.0, (SIZE, SIZE), swapRB=True)
    net.setInput(blob)
    out = net.forward()[0]          # (25200, 85)
    scale = s / SIZE
    best, best_score = None, 0.0
    for row in out:
        obj = row[4]
        if obj < CONF:
            continue
        cls_scores = row[5:]
        cls = int(np.argmax(cls_scores))
        score = obj * cls_scores[cls]
        if cls != PLANT_CLASS or score < CONF:
            continue
        if score > best_score:
            cx, cy, w, h = row[:4] * scale
            best = (int(cx - w / 2), int(cy - h / 2), int(w), int(h))
            best_score = score
    return best, best_score


def main():
    net = cv2.dnn.readNetFromONNX(str(MODEL))
    cap = cv2.VideoCapture(f"{BASE}/stream")
    if not cap.isOpened():
        print(f"cannot open {BASE}/stream")
        return
    print(f"neural tracking from {BASE} — show Ceres a plant. q quits.")
    last_tilt = last_pan = 0.0
    flip = FLIP_PAN
    pan_probe = None      # (ex_before, direction) — auto-learns pan polarity
    wrong_count = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.2)
            continue
        H, W = frame.shape[:2]
        box, score = detect_plant(net, frame)
        label = f"plant {score:.2f}" if box else ""
        if box is None:
            g = find_leaf(frame)
            if g:
                box, label = g, "green region (fallback)"
        now = time.time()
        if box:
            x, y, w, h = box
            cx, cy = x + w / 2, y + h / 2
            ex, ey = (cx - W / 2) / W, (cy - H / 2) / H
            if abs(ey) > TILT_DEADBAND and now - last_tilt > TILT_PERIOD:
                cmd("tiltup" if ey < 0 else "tiltdown")
                last_tilt = now
            if pan_probe and now - last_pan > 1.0:
                ex0, went_left = pan_probe
                # if we nudged toward the leaf but the error grew, polarity is wrong
                if abs(ex) > abs(ex0) + 0.03:
                    wrong_count += 1
                    if wrong_count >= 2:
                        flip = not flip
                        wrong_count = 0
                        print("pan polarity auto-flipped")
                else:
                    wrong_count = 0
                pan_probe = None
            if abs(ex) > PAN_DEADBAND and now - last_pan > PAN_COOLDOWN:
                left = ex < 0
                if flip:
                    left = not left
                cmd("panl" if left else "panr")
                pan_probe = (ex, left)
                last_pan = now
            cv2.rectangle(frame, (x, y), (x + w, y + h), (47, 143, 107), 3)
            cv2.putText(frame, label, (x, max(24, y - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (47, 143, 107), 2)
        cv2.drawMarker(frame, (W // 2, H // 2), (26, 28, 31),
                       cv2.MARKER_CROSS, 30, 2)
        cv2.imshow("Ceres neural tracking (q quits)", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
