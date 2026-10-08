"""Download every WooCommerce variation from the public Store API.

Usage: python3 -I fetch_variations.py <raw_dir>
Skips variations already saved, so it can be re-run until complete.
"""
import concurrent.futures as cf
import json
import os
import subprocess
import sys

RAW = sys.argv[1]
OUT = os.path.join(RAW, "variations")
API = "https://babasaleh.com/wp-json/wc/store/v1/products/"


def fetch(vid):
    path = os.path.join(OUT, f"{vid}.json")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return vid, True
    for _ in range(4):
        try:
            r = subprocess.run(
                ["curl", "-sS", "--max-time", "30", "--connect-timeout", "10", API + vid],
                capture_output=True, timeout=45,
            )
        except subprocess.TimeoutExpired:
            continue
        body = r.stdout.decode("utf-8", "replace")
        i = body.find("{")
        if i < 0:
            continue
        try:
            data = json.loads(body[i:])
        except ValueError:
            continue
        if "id" in data:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            return vid, True
    return vid, False


os.makedirs(OUT, exist_ok=True)
ids = open(os.path.join(RAW, "var_ids.txt")).read().split()
failed = []
with cf.ThreadPoolExecutor(6) as ex:
    for n, (vid, ok) in enumerate(ex.map(fetch, ids), 1):
        if not ok:
            failed.append(vid)
        if n % 200 == 0:
            print(n, "done", len(failed), "failed", flush=True)
print("total", len(ids), "failed", failed)
