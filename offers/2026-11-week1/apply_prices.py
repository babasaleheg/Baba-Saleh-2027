"""Week-1 November offer prices: python3 apply_prices.py [--dry-run | --revert]

Apply: saves every variant's current price / compareAtPrice to originals.json (only if that file
doesn't exist yet, so a second run can't overwrite the real originals with sale prices), then sets
price = PDF sale price and compareAtPrice = PDF old price (rules.json). Variants whose sale price
isn't below the old price are left alone. --revert puts originals.json back.
"""
import json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools", "woo_to_shopify"))
from sync import gql, log

HERE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(HERE, "originals.json")
DRY = "--dry-run" in sys.argv
VARIANTS_Q = """query($id: ID!) { product(id: $id) { title variants(first: 100) { nodes { id title price compareAtPrice } } } }"""
UPDATE = """mutation($p: ID!, $v: [ProductVariantsBulkInput!]!) { productVariantsBulkUpdate(productId: $p, variants: $v) {
  userErrors { field message } } }"""


def target(rule, title):
    if "price" in rule:
        return rule["price"]
    parts = [x.strip() for x in title.split("/")]
    for part in parts:
        if part in rule["sizes"]:
            return rule["sizes"][part]
    return rule["sizes"].get("*")


def apply():
    rules = json.load(open(os.path.join(HERE, "rules.json")))["products"]
    have_orig = os.path.exists(ORIG)
    originals = json.load(open(ORIG)) if have_orig else {}
    changed = skipped = 0
    for r in rules:
        pid = f"gid://shopify/Product/{r['id']}"
        p = gql(VARIANTS_Q, {"id": pid})["product"]
        if not p:
            log("missing product", r["h"]); continue
        updates = []
        for v in p["variants"]["nodes"]:
            if not have_orig:
                originals.setdefault(pid, []).append({"id": v["id"], "price": v["price"], "compareAtPrice": v["compareAtPrice"]})
            t = target(r, v["title"])
            if not t or t[1] >= t[0]:
                skipped += 1; continue
            updates.append({"id": v["id"], "price": str(t[1]), "compareAtPrice": str(t[0])})
        if updates and not DRY:
            errs = gql(UPDATE, {"p": pid, "v": updates})["productVariantsBulkUpdate"]["userErrors"]
            if errs:
                log("errors", p["title"], errs)
        changed += len(updates)
        if updates[:1]:
            log(p["title"], "->", updates[0]["price"], "was", next(v["price"] for v in p["variants"]["nodes"] if v["id"] == updates[0]["id"]))
    if not have_orig and not DRY:
        json.dump(originals, open(ORIG, "w"), indent=1)
    log(f"offer prices {'(dry run) ' if DRY else ''}{{'variants set': {changed}, 'skipped': {skipped}, 'products': {len(rules)}}}")


def revert():
    originals = json.load(open(ORIG))
    n = 0
    for pid, variants in originals.items():
        v = [{"id": x["id"], "price": x["price"], "compareAtPrice": x["compareAtPrice"]} for x in variants]
        if not DRY:
            errs = gql(UPDATE, {"p": pid, "v": v})["productVariantsBulkUpdate"]["userErrors"]
            if errs:
                log("errors", pid, errs)
        n += len(v)
    log(f"offer prices reverted {'(dry run) ' if DRY else ''}{n} variants")


if __name__ == "__main__":
    revert() if "--revert" in sys.argv else apply()
