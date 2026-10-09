"""
Export every API response the website needs as static JSON files.

Why this exists: the API runs on Render's free tier, which goes to sleep
after 15 minutes without visitors and takes up to a minute to wake. The
data itself only changes when a pipeline script is run, so instead of the
website asking a (possibly sleeping) server on every visit, this script
saves the answers once, into the frontend's public folder. Vercel then
serves them as plain files, instantly.

It doesn't re-implement any queries: it calls the exact same functions the
API's endpoints use (they're ordinary Python functions underneath the
@app.get decorators), so the files are byte-for-byte the same data the API
would have returned.

Writes, under web/public/data/:
    states.json               <- GET /api/states
    metrics.json              <- GET /api/metrics
    metrics/<slug>.json       <- GET /api/metrics/<slug>, one per metric
    states/<CODE>.json        <- GET /api/states/<CODE>, one per state

Run it after any pipeline script, then commit and push:
    cd api
    python3 export_static.py
"""

import json
import shutil
from pathlib import Path

from database import pool
from main import list_metrics, list_states, metric_map, state_profile

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "web" / "public" / "data"


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    # default=str covers any value JSON can't store natively (e.g. a date),
    # turning it into text instead of crashing.
    path.write_text(json.dumps(data, default=str, separators=(",", ":")), encoding="utf-8")


def main():
    # Start from an empty folder, so a metric or state that no longer has
    # data doesn't leave an old file behind.
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)

    states = list_states()
    write_json(OUTPUT_DIR / "states.json", states)

    metrics = list_metrics()
    write_json(OUTPUT_DIR / "metrics.json", metrics)

    for m in metrics:
        write_json(OUTPUT_DIR / "metrics" / f"{m['slug']}.json", metric_map(m["slug"]))

    for s in states:
        write_json(OUTPUT_DIR / "states" / f"{s['code']}.json", state_profile(s["code"]))

    files = list(OUTPUT_DIR.rglob("*.json"))
    total_kb = sum(f.stat().st_size for f in files) / 1024
    print(f"Wrote {len(files)} files ({total_kb:.0f} KB) to {OUTPUT_DIR}")
    print(f"  {len(metrics)} metrics, {len(states)} states")
    print("Next: commit and push web/public/data so the live site picks them up.")


if __name__ == "__main__":
    try:
        main()
    finally:
        # Close the database connections before exiting. Without this,
        # Python waits on the pool's background threads at exit and prints
        # "couldn't stop thread" warnings (harmless, but noisy).
        pool.close()
