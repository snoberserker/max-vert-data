#!/usr/bin/env python3
"""Max Vert snow data collector v2 — nationwide scale.

Modes:
  snow-all      All 976 SNOTEL/SNTLT stations nationwide (bulk AWDB queries).
  resort-forecast   NWS forecast for all 601 US ski areas (OpenStreetMap).
  daily         v1 snapshot (marquee stations) + forecast + stats.
  weekly        search-interest trends (needs pytrends PYTHONPATH).

All sources public domain / ODbL. OpenSnow is featured, never scraped.
"""
import json, os, sys, time, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(REPO, "data")
UA = "MaxVertDataCollector/0.2 (maxvert.com; contact via site)"

def get(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(3 * (i + 1))

def collect_snow_all(batch_size=80):
    stations = json.load(open(os.path.join(REPO, "snotel_stations.json")))
    triplets = [s["triplet"] for s in stations]
    end = date.today(); begin = end - timedelta(days=3)
    by_triplet = {}
    n_err = 0
    for i in range(0, len(triplets), batch_size):
        batch = triplets[i:i + batch_size]
        url = ("https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data?"
               + urllib.parse.urlencode({"stationTriplets": ",".join(batch),
                                         "elements": "WTEQ,SNWD", "duration": "DAILY",
                                         "beginDate": begin.isoformat(), "endDate": end.isoformat()}))
        try:
            resp = get(url)
        except Exception:
            n_err += len(batch)
            time.sleep(5)
            continue
        for rec in resp:
            t = rec["stationTriplet"]
            vals = {}
            for item in rec.get("data", []):
                el = item["stationElement"]["elementCode"].lower()
                for v in item.get("values", []):
                    if v.get("value") is not None:
                        vals.setdefault(el, {})[v["date"]] = v["value"]
            by_triplet[t] = vals
        time.sleep(1.0)
    out = {"date": date.today().isoformat(),
           "collectedAt": datetime.now(timezone.utc).isoformat(),
           "stationsRequested": len(triplets), "stationsReporting": len(by_triplet),
           "stations": []}
    meta = {s["triplet"]: s for s in stations}
    depths = []
    for t, vals in sorted(by_triplet.items()):
        swe = max(vals.get("wteq", {}).values(), default=None)
        snwd = max(vals.get("snwd", {}).values(), default=None)
        rec = {"triplet": t, "name": meta.get(t, {}).get("name"), "state": meta.get(t, {}).get("state"),
               "lat": meta.get(t, {}).get("latitude"), "lon": meta.get(t, {}).get("longitude"),
               "elevation_ft": meta.get(t, {}).get("elevation_ft"),
               "swe_in": swe, "snwd_in": snwd}
        if snwd is not None and snwd > 0:
            depths.append(snwd)
        out["stations"].append(rec)
    out["stats"] = {"stations_with_snow": len(depths),
                    "mean_depth_in_of_snowy": round(sum(depths) / len(depths), 1) if depths else 0}
    os.makedirs(os.path.join(DATA, "snowpack-all"), exist_ok=True)
    json.dump(out, open(os.path.join(DATA, "snowpack-all", f"{out['date']}.json"), "w"), indent=1)
    json.dump(out, open(os.path.join(DATA, "snowpack-all", "latest.json"), "w"), indent=1)
    return out

def collect_resort_forecast(delay=0.3):
    resorts = json.load(open(os.path.join(REPO, "resorts.json")))
    out = {"date": date.today().isoformat(),
           "collectedAt": datetime.now(timezone.utc).isoformat(),
           "requested": len(resorts), "ok": 0, "resorts": []}
    for r in resorts:
        try:
            url = r.get("forecast_url")
            if not url:  # fallback: two-step points lookup
                meta = get(f"https://api.weather.gov/points/{r['lat']},{r['lon']}")
                url = meta["properties"]["forecast"]
            f = get(url)
            periods = []
            for p in f["properties"]["periods"][:4]:
                periods.append({"name": p["name"], "tempF": p["temperature"],
                                "pop": (p.get("probabilityOfPrecipitation") or {}).get("value"),
                                "short": p.get("shortForecast")})
            out["resorts"].append({"name": r["name"], "lat": r["lat"], "lon": r["lon"],
                                   "office": f["properties"].get("cwa"), "periods": periods})
            out["ok"] += 1
        except Exception as e:
            out["resorts"].append({"name": r["name"], "lat": r["lat"], "lon": r["lon"],
                                   "error": f"{type(e).__name__}"})
        time.sleep(delay)
        if len(out["resorts"]) % 100 == 0:
            print(f"  ... {len(out['resorts'])}/{len(resorts)}", flush=True)
    os.makedirs(os.path.join(DATA, "resort-forecast"), exist_ok=True)
    json.dump(out, open(os.path.join(DATA, "resort-forecast", f"{out['date']}.json"), "w"), indent=1)
    json.dump(out, open(os.path.join(DATA, "resort-forecast", "latest.json"), "w"), indent=1)
    return out

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "snow-all"
    if mode == "snow-all":
        d = collect_snow_all()
        s = d["stats"]
        print(f"snow-all: {d['stationsReporting']}/{d['stationsRequested']} reporting; "
              f"{s['stations_with_snow']} with snow; mean snowy depth {s['mean_depth_in_of_snowy']} in")
    elif mode == "resort-forecast":
        d = collect_resort_forecast()
        print(f"resort-forecast: {d['ok']}/{d['requested']} ok")
    else:
        raise SystemExit(f"unknown mode {mode}; also see collect.py for daily/weekly")
