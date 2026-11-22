#!/usr/bin/env python3
"""Upload collected feed data to the GCS bucket (dual-write alongside git).

Usage: python3 gcs_upload.py <data-dir>
Uploads every file under <data-dir> to gs://$GCS_BUCKET preserving paths.
latest.json gets a short cache TTL (5 min); everything else 1 hour.
Prints UPLOADED <n> on success (the alert metrics watch for this string).
"""
import os, sys
from google.cloud import storage

def main():
    root = sys.argv[1]
    bucket_name = os.environ["GCS_BUCKET"]
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    n = 0
    for dirpath, _, files in os.walk(root):
        for fn in files:
            local = os.path.join(dirpath, fn)
            blob_path = os.path.relpath(local, root)
            ttl = 300 if fn == "latest.json" else 3600
            blob = bucket.blob(blob_path)
            blob.cache_control = f"public, max-age={ttl}"
            blob.upload_from_filename(local)
            n += 1
    print(f"UPLOADED {n} objects to gs://{bucket_name}")

if __name__ == "__main__":
    main()
