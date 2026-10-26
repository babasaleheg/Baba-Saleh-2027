"""Arabic product and page descriptions (so Arabic pages never show English text).

    python3 ar_descriptions.py export [N]   # write the products/pages whose Arabic description is
                                            # missing or outdated to $DATA_DIR/ar_todo_<k>.json,
                                            # N per file (default 100); prints the files
    python3 ar_descriptions.py apply FILE…  # FILE: {"<resource id>": "<Arabic HTML>", ...}

The nightly runs "export"; whoever reviews the night (the nightly assistant) writes the Arabic
for each file and runs "apply". Keep the same HTML structure (paragraphs, lists) as the English.
"""
import json, os, sys
from collections import Counter

from seo_bilingual import register, resources, resources_by_id
from sync import log

D = os.environ.get("DATA_DIR", "woo_data")


def todo():
    out = []
    for kind in ("PRODUCT", "PAGE"):
        for rid, r in resources(kind).items():
            body = (r["content"].get("body_html") or ("",))[0]
            if not body or not body.strip():
                continue
            ar = r["ar"].get("body_html")
            if not ar or not ar[0] or ar[1]:
                out.append({"id": rid, "title": (r["content"].get("title") or ("",))[0],
                            "ar_title": (r["ar"].get("title") or ("",))[0], "body_html": body})
    return out


def export(per_file):
    for f in os.listdir(D):
        if f.startswith("ar_todo_") and f.endswith(".json"):
            os.remove(os.path.join(D, f))
    items = todo()
    files = []
    for i in range(0, len(items), per_file):
        path = os.path.join(D, f"ar_todo_{i // per_file + 1}.json")
        json.dump(items[i:i + per_file], open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        files.append(path)
    print("\n".join(files))
    log(f"ar-descriptions to write: {len(items)} in {len(files)} file(s)")


def apply(paths):
    data = {}
    for path in paths:
        data.update(json.load(open(path, encoding="utf-8")))
    ids = list(data)
    st = Counter()
    for i in range(0, len(ids), 200):
        res = resources_by_id(ids[i:i + 200])  # fresh digests
        for rid in ids[i:i + 200]:
            if rid in res and data[rid].strip():
                register(rid, res[rid], {"body_html": data[rid]}, st, force=("body_html",))
    log(f"ar-descriptions applied {dict(st)} of {len(ids)}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "apply":
        apply(sys.argv[2:])
    else:
        export(int(sys.argv[2]) if len(sys.argv) > 2 else 100)
