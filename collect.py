#!/usr/bin/env python3
"""Max Vert snow data collector.

Daily: SNOTEL snowpack (WTEQ snow-water-equivalent, SNWD snow depth) from the
free public USDA NRCS AWDB REST API for a curated set of resort-adjacent
stations, plus NWS point forecasts. Appends dated JSON snapshots under data/.

Weekly: collects search-interest trend points (optional; fails soft).

Sources are public-domain / free APIs. No OpenSnow data is collected — the
site links to and features OpenSnow instead (their API is not openly available).
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(REPO, "data")
UA = "MaxVertDataCollector/0.1 (maxvert.com; contact via site)"

STATIONS = json.load(open(os.path.join(REPO, "stations.json")))

def get(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(3 * (i + 1))

def awdb_series(triplet, elements, days=45):
    end = date.today()
    begin = end - timedelta(days=days)
    url = ("https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data?"
           + urllib.parse.urlencode({
               "stationTriplets": triplet, "elements": elements,
               "duration": "DAILY", "beginDate": begin.isoformat(),
               "endDate": end.isoformat()}))
    out = {}
    for rec in get(url):
        for item in rec.get("data", [rec]):
            el = item["stationElement"]["elementCode"]
            vals = {v["date"]: v["value"] for v in item.get("values", []) if v.get("value") is not None}
            if vals:
                out.setdefault(el, {}).update(vals)
    return out

def collect_daily():
    today = date.today().isoformat()
    snapshot = {"date": today, "collectedAt": datetime.now(timezone.utc).isoformat(), "stations": []}
    for st in STATIONS:
        s = {"triplet": st["triplet"], "station": st["name"], "resortArea": st["resortArea"],
             "latitude": st.get("latitude"), "longitude": st.get("longitude")}
        try:
            series = awdb_series(st["triplet"], "WTEQ,SNWD")
            for el in ("WTEQ", "SNWD"):
                vals = series.get(el, {})
                latest = sorted(vals.items())[-1] if vals else (None, None)
                prev = sorted(vals.items())[-2] if len(vals) > 1 else (None, None)
                s[el.lower() + "_in"] = latest[1]
                s[el.lower() + "_date"] = latest[0]
                s[el.lower() + "_prev_in"] = prev[1] if prev[0] == (date.today() - timedelta(days=1)).isoformat() else None
                s[el.lower() + "_45d"] = {d: v for d, v in sorted(vals.items())}
        except Exception as e:
            s["error"] = f"{type(e).__name__}: {e}"
        snapshot["stations"].append(s)
        time.sleep(1.5)  # be polite to the public API
    os.makedirs(os.path.join(DATA, "snowpack"), exist_ok=True)
    with open(os.path.join(DATA, "snowpack", f"{today}.json"), "w") as f:
        json.dump(snapshot, f, indent=2, sort_keys=True)
    with open(os.path.join(DATA, "latest.json"), "w") as f:
        json.dump(snapshot, f, indent=2, sort_keys=True)
    return snapshot

def collect_forecast():
    today = date.today().isoformat()
    out = {"date": today, "collectedAt": datetime.now(timezone.utc).isoformat(), "points": []}
    for pt in json.load(open(os.path.join(REPO, "forecast_points.json"))):
        try:
            meta = get(f"https://api.weather.gov/points/{pt['lat']},{pt['lon']}")
            grid = get(meta["properties"]["forecast"])
            periods = []
            for p in grid["properties"]["periods"][:10]:
                periods.append({"name": p["name"], "tempF": p["temperature"],
                                "pop": (p.get("probabilityOfPrecipitation") or {}).get("value"),
                                "short": p.get("shortForecast")})
            out["points"].append({"label": pt["label"], "lat": pt["lat"], "lon": pt["lon"],
                                  "office": meta["properties"]["cwa"], "periods": periods})
        except Exception as e:
            out["points"].append({"label": pt["label"], "error": f"{type(e).__name__}: {e}"})
        time.sleep(1.0)
    os.makedirs(os.path.join(DATA, "forecast"), exist_ok=True)
    with open(os.path.join(DATA, "forecast", f"{today}.json"), "w") as f:
        json.dump(out, f, indent=2, sort_keys=True)
    with open(os.path.join(DATA, "forecast", "latest.json"), "w") as f:
        json.dump(out, f, indent=2, sort_keys=True)
    return out

def collect_weekly_trends():
    """Search-interest trends for 'skiing' and 'snowboarding' (Google via pytrends).
    Fails soft — a missing/rate-limited run is logged, not fatal."""
    out = {"collectedAt": datetime.now(timezone.utc).isoformat()}
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl="en-US", tz=480)
        pt.build_payload(["skiing", "snowboarding"], timeframe="today 3-m")
        df = pt.interest_over_time()
        if len(df):
            rows = [{"week": str(idx.date()), "skiing": int(r["skiing"]),
                     "snowboarding": int(r["snowboarding"])}
                    for idx, r in df.iterrows()]
            out["weekly"] = rows
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    path = os.path.join(DATA, "trends", "latest.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # merge into history
    hist_path = os.path.join(DATA, "trends", "history.jsonl")
    with open(hist_path, "a") as f:
        f.write(json.dumps(out) + "\n")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, sort_keys=True)
    return out

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "daily"
    if mode == "daily":
        snap = collect_daily()
        fc = collect_forecast()
        ok = sum(1 for s in snap["stations"] if "error" not in s)
        print(f"daily: {ok}/{len(snap['stations'])} stations ok; forecast points: "
              f"{sum(1 for p in fc['points'] if 'error' not in p)}/{len(fc['points'])} ok")
    elif mode == "weekly":
        t = collect_weekly_trends()
        n = len(t.get("weekly", []))
        print(f"weekly: {n} trend weeks" + (f" ERROR {t['error']}" if "error" in t else ""))
    else:
        raise SystemExit(f"unknown mode {mode}")
