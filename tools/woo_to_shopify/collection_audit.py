"""Check that every collection only holds the categories its rules are meant for.

A product in the wrong collection (e.g. a swimsuit in Sportswear) usually means a leftover
tag or product type that a rule matches on. categorize.py fixes the product side every night;
this check catches whatever is left, including rules that are too broad, and adds the list
to quality_report.json ("collection_leaks") for the nightly summary.

    python3 collection_audit.py
Collections that pick by audience (for:), price, sale or "all" are not checked.
"""
import json, os

from categorize import TAX, TYPE_CAT
from sync import gql, log

D = os.environ.get("DATA_DIR", "woo_data")
REPORT = os.path.join(D, "quality_report.json")

COLLECTIONS_Q = """{ collections(first: 250) { nodes { handle title ruleSet { rules { column relation condition } } } } }"""
MEMBERS_Q = """query($h: String!, $a: String) { collectionByHandle(handle: $h) { products(first: 250, after: $a) {
  pageInfo { hasNextPage endCursor } nodes { title status tags } } } }"""


def allowed_cats(rules):
    """Categories a collection's rules mean to include; None = not a category collection."""
    allowed = set()
    for r in rules:
        col, rel, cond = r["column"], r["relation"], r["condition"]
        if rel != "EQUALS":
            return None
        if col == "TAG" and cond.startswith("for:"):
            return None
        if col == "TAG" and cond.startswith("cat:"):
            allowed.add(cond)
        elif col == "TAG" and cond.startswith(("dept:", "group:")):
            allowed |= {cat for cat, v in TAX.items() if cond in v["tags"]}
        elif col == "TYPE" and cond in TYPE_CAT:
            allowed.add(TYPE_CAT[cond])
        elif col == "TAG" and cond.startswith("x:"):
            continue  # extra sections (balls, gloves, home workout): any category
        else:
            return None
    return allowed or None


def members(handle):
    out, after = [], None
    while True:
        page = gql(MEMBERS_Q, {"h": handle, "a": after})["collectionByHandle"]["products"]
        out += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return out
        after = page["pageInfo"]["endCursor"]


def main():
    leaks = {}
    checked = 0
    for c in gql(COLLECTIONS_Q)["collections"]["nodes"]:
        if not c["ruleSet"]:
            continue
        rules = c["ruleSet"]["rules"]
        allowed = allowed_cats(rules)
        if allowed is None or any(r["condition"].startswith("x:") for r in rules) and len(rules) == 1:
            continue
        checked += 1
        bad = []
        for p in members(c["handle"]):
            if p["status"] != "ACTIVE":
                continue
            cats = [t for t in p["tags"] if t.startswith("cat:")]
            if len(cats) != 1 or cats[0] not in allowed:
                bad.append(f'{p["title"]} ({", ".join(cats) or "no category"})')
        if bad:
            leaks[c["handle"]] = bad
            log(f"{c['handle']}: {len(bad)} product(s) that don't belong: {bad[:5]}")
    report = {}
    if os.path.exists(REPORT):
        report = json.load(open(REPORT, encoding="utf-8"))
    report["collection_leaks"] = leaks
    json.dump(report, open(REPORT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"collection-audit {{'collections checked': {checked}, 'with leaks': {len(leaks)}}}")


if __name__ == "__main__":
    main()
