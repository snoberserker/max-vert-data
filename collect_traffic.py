#!/usr/bin/env python3
"""Max Vert traffic collector v2 — ski-corridor road intelligence.

Corridors:
  seatosky   Vancouver→Whistler (BC Hwy 99) via DriveBC Open511 (no auth, OGL-BC).
  i70        Denver→Grand Junction I-70 via CDOT api-511x-co.carsprogram.org
             (no auth; one eventClassifications value per call).
  i90        Seattle→Snoqualmie via WSDOT ArcGIS FeatureServers on
             data.wsdot.wa.gov (no key; the Traveler API access code is
             human-email-only).
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

def bbox_hit(coords, lat_range, lon_range):
    try:
        for p in _flatten(coords):
            lat, lon = p[1], p[0]
            if lat_range[0] <= lat <= lat_range[1] and lon_range[0] <= lon <= lon_range[1]:
                return True
    except Exception:
        return False
    return False

I70_BBOX = ((38.9, 40.1), (-109.3, -104.5))  # Grand Junction → Denver

def collect_seatosky():
    d = get("https://api.open511.gov.bc.ca/events?status=ACTIVE&limit=500&format=json")
    events = []
    for ev in d.get("events", []):
        roads = str(ev.get("roads", "")).lower()
        geo = (ev.get("geography") or {}).get("coordinates")
        if "highway 99" in roads and geo and bbox_hit(geo, (49.2, 50.2), (-123.6, -122.7)):
            events.append({"id": ev.get("id"), "type": ev.get("event_type"),
                           "severity": ev.get("severity"), "headline": ev.get("headline"),
                           "description": ev.get("description"), "updated": ev.get("updated"),
                           "status": ev.get("status")})
    return {"label": "Vancouver → Whistler (Sea-to-Sky, Hwy 99)",
            "source": "DriveBC Open511 (api.open511.gov.bc.ca)", "events": events}

def collect_i70():
    events = []
    for cls in ("roadReports", "roadClosures", "winterDriving"):
        try:
            d = get(f"https://api-511x-co.carsprogram.org/events/map-features?eventClassifications={cls}")
            time.sleep(2)
        except Exception as e:
            continue
        for f in d.get("features", []):
            p = f.get("properties", {})
            geo = (f.get("geometry") or {}).get("coordinates")
            if geo and bbox_hit(geo, *I70_BBOX):
                events.append({"id": p.get("id"), "type": cls, "headline": p.get("tooltip"),
                               "description": p.get("description"), "icon": p.get("icon")})
    return {"label": "I-70 Denver → Grand Junction (Summit County ski corridor)",
            "source": "CDOT api-511x-co.carsprogram.org (no auth)", "events": events}

def collect_i90():
    base = "https://data.wsdot.wa.gov/arcgis/rest/services/TravelInformation"
    events = []
    alerts = get(f"{base}/TravelInfoRoadAlerts/FeatureServer/0/query?where=1%3D1"
                 "&outFields=Road,RoadDirection,EventCategoryDescription,HeadlineMessage,LastModifiedDate,RoadClosedFlag&f=json")
    for f in alerts.get("features", []):
        a = f["attributes"]
        if "I-90" in str(a.get("Road", "")):
            events.append({"type": "alert", "headline": a.get("HeadlineMessage"),
                           "road": a.get("Road"), "direction": a.get("RoadDirection"),
                           "closed": a.get("RoadClosedFlag"), "updated": a.get("LastModifiedDate")})
    passes = get(f"{base}/TravelInfoMtPassReports/FeatureServer/0/query?where=1%3D1&outFields=*&f=json")
    for f in passes.get("features", []):
        a = f["attributes"]
        if "snoqualmie" in str(a.get("MountainPassName", "")).lower():
            events.append({"type": "passReport",
                           "headline": f"{a.get('MountainPassName')}: {a.get('WeatherCondition') or ''}",
                           "detail": {k: v for k, v in a.items()
                                      if v not in (None, "") and k not in ("OBJECTID", "globalId")},
                           "updated": a.get("LastUpdatedDate")})
    return {"label": "Seattle → Snoqualmie Pass (I-90)",
            "source": "WSDOT ArcGIS FeatureServers data.wsdot.wa.gov (no key)", "events": events}

CORRIDORS = {"seatosky": collect_seatosky, "i70": collect_i70, "i90": collect_i90}

if __name__ == "__main__":
    keys = sys.argv[1:] or list(CORRIDORS)
    for k in keys:
        try:
            r = CORRIDORS[k]()
            out = {"corridor": k, "label": r["label"], "source": r["source"],
                   "collectedAt": datetime.now(timezone.utc).isoformat(),
                   "activeEvents": len(r["events"]), "events": r["events"]}
            today = datetime.now(timezone.utc).date().isoformat()
            os.makedirs(os.path.join(DATA, "traffic", k), exist_ok=True)
            json.dump(out, open(os.path.join(DATA, "traffic", k, f"{today}.json"), "w"), indent=1)
            json.dump(out, open(os.path.join(DATA, "traffic", k, "latest.json"), "w"), indent=1)
            print(f"{k}: {out['activeEvents']} active events")
        except Exception as e:
            print(f"{k}: ERROR {type(e).__name__}: {e}")
