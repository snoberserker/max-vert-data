# Max Vert cloud collectors (GCP Cloud Run Jobs)

The two high-frequency data collectors no longer run on the local agent sandbox.
They run as Cloud Run Jobs in project `max-vert` (us-central1), triggered by
Cloud Scheduler. Data lands in this repo's `data/` via git push from the job;
the site reads `raw.githubusercontent.com/snoberserker/max-vert-data/main/data/<feed>/latest.json`.

## Jobs

| Job | Schedule (America/Los_Angeles) | Image | What it runs |
|---|---|---|---|
| `maxvert-weather-2h` | every 2h at :10 | `weather-collector` | `collect_v2.py resort-forecast` (602 resorts, NWS) |
| `maxvert-snow-daily` | daily 06:15 | `snow-collector` | `collect_v2.py snow-all` (976 SNOTEL) + `collect.py daily` + `collect_traffic.py` + `collect_airfare.py` |

Failure semantics for the snow job: snow-all is fatal (nonzero exit → failure
alert); daily/traffic/airfare are non-fatal. Airfare is skipped entirely unless
the env var `TRAVELPAYOUTS_TOKEN` is set (not configured as of 2026-11-21).

Both jobs are 1 vCPU / 512 MiB / 15–30 min timeout / 1 retry. Collectors are
network-bound, so cost tracks CPU-seconds: roughly $1/month per 0.25 vCPU at
these cadences (~$5–8/month total for both).

## Layout

- `cloud/Dockerfile` + `cloud/run.sh` — weather job (2-hourly NWS forecast)
- `cloud/snow/Dockerfile` + `cloud/snow/run.sh` — nightly snow job

Both entrypoints shallow-clone this repo fresh at runtime (so `resorts.json`,
`snotel_stations.json`, and any collector changes take effect without an image
rebuild), run the collectors, then `git add data && git commit && git push` as
`maxvert-cloud-collector <agent@maxvert.dev>`, commit messages ending in
`[cloud-run]`. The GitHub token comes from Secret Manager secret
`max-vert-data-github-token` (env var `GITHUB_TOKEN`), never baked into the
image or echoed.

## Rebuild an image (only when Dockerfile/run.sh changes)

```bash
gcloud builds submit --project=max-vert --region=us-central1 \
  --tag us-central1-docker.pkg.dev/max-vert/maxvert-data/weather-collector:latest cloud
gcloud builds submit --project=max-vert --region=us-central1 \
  --tag us-central1-docker.pkg.dev/max-vert/maxvert-data/snow-collector:latest cloud/snow
```

## Operations

```bash
# manual run + wait (~7 min weather, ~12 min snow)
gcloud run jobs execute maxvert-weather-2h --project=max-vert --region=us-central1 --wait
gcloud run jobs execute maxvert-snow-daily --project=max-vert --region=us-central1 --wait

# scheduler jobs
gcloud scheduler jobs list --project=max-vert --location=us-central1

# recent run logs
gcloud logging read 'resource.type="cloud_run_job" AND resource.labels.job_name="maxvert-snow-daily"' \
  --project=max-vert --limit=25 --freshness=1h
```

Scheduler invokes the Run Jobs API with OAuth service account
`max-vert-agent@max-vert.iam.gserviceaccount.com`, which holds
`roles/run.invoker` and `roles/secretmanager.secretAccessor` (on the token
secret). Data pushes use the same GitHub token the local agent uses.

## Alerting

Cloud Monitoring (built-in, project `max-vert`):

- Log-based metrics `maxvert_weather_ok` (successful run: `PUSHED` or
  "No data changes" from either job) and `maxvert_weather_fail`
  (severity>=ERROR from either job). When adding a new cloud collector, widen
  both metric filters with another `OR resource.labels.job_name="..."`.
- Two alert policies on those metrics, both routing to the email notification
  channel (tobrien@discursive.com):
  - "Max Vert weather collector run failed" — immediate failure alert
  - "Max Vert weather collector silent >6h (dead man)" — absence alert;
    catches the scheduler-stop-firing case that a failure-only alert misses

Belt-and-suspenders: a local Hermes cron (`maxvert-weather-deadman`, every 2h
at :40) checks GitHub for stale commits — weather `[cloud-run]` commit must be
<3h old, `Snow data` commit <26h old — and pings the owner's chat only when
stale, silent when healthy.

## Local jobs retired

The agent-sandbox cron jobs of the same names (`maxvert-weather-2h`,
`maxvert-snow-daily`) are paused, not deleted, as of 2026-11-21 — they are the
rollback path if GCP ever needs to be backed out.

## What still runs on the agent (by design)

Model-driven jobs that a container cannot do: nightly ski news digest
(`ski-news-nightly`), daily news script + blog post authoring/illustration/
deploy (`ski-snowboard-news-daily`, `maxvert-blog-daily`), weekly GA4 growth
measurement (`maxvert-weekly-measure`), weekly search trends
(`maxvert-trends-weekly`, needs the local pytrends install), and the dead-man
checker. See the `maxvert-data-feeds` skill for the full pipeline reference.
