"""No product without a photo stays on the store (owner's rule 14, Nov 25 2026): every active or draft
product with no image is set to Archived and listed in quality_report.json ("archived_no_photo") for the
nightly summary. Stock is never touched (rule 8). Add a photo and set it back to Active to bring it back.

    python3 no_photo.py            # runs nightly (daily.sh); safe to run any time
    python3 no_photo.py --dry-run
"""
import json, os, sys

from sync import gql, log

D = os.environ.get("DATA_DIR", "woo_data")
REPORT = os.path.join(D, "quality_report.json")
DRY = "--dry-run" in sys.argv
Q = """query($a: String) { products(first: 250, after: $a, query: "status:active OR status:draft") {
  pageInfo { hasNextPage endCursor } nodes { id title status mediaCount { count } } } }"""
ARCHIVE = """mutation($p: ProductUpdateInput!) { productUpdate(product: $p) { product { status } userErrors { message } } }"""


def main():
    found, after = [], None
    while True:
        page = gql(Q, {"a": after})["products"]
        found += [p for p in page["nodes"] if p["mediaCount"]["count"] == 0]
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    archived = []
    for p in found:
        if not DRY:
            errs = gql(ARCHIVE, {"p": {"id": p["id"], "status": "ARCHIVED"}})["productUpdate"]["userErrors"]
            if errs:
                log("could not archive", p["title"], errs)
                continue
        archived.append(p["title"])
        log(f"{'would archive' if DRY else 'archived'} (no photo, was {p['status'].lower()}): {p['title']}")
    if not DRY:
        report = json.load(open(REPORT, encoding="utf-8")) if os.path.exists(REPORT) else {}
        report["archived_no_photo"] = archived
        json.dump(report, open(REPORT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"no-photo {{'archived': {len(archived)}}}")


if __name__ == "__main__":
    main()
