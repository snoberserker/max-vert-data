#!/usr/bin/env python3
"""Collect Environment and Climate Change Canada forecasts near catalogued ski resorts."""

import datetime as dt
import json
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CATALOG = "https://www.playmaxvert.com/api/resort-catalog"
CITYPAGE = "https://api.weather.gc.ca/collections/citypageweather-realtime/items"
SOURCE = "Environment and Climate Change Canada"
OUTPUT = Path(__file__).resolve().parent / "data/canada-forecast/latest.json"


def read_json(url):
    request = Request(url, headers={"User-Agent": "Max Vert (https://www.playmaxvert.com)"})
    with urlopen(request, timeout=25) as response:
        return json.load(response)


def distance(lat, lon, station_lat, station_lon):
    a, b = math.radians(lat), math.radians(station_lat)
    haversine = math.sin((b - a) / 2) ** 2
    haversine += math.cos(a) * math.cos(b) * math.sin(math.radians(station_lon - lon) / 2) ** 2
    return 12742 * math.asin(min(1, math.sqrt(haversine)))


def period(row):
    temperatures = (row.get("temperatures") or {}).get("temperature") or []
    high = next((temp for temp in temperatures if (temp.get("class") or {}).get("en") == "high"), None)
    wind_parts = (row.get("winds") or {}).get("periods") or []
    wind = next((part for part in wind_parts if (part.get("speed") or {}).get("value", {}).get("en", 0) > 0), None)
    temperature = (high or next(iter(temperatures), {})).get("value", {}).get("en")
    return {
        "name": row.get("period", {}).get("textForecastName", {}).get("en", ""),
        "daytime": high is not None,
        "summary": (row.get("abbreviatedForecast") or {}).get("textSummary", {}).get("en")
        or (row.get("cloudPrecip") or {}).get("en", ""),
        "detail": (row.get("textSummary") or {}).get("en", ""),
        "temperature": temperature,
        "unit": "C",
        "precipitation": (row.get("lop") or {}).get("value", {}).get("en"),
        "wind": f"{wind['speed']['value']['en']} km/h {(wind.get('direction') or {}).get('en', '')}".strip()
        if wind else "",
    }


def normalize(features, lat, lon, now):
    forecasts = []
    for feature in features:
        coords = (feature.get("geometry") or {}).get("coordinates")
        properties = feature.get("properties") or {}
        group = properties.get("forecastGroup") or {}
        if not coords or not group.get("forecasts"):
            continue
        try:
            issued = dt.datetime.fromisoformat(group["timestamp"]["en"])
        except (KeyError, TypeError, ValueError):
            continue
        if issued.tzinfo is None or abs(now - issued) >= dt.timedelta(hours=24):
            continue
        km = distance(lat, lon, coords[1], coords[0])
        if km > 60:
            continue
        periods = [period(row) for row in group["forecasts"][:14]]
        periods = [row for row in periods if row["name"] and (row["summary"] or row["temperature"] is not None)]
        if periods:
            forecasts.append((km, {
                "status": "snapshot",
                "source": SOURCE,
                "sourceLocation": properties.get("name", {}).get("en", ""),
                "issuedAt": issued.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "periods": periods,
            }))
    return min(forecasts, key=lambda row: row[0])[1] if forecasts else None


def collect():
    resorts = [resort for resort in read_json(CATALOG) if resort["country"] == "Canada"]
    now = dt.datetime.now(dt.timezone.utc)

    def lookup(resort):
        lat, lon = resort["lat"], resort["lon"]
        lon_span = .55 / math.cos(math.radians(lat))
        bounds = (lon - lon_span, lat - .55, lon + lon_span, lat + .55)
        query = urlencode({"limit": 40, "f": "json", "bbox": ",".join(f"{value:.4f}" for value in bounds)})
        try:
            return resort["id"], normalize(read_json(f"{CITYPAGE}?{query}")["features"], lat, lon, now)
        except (OSError, ValueError, KeyError) as error:
            print(f"{resort['id']}: {error}")
            return resort["id"], None

    with ThreadPoolExecutor(max_workers=4) as executor:
        outlooks = {slug: outlook for slug, outlook in executor.map(lookup, resorts) if outlook}
    if not outlooks:
        raise RuntimeError("No Canadian forecasts were available")
    stamp = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text(json.dumps({"collectedAt": stamp, "resorts": outlooks}, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(OUTPUT)
    print(f"Canadian forecasts: {len(outlooks)}/{len(resorts)}")


if __name__ == "__main__":
    collect()
