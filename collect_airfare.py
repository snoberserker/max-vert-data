#!/usr/bin/env python3
"""Max Vert airfare collector — free Travelpayouts Data API.

Uses the affiliate token in TRAVELPAYOUTS_TOKEN (header x-access-token).
The Data API has no per-call fee. Signup: https://www.travelpayouts.com/

Endpoint (confirmed against the public Travelpayouts API reference):
  GET https://api.travelpayouts.com/v1/prices/cheap
  query: origin, destination, currency
  header: x-access-token

This script does not scrape Kayak, Google Flights, or airline sites.
Snapshots already in data/airfare/ are a retired Kayak scrape. Do not
serve them. A successful run of this collector replaces those files.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(REPO, "data")
UA = "MaxVertDataCollector/0.3 (maxvert.com; contact via site)"
CHEAP = "https://api.travelpayouts.com/v1/prices/cheap"

# Hub → mountain-city. Same ski routes the desk cares about.
ROUTES = [
    ("SFO", "SLC"), ("SFO", "DEN"), ("SFO", "SEA"), ("SFO", "YVR"),
    ("LAX", "SLC"), ("LAX", "DEN"), ("LAX", "SEA"), ("LAX", "YVR"),
    ("DEN", "SLC"), ("DEN", "SEA"), ("DEN", "YVR"),
    ("SEA", "YVR"), ("SEA", "DEN"),
]

CARRIERS = {
    "AA": "American", "AC": "Air Canada", "AS": "Alaska", "B6": "JetBlue",
    "DL": "Delta", "F9": "Frontier", "NK": "Spirit", "UA": "United",
    "WN": "Southwest", "WS": "WestJet", "HA": "Hawaiian", "SY": "Sun Country",
    "G4": "Allegiant",
}


def aviasales_link(origin, dest, departure_at):
    """Public search URL. The affiliate token never goes in the link or the JSON."""
    if departure_at and len(departure_at) >= 10:
        dd, mm = departure_at[8:10], departure_at[5:7]
        return "https://www.aviasales.com/search/%s%s%s%s1" % (origin, dd, mm, dest)
    return "https://www.aviasales.com/search/%s%s1" % (origin, dest)


def get_json(url, token):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json",
        "x-access-token": token,
    })
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read().decode("utf-8"))


def cheapest(payload, dest):
    block = (payload.get("data") or {}).get(dest) or {}
    best = None
    for rec in block.values():
        if not isinstance(rec, dict) or rec.get("price") is None:
            continue
        if best is None or rec["price"] < best["price"]:
            best = rec
    return best


def collect(token):
    out = {
        "collectedAt": datetime.now(timezone.utc).isoformat(),
        "source": "Travelpayouts Data API v1/prices/cheap",
        "attribution": "Indicative fares from the free Travelpayouts Data API. Search Aviasales for a live price.",
        "currency": "usd",
        "routes": [],
        "ok": 0,
        "requested": len(ROUTES),
    }
    for origin, dest in ROUTES:
        url = CHEAP + "?" + urllib.parse.urlencode({
            "origin": origin,
            "destination": dest,
            "currency": "usd",
        })
        try:
            payload = get_json(url, token)
            if not payload.get("success", True) and not payload.get("data"):
                raise RuntimeError(payload.get("error") or "request failed")
            rec = cheapest(payload, dest)
            if not rec:
                out["routes"].append({
                    "origin": origin, "destination": dest, "error": "no price",
                })
            else:
                carrier = rec.get("airline") or ""
                out["routes"].append({
                    "origin": origin,
                    "destination": dest,
                    "price": rec.get("price"),
                    "currency": "usd",
                    "carrier": carrier,
                    "carrier_name": CARRIERS.get(carrier, carrier),
                    "departure_at": rec.get("departure_at"),
                    "return_at": rec.get("return_at"),
                    "expires_at": rec.get("expires_at"),
                    "deep_link": aviasales_link(origin, dest, rec.get("departure_at")),
                })
                out["ok"] += 1
        except Exception as e:
            out["routes"].append({
                "origin": origin,
                "destination": dest,
                "error": type(e).__name__,
            })
        time.sleep(0.4)
    return out


def main():
    token = os.environ.get("TRAVELPAYOUTS_TOKEN", "").strip()
    if not token:
        sys.stderr.write(
            "TRAVELPAYOUTS_TOKEN is not set.\n"
            "Sign up free at https://www.travelpayouts.com/ and export your affiliate token.\n"
            "The Data API has no per-call fee. This collector does not scrape Kayak.\n"
        )
        raise SystemExit(1)
    out = collect(token)
    print("airfare: %d/%d routes ok" % (out["ok"], out["requested"]))
    if out["ok"] == 0:
        sys.stderr.write("No prices returned. Left data/airfare untouched.\n")
        raise SystemExit(1)
    today = datetime.now(timezone.utc).date().isoformat()
    os.makedirs(os.path.join(DATA, "airfare"), exist_ok=True)
    for name in (today + ".json", "latest.json"):
        with open(os.path.join(DATA, "airfare", name), "w") as f:
            json.dump(out, f, indent=2, sort_keys=True)
            f.write("\n")


if __name__ == "__main__":
    main()
