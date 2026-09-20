#!/usr/bin/env python3
"""Local web console for SECNS. Standard library only - nothing to install.

    python server.py            then open http://localhost:8000

The browser is only a view. Every severity score, contact ranking and message
shown on screen is computed by the Python agents in secns/, not by JavaScript.
"""

import json
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from secns import Orchestrator, make_packet
from secns.agents import DispatchAgent
from secns.config import EVENTS, LOCATIONS

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
PORT = int(os.environ.get("SECNS_PORT", 8000))

ORCH = Orchestrator()
INCIDENTS = {}          # incident_id -> Incident, kept for ACK and escalation


def serialise(inc):
    return {
        "id": inc.incident_id,
        "severity": inc.severity,
        "tier": inc.tier,
        "suppressed": inc.suppressed,
        "location": inc.location,
        "coordinates": inc.coordinates,
        "facility": inc.nearest_facility,
        "outcome": inc.outcome,
        "event_label": EVENTS[inc.normalised["event"]]["label"],
        "trace": inc.trace,
        "contacts": [{"name": c.name, "relation": c.relation,
                      "channels": " + ".join(c.channels), "km": c.distance_km,
                      "weight": c.weight, "status": c.status}
                     for c in inc.ranked_contacts],
        "messages": [{"contact": m.contact, "channel": m.channel, "body": m.body}
                     for m in inc.messages],
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ---------------- GET: static files ----------------
    def do_GET(self):
        path = "/index.html" if self.path in ("/", "") else self.path.split("?")[0]
        if path == "/api/meta":
            return self._send(200, json.dumps({
                "events": {k: v["label"] for k, v in EVENTS.items()},
                "locations": {k: v["label"] for k, v in LOCATIONS.items()},
            }))
        fname = os.path.normpath(os.path.join(ROOT, path.lstrip("/")))
        if not fname.startswith(ROOT) or not os.path.isfile(fname):
            return self._send(404, "not found", "text/plain")
        ctype = {"html": "text/html; charset=utf-8", "css": "text/css",
                 "js": "text/javascript"}.get(fname.rsplit(".", 1)[-1], "text/plain")
        with open(fname, "rb") as fh:
            self._send(200, fh.read(), ctype)

    # ---------------- POST: run the pipeline ----------------
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")

        if self.path == "/api/incident":
            try:
                inc = ORCH.handle(make_packet(
                    payload.get("event", "fall"),
                    int(payload.get("heart_rate", 120)),
                    float(payload.get("impact_g", 0)),
                    int(payload.get("user_reply", 0)),
                    payload.get("location_key", "home")))
            except ValueError as exc:
                return self._send(400, json.dumps({"error": str(exc)}))
            INCIDENTS[inc.incident_id] = inc
            return self._send(200, json.dumps(serialise(inc)))

        if self.path == "/api/ack":
            inc = INCIDENTS.get(payload.get("id"))
            if not inc:
                return self._send(404, json.dumps({"error": "unknown incident"}))
            DispatchAgent.acknowledge(inc, payload.get("contact", ""))
            return self._send(200, json.dumps(serialise(inc)))

        if self.path == "/api/escalate":
            inc = INCIDENTS.get(payload.get("id"))
            if not inc:
                return self._send(404, json.dumps({"error": "unknown incident"}))
            lines = DispatchAgent.escalate(inc)
            inc.log("Dispatch & Escalation Agent", lines)
            return self._send(200, json.dumps(serialise(inc)))

        self._send(404, json.dumps({"error": "no such endpoint"}))

    def log_message(self, fmt, *args):
        pass        # keep the console clean during a live demo


if __name__ == "__main__":
    print("SECNS console running at  http://localhost:%d" % PORT)
    print("Press Ctrl+C to stop.")
    try:
        webbrowser.open("http://localhost:%d" % PORT)
    except Exception:
        pass
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
