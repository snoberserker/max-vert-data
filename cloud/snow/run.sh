#!/bin/bash
# Max Vert nightly snow collector — Cloud Run Job entrypoint.
# Runs snow-all (SNOTEL) + daily v1 + traffic + airfare, commits data/ to
# GitHub AND uploads to the GCS feed bucket (dual-write).
# snow-all and the GCS upload are fatal (alerts fire); the side-feeds are
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
  pushed=0
  for i in 1 2 3; do
    if git push 2>/dev/null; then pushed=1; echo "PUSHED"; break; fi
    echo "push rejected; rebasing onto latest main"
    git fetch --depth 1 origin main
    git rebase FETCH_HEAD || git rebase --abort
    sleep 5
  done
  if [ "$pushed" = 0 ]; then
    echo "WARN: git push failed after retries (git mirror stale; GCS upload is authoritative)"
  fi
fi
python3 cloud/gcs_upload.py data
echo "GCS-OK"
