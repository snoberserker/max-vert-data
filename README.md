# max-vert-data

Daily and weekly skiing/snowboarding data feeds for maxvert.com.

## Sources (all free/public)

- **USDA NRCS AWDB REST API** (public domain, no key): SNOTEL snowpack — snow-water-equivalent (WTEQ) and snow depth (SNWD) — for 7 resort-adjacent stations across CA, UT, CO, WA, OR. Daily.
- **NWS api.weather.gov** (public domain, no key): 7-day point forecasts for marquee resorts. Daily.
- **Google search interest** for "skiing" / "snowboarding" via pytrends. Weekly.
- **OpenSnow is featured, not scraped**: their API is not openly available; the site links to and features OpenSnow content instead.

## Structure

- `data/snowpack/YYYY-MM-DD.json` — daily snapshot per station (latest + 45-day series)
- `data/latest.json` — most recent daily snapshot (what the site renders)
- `data/forecast/YYYY-MM-DD.json` — resort point forecasts
- `data/trends/history.jsonl` — weekly search-interest history (appended)
- `stations.json`, `forecast_points.json` — curated station/point config

## Run

```bash
python3 collect.py daily    # SNOTEL + NWS snapshots
python3 collect.py weekly   # search-interest trends (needs pytrends)
```

pytrends note: installed under `/opt/data/home/.local/lib/python3.14/site-packages`
(user site); run with `PYTHONPATH=/opt/data/home/.local/lib/python3.14/site-packages`
under the Hermes venv interpreter.

## Consumers

The maxvert.com data page (`/data/`) fetches `data/latest.json` and
`data/trends/history.jsonl` from raw.githubusercontent.com on this repo.
