#!/usr/bin/env python3
"""Max Vert traffic collector — ski-corridor road intelligence.

Corridors:
  seatosky   Vancouver→Whistler (BC Hwy 99) via DriveBC Open511 (no auth, OGL-BC).
Others added as sources are verified (I-70/CDOT, I-90/WSDOT need free access codes).
"""
import json, os, sys, time, urllib.request
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(REPO, "data")
UA = "MaxVertDataCollector/0.2 (maxvert.com; contact via site)"

def get(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(3 * (i + 1))

def _flatten(coords):
    if isinstance(coords[0], (int, float)):
        yield coords
    else:
        for c in coords:
            yield from _flatten(c)

def in_bbox(event, lat_range, lon_range):
    geo = (event.get("geography") or {}).get("coordinates")
    if not geo:
        return False
    try:
        for p in _flatten(geo):
            lat, lon = p[1], p[0]
            if lat_range[0] <= lat <= lat_range[1] and lon_range[0] <= lon <= lon_range[1]:
                return True
    except Exception:
        return False
    return False

CORRIDORS = {
    "seatosky": {
        "label": "Vancouver → Whistler (Sea-to-Sky, Hwy 99)",
        "source": "DriveBC Open511 (api.open511.gov.bc.ca)",
        "filter": lambda ev: (
            any("highway 99" in str(r.get("name", "")).lower() for r in ev.get("roads", []))
            and in_bbox(ev, (49.2, 50.2), (-123.6, -122.7))
        ),
    },
}

def collect_corridor(key):
    cfg = CORRIDORS[key]
    d = get("https://api.open511.gov.bc.ca/events?status=ACTIVE&limit=500&format=json")
    events = []
    for ev in d.get("events", []):
        if not cfg["filter"](ev):
            continue
        events.append({
            "id": ev.get("id"), "type": ev.get("event_type"),
            "subtypes": ev.get("event_subtypes"), "severity": ev.get("severity"),
            "headline": ev.get("headline"), "description": ev.get("description"),
            "roads": [r.get("name") for r in ev.get("roads", [])],
            "updated": ev.get("updated"), "status": ev.get("status"),
        })
    out = {"corridor": key, "label": cfg["label"], "source": cfg["source"],
           "collectedAt": datetime.now(timezone.utc).isoformat(),
           "activeEvents": len(events), "events": events}
    today = datetime.now(timezone.utc).date().isoformat()
    os.makedirs(os.path.join(DATA, "traffic", key), exist_ok=True)
    json.dump(out, open(os.path.join(DATA, "traffic", key, f"{today}.json"), "w"), indent=1)
    json.dump(out, open(os.path.join(DATA, "traffic", key, "latest.json"), "w"), indent=1)
    return out

if __name__ == "__main__":
    keys = sys.argv[1:] or list(CORRIDORS)
    for k in keys:
        o = collect_corridor(k)
        print(f"{k}: {o['activeEvents']} active events")
