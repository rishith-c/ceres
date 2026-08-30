#!/usr/bin/env python3
"""Rover remote control — served by the Pi, driven from any browser or phone.

    python3 drive_gui.py [port]     # default 8081

One page: live C920 feed + hold-to-drive pad + probe/tilt/pan controls +
live status. Every command goes through rover.py and therefore through the
firmware's safety net (timed bursts, watchdog, fences, interlocks) — holding
a drive button streams short bursts, so releasing (or losing WiFi) stops the
car within 600 ms no matter what.

Tolerates missing hardware: no Mega -> controls show "rover offline" and a
reconnect button; no camera -> feed shows a placeholder.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from rover import Rover, RoverError  # noqa: E402

BURST_MS = 600      # each held-button tick asks for this much motion
DRIVE_PWM = 140


# ---------------- camera thread: always hold the latest JPEG ----------------
class Cam:
    def __init__(self):
        self.frame = None
        self.ok = False
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        except Exception:
            return
        while True:
            okr, frm = cap.read()
            if okr:
                okj, buf = cv2.imencode(".jpg", frm,
                                        [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                if okj:
                    self.frame = buf.tobytes()
                    self.ok = True
            else:
                self.ok = False
                time.sleep(0.5)


# ---------------- rover link: one serial connection, one lock ----------------
class Link:
    def __init__(self):
        self.rover = None
        self.lock = threading.Lock()
        self.error = "not connected yet"
        self.connect()

    def connect(self):
        import glob as g
        with self.lock:
            if self.rover:
                try: self.rover.close()
                except Exception: pass
                self.rover = None
            ports = g.glob("/dev/ttyACM*") + g.glob("/dev/ttyUSB*")
            if not ports:
                self.error = "no Mega on USB"
                return False
            try:
                r = Rover(ports[0])
                r.connect()
                self.rover = r
                self.error = ""
                return True
            except RoverError as e:
                self.error = str(e)
                return False

    def do(self, fn):
        with self.lock:
            if not self.rover:
                raise RoverError(self.error or "rover offline")
            return fn(self.rover)


cam = Cam()
link = Link()

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>Rover Remote</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{--bg:#fff;--border:rgba(26,28,31,.117);--ink:#1A1C1F;--ink2:rgba(26,28,31,.62);
 --leaf:#6B8F2E;--leafw:#EFF4E2;--daisy:#E9C64A;--daisyw:#FBF3DA;--fail:#BA2623;
 --mono:"IBM Plex Mono",ui-monospace,monospace;
 --sh:0 0 0 .5px var(--border),0 3px 7.5px rgba(0,0,0,.04),0 0 20px rgba(0,0,0,.05)}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:var(--bg);color:var(--ink);
 font:14px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",sans-serif;padding:18px}
.wrap{max-width:900px;margin:0 auto}
h1{font:600 24px "Source Serif 4",Georgia,serif;margin:0 0 2px}
.status{font:500 12px var(--mono);color:var(--ink2);margin-bottom:14px;min-height:18px}
.status .on{color:var(--leaf)} .status .off{color:var(--fail)}
.cols{display:grid;grid-template-columns:1fr 300px;gap:16px}
@media(max-width:760px){.cols{grid-template-columns:1fr}}
.feed{border-radius:12px;overflow:hidden;box-shadow:var(--sh);background:#F3F3F3;
 aspect-ratio:16/9;display:flex;align-items:center;justify-content:center;color:var(--ink2)}
.feed img{width:100%;height:100%;object-fit:cover;display:block}
.panel{background:var(--bg);border-radius:12px;box-shadow:var(--sh);padding:14px}
.panel h2{font:500 10.5px var(--mono);letter-spacing:.1em;text-transform:uppercase;
 color:var(--ink2);margin:0 0 10px}
.pad{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:14px}
button{border:none;border-radius:10px;background:#F3F3F3;color:var(--ink);
 font:500 13px var(--mono);padding:16px 0;cursor:pointer;user-select:none;touch-action:none}
button:active{background:var(--daisyw);box-shadow:inset 0 0 0 1.5px var(--daisy)}
.stop{background:var(--fail);color:#fff;grid-column:2}
.row{display:flex;gap:8px;margin-bottom:8px}
.row button{flex:1;padding:12px 0}
.small{font-size:11.5px}
.reconnect{background:var(--leafw);color:var(--leaf)}
#estop{display:block;width:100%;background:var(--fail);color:#fff;font:600 15px var(--mono);
 letter-spacing:.06em;padding:14px 0;border-radius:12px;margin:0 0 14px;box-shadow:var(--sh)}
#estop:active{filter:brightness(.85)}
</style></head><body><div class="wrap">
<h1>Rover Remote</h1>
<div class="status" id="st">connecting…</div>
<button id="estop">■ STOP EVERYTHING</button>
<div class="cols">
 <div class="feed" id="feed"><span>camera warming up…</span></div>
 <div>
  <div class="panel">
   <h2>Drive — hold to move</h2>
   <div class="pad">
    <button data-hold="arcl">↖</button><button data-hold="fwd">▲</button><button data-hold="arcr">↗</button>
    <button data-hold="spinl">⟲</button><button class="stop" data-tap="stop">STOP</button><button data-hold="spinr">⟳</button>
    <button data-hold="rarcl">↙</button><button data-hold="rev">▼</button><button data-hold="rarcr">↘</button>
   </div>
   <h2>Camera — hold to aim</h2>
   <div class="row"><button data-rep="tiltup" data-ms="320" class="small">👀 look UP</button>
    <button data-rep="tiltdown" data-ms="320" class="small">👀 look DOWN</button></div>
   <div class="row"><button data-rep="panl" data-ms="700" class="small">↰ turn body LEFT</button>
    <button data-rep="panr" data-ms="700" class="small">↱ turn body RIGHT</button></div>
   <h2>Soil probe</h2>
   <div class="row"><button data-tap="probe0" class="small">⬆ probe UP (safe)</button>
    <button data-tap="probe50" class="small">probe half</button>
    <button data-tap="probe100" class="small">⬇ probe DOWN</button></div>
   <div class="row"><button data-tap="home" class="small">HOME</button>
    <button data-tap="reconnect" class="small reconnect">reconnect</button></div>
  </div>
 </div>
</div></div>
<script>
const st = document.getElementById("st");
async function cmd(c){ try{ const r = await fetch("/cmd?c="+c); return await r.json(); }catch(e){ return {err:"network"} } }
let holdTimer = null;
document.querySelectorAll("[data-hold]").forEach(b=>{
  const start = e=>{ e.preventDefault(); cmd(b.dataset.hold);
    holdTimer = setInterval(()=>cmd(b.dataset.hold), 300); };
  const end = ()=>{ if(holdTimer){ clearInterval(holdTimer); holdTimer=null; cmd("stop"); } };
  b.addEventListener("pointerdown", start);
  b.addEventListener("pointerup", end); b.addEventListener("pointerleave", end);
  b.addEventListener("pointercancel", end);
});
document.querySelectorAll("[data-tap]").forEach(b=>
  b.addEventListener("click", ()=>cmd(b.dataset.tap)));
let repTimer = null;
document.querySelectorAll("[data-rep]").forEach(b=>{
  const start = e=>{ e.preventDefault(); cmd(b.dataset.rep);
    repTimer = setInterval(()=>cmd(b.dataset.rep), +b.dataset.ms); };
  const end = ()=>{ if(repTimer){ clearInterval(repTimer); repTimer=null; } };
  b.addEventListener("pointerdown", start);
  b.addEventListener("pointerup", end); b.addEventListener("pointerleave", end);
  b.addEventListener("pointercancel", end);
});
const keys = {ArrowUp:"fwd",w:"fwd",ArrowDown:"rev",s:"rev",ArrowLeft:"spinl",a:"spinl",ArrowRight:"spinr",d:"spinr"};
let keyTimer=null, curKey=null;
addEventListener("keydown", e=>{ const c=keys[e.key]; if(!c||curKey===e.key) return;
  curKey=e.key; cmd(c); keyTimer=setInterval(()=>cmd(c),300); });
addEventListener("keyup", e=>{ if(keys[e.key]&&curKey===e.key){ clearInterval(keyTimer); curKey=null; cmd("stop"); }});
function killTimers(){ if(holdTimer){clearInterval(holdTimer);holdTimer=null}
  if(repTimer){clearInterval(repTimer);repTimer=null}
  if(keyTimer){clearInterval(keyTimer);keyTimer=null;curKey=null} }
document.getElementById("estop").addEventListener("click", async ()=>{
  killTimers(); await cmd("stop"); setTimeout(()=>cmd("stop"), 300);
  st.innerHTML = '<span class="off">ALL STOP sent</span>';
});
async function poll(){ const s = await cmd("status");
  st.innerHTML = s.err ? `<span class="off">rover offline</span> — ${s.err}`
    : `<span class="on">online</span> · ${s.drive} · probe ${s.probe}% · pan ${s.pan}° · tilt ${s.tilt}°`;
}
setInterval(poll, 1000); poll();
const img = new Image();
img.onload = ()=>{ const f=document.getElementById("feed"); f.innerHTML=""; f.appendChild(img); };
img.src = "/stream";
</script></body></html>"""


TILT = {"cur": 96}


def handle_cmd(c):
    if c == "reconnect":
        return {"ok": link.connect(), "err": link.error}
    if c == "status":
        try:
            s = link.do(lambda r: r.status())
            return {"drive": s.drive, "probe": s.probe, "pan": s.pan,
                    "tilt": s.tilt, "settled": s.settled}
        except RoverError as e:
            return {"err": str(e)}
    try:
        if c == "fwd":      link.do(lambda r: r.forward(BURST_MS, DRIVE_PWM))
        elif c == "arcl":   link.do(lambda r: r.arc(BURST_MS, DRIVE_PWM, "L"))
        elif c == "arcr":   link.do(lambda r: r.arc(BURST_MS, DRIVE_PWM, "R"))
        elif c == "rarcl":  link.do(lambda r: r.arc(BURST_MS, DRIVE_PWM, "L", reverse=True))
        elif c == "rarcr":  link.do(lambda r: r.arc(BURST_MS, DRIVE_PWM, "R", reverse=True))
        elif c == "rev":    link.do(lambda r: r.reverse(BURST_MS, DRIVE_PWM))
        elif c == "spinl":  link.do(lambda r: r.spin(BURST_MS, DRIVE_PWM, "L"))
        elif c == "spinr":  link.do(lambda r: r.spin(BURST_MS, DRIVE_PWM, "R"))
        elif c == "stop":   link.do(lambda r: r.stop())
        elif c == "home":   link.do(lambda r: r.home()); TILT["cur"] = 90
        elif c == "tiltup":
            TILT["cur"] = min(118, TILT["cur"] + 2)
            link.do(lambda r: r.tilt(TILT["cur"]))
        elif c == "tiltdown":
            TILT["cur"] = max(74, TILT["cur"] - 2)
            link.do(lambda r: r.tilt(TILT["cur"]))
        # pan servo retired (fried board) — the wheels are the pan axis now
        elif c == "panl":   link.do(lambda r: r.spin(250, 140, "L"))
        elif c == "panr":   link.do(lambda r: r.spin(250, 140, "R"))
        elif c == "probe0":   link.do(lambda r: r.probe(0))
        elif c == "probe50":  link.do(lambda r: r.probe(50))
        elif c == "probe100": link.do(lambda r: r.probe(100))
        else:
            return {"err": f"unknown command {c}"}
        return {"ok": True}
    except RoverError as e:
        return {"err": str(e)}


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif u.path == "/cmd":
            c = parse_qs(u.query).get("c", [""])[0]
            body = json.dumps(handle_cmd(c)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif u.path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type",
                             "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                while True:
                    f = cam.frame
                    if f:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n"
                                         + f"Content-Length: {len(f)}\r\n\r\n".encode()
                                         + f + b"\r\n")
                    time.sleep(0.08)          # ~12 fps
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
    print(f"rover remote on http://0.0.0.0:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
