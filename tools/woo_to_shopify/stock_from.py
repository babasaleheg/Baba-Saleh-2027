"""Show staff where the stock for each item of an order is, on the order page.

Writes the order metafield $app:babasaleh.stock_from ("Stock from", pinned, read-only for staff):
one line per item with what October Branch holds (website orders are fulfilled only from October,
CLAUDE.md rules 8 and 10; other branches are never shown, so staff don't take stock from them), e.g.
    Track 3D Slip Swimsuit - Green / M ×1: October Branch 3
    Venum Headguard ×1: not in stock at October Branch
Open (not yet fulfilled) orders of the last 30 days are refreshed on every run, so the note follows
stock moves until the order ships; fulfilled and cancelled orders keep their last note (or get none).

    python3 stock_from.py            # runs nightly (daily.sh); safe to run any time
    python3 stock_from.py --dry-run
"""
import sys
from datetime import datetime, timedelta, timezone

from sync import gql, log

NS, KEY = "$app:babasaleh", "stock_from"   # app-owned: staff see it but can't edit it
DRY = "--dry-run" in sys.argv
OPEN = {"UNFULFILLED", "PARTIALLY_FULFILLED", "ON_HOLD", "IN_PROGRESS", "OPEN", "PENDING_FULFILLMENT", "SCHEDULED"}
OCTOBER = "95443550256"  # October Branch: the only location website orders are fulfilled from

DEFINE = """mutation($d: MetafieldDefinitionInput!) { metafieldDefinitionCreate(definition: $d) {
  createdDefinition { id } userErrors { code message } } }"""
SET = """mutation($m: [MetafieldsSetInput!]!) { metafieldsSet(metafields: $m) { userErrors { field message } } }"""
ORDERS_Q = """query($a: String, $q: String) { orders(first: 25, after: $a, query: $q) { pageInfo { hasNextPage endCursor }
  nodes { id name cancelledAt displayFulfillmentStatus note: metafield(namespace: "$app:babasaleh", key: "stock_from") { value }
    lineItems(first: 50) { nodes { name quantity variant { inventoryItem { tracked
      inventoryLevels(first: 20) { nodes { location { id } quantities(names: ["on_hand"]) { quantity } } } } } } } } } }"""


def line(li):
    head = f"{li['name']} ×{li['quantity']}"
    item = (li["variant"] or {}).get("inventoryItem")
    if not item:
        return f"{head}: product deleted"
    if not item["tracked"]:
        return f"{head}: stock not tracked"
    n = next((lvl["quantities"][0]["quantity"] if lvl["quantities"] else 0 for lvl in item["inventoryLevels"]["nodes"]
              if lvl["location"]["id"].split("/")[-1] == OCTOBER), 0)
    return f"{head}: October Branch {n}" if n > 0 else f"{head}: not in stock at October Branch"


def main():
    if not DRY:
        errs = gql(DEFINE, {"d": {"name": "Stock from", "namespace": NS, "key": KEY, "type": "multi_line_text_field",
                                  "ownerType": "ORDER", "pin": True, "access": {"admin": "MERCHANT_READ"},
                                  "description": "Pieces of each item on hand at October Branch, for staff"}}
                   )["metafieldDefinitionCreate"]["userErrors"]
        if errs and not any(e["code"] == "TAKEN" for e in errs):
            log("definition", errs)
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows, after, stats = [], None, {"orders": 0, "set": 0, "failed": 0}
    while True:
        page = gql(ORDERS_Q, {"a": after, "q": f"processed_at:>'{since}'"})["orders"]
        for o in page["nodes"]:
            stats["orders"] += 1
            if o["cancelledAt"] or o["displayFulfillmentStatus"] not in OPEN:
                continue  # shipped or cancelled: keep the note it had (if any)
            value = "\n".join(line(li) for li in o["lineItems"]["nodes"])
            if value and value != (o["note"] or {}).get("value"):
                rows.append((o["id"], o["name"], value))
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    for _, name, v in rows[:3]:
        log("example", name, v.replace("\n", " | "))
    for i in range(0, len(rows), 25):
        batch = [{"ownerId": oid, "namespace": NS, "key": KEY, "type": "multi_line_text_field", "value": v}
                 for oid, _, v in rows[i:i + 25]]
        if not DRY:
            errs = gql(SET, {"m": batch})["metafieldsSet"]["userErrors"]
            if errs:
                log("metafieldsSet", errs[:3])
                stats["failed"] += len(batch)
                continue
        stats["set"] += len(batch)
    log("stock-from", stats)


if __name__ == "__main__":
    main()
