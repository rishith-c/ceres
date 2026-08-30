#!/usr/bin/env python3
"""Live triage dashboard, served by the Pi itself (stdlib only — no deps).

    python3 dashboard.py [port]        # default 8080

Reads work/reports.jsonl (one PlantReport per line, written by station.py's
append_report) and renders a plant-row heatmap: one tile per plant, colored
by triage flag, with cause text and moisture. Auto-refreshes every 3 s.
Works with zero internet — any browser on the same network:
    http://<pi-address>:8080
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPORTS = Path(__file__).parent / "work" / "reports.jsonl"

COLORS = {
    "fine": "#1f9d55", "underwatered": "#d97706", "diseased": "#c02637",
    "water_then_recheck": "#b45309", "needs_human": "#64748b",
}
ICONS = {
    "fine": "OK", "underwatered": "DRY", "diseased": "SICK",
    "water_then_recheck": "DRY+", "needs_human": "?",
}


def load_reports():
    if not REPORTS.exists():
        return []
    rows = []
    for line in REPORTS.read_text().splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    latest = {}
    for r in rows:                      # last report per plant wins
        latest[r.get("plant_id", "?")] = r
    return [latest[k] for k in sorted(latest)]


def render():
    rows = load_reports()
    tiles = ""
    counts = {}
    STYLE = {
        "fine":               ("#0B7A33", "#EFF4E2", "healthy"),
        "underwatered":       ("#8A6B18", "#FBF3DA", "dry"),
        "water_then_recheck": ("#923B0F", "#FBF3DA", "dry + recheck"),
        "diseased":           ("#BA2623", "#F9E8E7", "sick"),
        "needs_human":        ("#52514E", "#F3F3F3", "check me"),
    }
    for r in rows:
        flag = r.get("flag", "needs_human")
        counts[flag] = counts.get(flag, 0) + 1
        ink, wash, word = STYLE.get(flag, STYLE["needs_human"])
        moist = r.get("moisture")
        moist_s = f"{moist:.2f}" if isinstance(moist, (int, float)) else "not measured"
        cause_extra = f' <span class="pest">{r["leaf_cause"]}</span>' if r.get("leaf_cause") not in (None, "none") else ""
        tiles += f"""
        <article class="tile">
          <header><h3>{r.get("plant_id", "?")}</h3>
            <span class="chip" style="color:{ink};background:{wash}">{word}</span></header>
          <div class="flag" style="color:{ink}">{flag.replace("_", " ")}{cause_extra}</div>
          <dl><dt>moisture</dt><dd>{moist_s}</dd></dl>
          <p class="why">{r.get("cause", "")}</p>
        </article>"""
    if not rows:
        tiles = '<p class="empty">No plants scanned yet — verdicts appear here the moment the rover files one.</p>'
    n = len(rows)
    summary = " · ".join(f"{v} {k.replace('_',' ')}" for k, v in sorted(counts.items())) or "waiting for the rover"
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Field Triage Rover</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root {{
  --bg:#FFFFFF; --surface-2:#F3F3F3; --border:rgba(26,28,31,.078);
  --border-strong:rgba(26,28,31,.117); --ink:#1A1C1F; --ink-2:rgba(26,28,31,.66);
  --ink-4:rgba(26,28,31,.48); --daisy:#E9C64A; --daisy-wash:#FBF3DA;
  --leaf:#6B8F2E; --leaf-wash:#EFF4E2;
  --shadow-1:0 0 0 .5px var(--border-strong),0 1px 2px rgba(0,0,0,.04);
  --shadow-2:0 0 0 .5px var(--border-strong),0 3px 7.5px rgba(0,0,0,.04),0 0 20px rgba(0,0,0,.051);
  --serif:"Source Serif 4",Charter,Georgia,serif;
  --sans:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);
  font:14px/1.55 var(--sans);padding:40px 32px 64px}}
.wrap{{max-width:1000px;margin:0 auto}}
.crown{{display:flex;align-items:center;gap:10px;margin-bottom:6px}}
.dot{{width:10px;height:10px;border-radius:50%;background:var(--leaf);
  box-shadow:0 0 0 4px var(--leaf-wash)}}
.crown span{{font:500 11px var(--mono);letter-spacing:.12em;color:var(--ink-4);text-transform:uppercase}}
h1{{font:600 34px/1.15 var(--serif);margin:0 0 6px;letter-spacing:-.01em}}
.sub{{color:var(--ink-2);margin:0 0 30px;font-size:13.5px}}
.sub b{{color:var(--ink);font-weight:600}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px}}
.tile{{background:var(--bg);border-radius:12px;box-shadow:var(--shadow-1);
  padding:16px 18px;transition:box-shadow .18s cubic-bezier(.23,1,.32,1)}}
.tile:hover{{box-shadow:var(--shadow-2)}}
.tile header{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:2px}}
h3{{font:600 17px var(--serif);margin:0}}
.chip{{font:500 10.5px var(--mono);letter-spacing:.06em;text-transform:uppercase;
  padding:3px 8px;border-radius:999px}}
.flag{{font-weight:600;font-size:12.5px;text-transform:uppercase;letter-spacing:.05em;margin:4px 0 10px}}
.pest{{font:500 10.5px var(--mono);background:var(--daisy-wash);color:#8A6B18;
  padding:2px 6px;border-radius:4px;text-transform:none;letter-spacing:0}}
dl{{display:flex;gap:8px;margin:0 0 8px;align-items:baseline}}
dt{{font-size:11px;color:var(--ink-4);text-transform:uppercase;letter-spacing:.06em}}
dd{{margin:0;font:500 13px var(--mono)}}
.why{{color:var(--ink-2);font-size:12.5px;margin:0;border-top:1px solid var(--border);padding-top:8px}}
.empty{{color:var(--ink-2)}}
footer{{margin-top:36px;color:var(--ink-4);font-size:12px}}
</style></head><body><div class="wrap">
<div class="crown"><div class="dot"></div><span>Field Triage Rover · live</span></div>
<h1>The plant board</h1>
<p class="sub"><b>{n} plants</b> · {summary} · every verdict carries its reason</p>
<div class="grid" id="grid">{tiles}</div>
<footer>Served by the rover&rsquo;s own Raspberry Pi · refreshes live · no cloud required</footer>
</div>
<script>
setInterval(async () => {{
  try {{
    const t = await (await fetch(location.href)).text();
    const doc = new DOMParser().parseFromString(t, "text/html");
    document.getElementById("grid").innerHTML = doc.getElementById("grid").innerHTML;
    document.querySelector(".sub").innerHTML = doc.querySelector(".sub").innerHTML;
  }} catch (e) {{}}
}}, 3000);
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = render().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"triage dashboard on http://0.0.0.0:{port}")
    HTTPServer(("0.0.0.0", port), H).serve_forever()
