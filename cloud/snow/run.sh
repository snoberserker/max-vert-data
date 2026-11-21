#!/bin/bash
# Max Vert nightly snow collector — Cloud Run Job entrypoint.
# Shallow-clones repo fresh at runtime, runs snow-all (SNOTEL) + daily v1 +
# traffic + airfare, commits data/, pushes to GitHub.
# snow-all failure fails the job (alerts fire); traffic/airfare/daily are
# non-fatal so a broken side-feed never blocks the SNOTEL snapshot.
set -euo pipefail
cd /work
git clone --depth 1 "https://x-access-token:${GITHUB_TOKEN}@github.com/snoberserker/max-vert-data.git" repo
cd repo
python3 collect_v2.py snow-all
python3 collect.py daily || echo "WARN: daily v1 failed (non-fatal)"
python3 collect_traffic.py || echo "WARN: traffic failed (non-fatal)"
if [ -n "${TRAVELPAYOUTS_TOKEN:-}" ]; then
  python3 collect_airfare.py || echo "WARN: airfare failed (non-fatal)"
else
  echo "TRAVELPAYOUTS_TOKEN not set; airfare skipped"
fi
git config user.email "agent@maxvert.dev"
git config user.name "maxvert-cloud-collector"
git add data
if git diff --cached --quiet; then
  echo "No data changes; nothing to commit."
else
  git commit -m "Snow data $(date -u +%FT%TZ) [cloud-run]"
  git push
  echo "PUSHED"
fi
