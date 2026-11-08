#!/usr/bin/env python3
"""Max Vert airfare collector - indicative cheapest fares on ski routes.

Source: Kayak public SEO route pages (/flight-routes/ORG/DST). No auth; robots.txt
does not disallow /flight-routes/. CAVEAT: Kayak ToS restricts automated collection;
prices are INDICATIVE, each record deep-links to Kayak with attribution. If this
graduates to a public display feature, move to a licensed source (Travelpayouts).
"""
import json, os, re, time, urllib.request
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(REPO, "data")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36")

ROUTES = [("SFO", "SLC"), ("SFO", "DEN"), ("SFO", "SEA"), ("SFO", "YVR"),
          ("LAX", "SLC"), ("LAX", "DEN"), ("LAX", "SEA"), ("LAX", "YVR"),
          ("DEN", "SLC"), ("DEN", "SEA"), ("DEN", "YVR"),
          ("SEA", "YVR"), ("SEA", "DEN")]

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf8", "ignore")

def parse(html, org, dst):
    out = {"origin": org, "destination": dst}
    t = re.search(r"(?is)<title>(.*?)</title>", html)
    if t:
        m = re.search(r"\$(\d+)", t.group(1))
        if m:
            out["cheapest_usd"] = int(m.group(1))
    d = re.search(r'(?:name="description" content=")(.*?)"', html, re.I)
    if d:
        c = re.search(r"on ([\w][\w ]*?) from \$", d.group(1))
        if c:
            out["carrier"] = c.group(1).strip()
    c = re.search(r'"cheapestPrice":\{"price":(\d+)', html)
    if c:
        out["cheapest_usd"] = out.get("cheapest_usd") or int(c.group(1))
        i = html.find('"cheapestPrice"')
        mm = re.search(r"departing in (\w+)", html[max(0, i - 300):i])
        if mm:
            out["price_month"] = mm.group(1)
    if "cheapest_usd" not in out:
        return None
    out["deep_link"] = "https://www.kayak.com/flight-routes/%s-%s/" % (org, dst)
    return out

def main():
    out = {"collectedAt": datetime.now(timezone.utc).isoformat(),
           "source": "Kayak public route pages (indicative cheapest fares)",
           "attribution": "Prices are indicative; search on Kayak for current fares.",
           "routes": [], "ok": 0, "requested": len(ROUTES)}
    for org, dst in ROUTES:
        try:
            html = fetch("https://www.kayak.com/flight-routes/%s/%s" % (org, dst))
            rec = parse(html, org, dst)
            if rec:
                out["routes"].append(rec)
                out["ok"] += 1
        except Exception as e:
            out["routes"].append({"origin": org, "destination": dst, "error": type(e).__name__})
        time.sleep(2.5)
    today = datetime.now(timezone.utc).date().isoformat()
    os.makedirs(os.path.join(DATA, "airfare"), exist_ok=True)
    json.dump(out, open(os.path.join(DATA, "airfare", today + ".json"), "w"), indent=1)
    json.dump(out, open(os.path.join(DATA, "airfare", "latest.json"), "w"), indent=1)
    print("airfare: %d/%d routes ok" % (out["ok"], out["requested"]))

if __name__ == "__main__":
    main()
