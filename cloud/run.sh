#!/bin/bash
# Max Vert weather collector — Cloud Run Job entrypoint.
# Shallow-clones the repo fresh at runtime (so resorts.json is always current),
# runs the resort-forecast collector, commits data/, pushes to GitHub.
set -euo pipefail
cd /work
git clone --depth 1 "https://x-access-token:${GITHUB_TOKEN}@github.com/snoberserker/max-vert-data.git" repo
cd repo
python3 collect_v2.py resort-forecast
git config user.email "agent@maxvert.dev"
git config user.name "maxvert-cloud-collector"
git add data
if git diff --cached --quiet; then
  echo "No data changes; nothing to commit."
else
  git commit -m "Weather data $(date -u +%FT%TZ) [cloud-run]"
  git push
  echo "PUSHED"
fi
