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
    for r in rows:
        flag = r.get("flag", "needs_human")
        counts[flag] = counts.get(flag, 0) + 1
        color = COLORS.get(flag, "#64748b")
        moist = r.get("moisture")
        moist_s = f"{moist:.2f}" if isinstance(moist, (int, float)) else "—"
        cause_extra = f" [{r['leaf_cause']}]" if r.get("leaf_cause") not in (None, "none") else ""
        tiles += f"""
        <div class="tile" style="--c:{color}">
          <div class="badge">{ICONS.get(flag, "?")}</div>
          <h3>{r.get("plant_id", "?")}</h3>
          <div class="flag">{flag.replace("_", " ")}{cause_extra}</div>
          <div class="m">moisture {moist_s}</div>
          <div class="why">{r.get("cause", "")}</div>
        </div>"""
    if not rows:
        tiles = '<p class="empty">No plants scanned yet — reports will appear here live.</p>'
    summary = " · ".join(f"{v} {k.replace('_',' ')}" for k, v in sorted(counts.items())) or "waiting"
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="3"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Field Triage Rover</title><style>
body{{margin:0;background:#14171c;color:#e8ebef;font:15px/1.5 system-ui,sans-serif;padding:28px}}
h1{{font-size:22px;margin:0 0 4px;letter-spacing:.02em}} .sub{{color:#8b93a1;margin:0 0 24px;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px}}
.tile{{background:#1c2027;border:1px solid #2e343d;border-left:5px solid var(--c);border-radius:10px;padding:14px 16px}}
.badge{{float:right;font-weight:700;font-size:11px;color:var(--c);letter-spacing:.08em}}
h3{{margin:0 0 2px;font-size:15px}} .flag{{color:var(--c);font-weight:600;font-size:13px;text-transform:uppercase;letter-spacing:.04em}}
.m{{color:#8b93a1;font-size:12px;margin-top:6px;font-family:ui-monospace,monospace}}
.why{{color:#8b93a1;font-size:12px;margin-top:6px}} .empty{{color:#8b93a1}}
</style></head><body>
<h1>Field Triage Rover — live plant board</h1>
<p class="sub">{summary} · auto-refreshing · served by the rover's own Pi</p>
<div class="grid">{tiles}</div></body></html>"""


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
