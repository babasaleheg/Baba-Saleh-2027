"""No product is ever on sale at EGP 0 (owner's rule): any active product with a variant priced 0
is set to Draft, and listed in quality_report.json ("drafted_zero_price") for the nightly summary.
It goes live again only when someone gives it a real price and activates it.

    python3 zero_price.py            # runs nightly (daily.sh); safe to run any time
    python3 zero_price.py --dry-run
"""
import json, os, sys

from sync import gql, log

D = os.environ.get("DATA_DIR", "woo_data")
REPORT = os.path.join(D, "quality_report.json")
DRY = "--dry-run" in sys.argv
PRODUCTS_Q = """query($a: String) { products(first: 250, after: $a, query: "status:active") {
  pageInfo { hasNextPage endCursor } nodes { id title variants(first: 100) { nodes { price } } } } }"""
DRAFT = """mutation($p: ProductUpdateInput!) { productUpdate(product: $p) { product { status } userErrors { message } } }"""


def main():
    zero, after = [], None
    while True:
        page = gql(PRODUCTS_Q, {"a": after})["products"]
        zero += [p for p in page["nodes"] if any(float(v["price"] or 0) <= 0 for v in p["variants"]["nodes"])]
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    drafted = []
    for p in zero:
        if not DRY:
            errs = gql(DRAFT, {"p": {"id": p["id"], "status": "DRAFT"}})["productUpdate"]["userErrors"]
            if errs:
                log("could not draft", p["title"], errs)
                continue
        drafted.append(p["title"])
        log(f"{'would draft' if DRY else 'drafted'} (price 0): {p['title']}")
    if not DRY:
        report = json.load(open(REPORT, encoding="utf-8")) if os.path.exists(REPORT) else {}
        report["drafted_zero_price"] = drafted
        json.dump(report, open(REPORT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"zero-price {{'drafted': {len(drafted)}}}")


if __name__ == "__main__":
    main()
