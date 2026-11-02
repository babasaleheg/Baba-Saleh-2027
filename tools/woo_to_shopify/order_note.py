"""Show the customer's earlier orders in the order's Note, so staff see them in the phone app.

The phone app doesn't show order metafields, but it shows the Note. Below the customer's own
note (kept as is, on top) this adds, only for returning customers:

    Previous orders:
    #3289 · 31 Oct 2026 · EGP 435 · Shipped
      1× Track 3D Slip Swimsuit - Green / M

(from the read-only "Previous orders" field written by came_from.py). That part is rewritten on
every run; first orders get nothing. Orders of the last 30 days are kept up to date.

    python3 order_note.py            # hourly and nightly, after came_from.py
    python3 order_note.py --dry-run
"""
import sys
from datetime import datetime, timedelta, timezone

from sync import gql, log

DRY = "--dry-run" in sys.argv
MARK = "Previous orders:"
OLD_MARK = "── Baba Saleh info (updated automatically) ──"  # earlier, longer version (removed)
LIMIT = 3000
Q = """query($a: String, $q: String) { orders(first: 50, after: $a, query: $q, reverse: true) { pageInfo { hasNextPage endCursor }
  nodes { id name note prev: metafield(namespace: "$app:babasaleh", key: "previous_orders") { value } } } }"""
UPDATE = """mutation($i: OrderInput!) { orderUpdate(input: $i) { userErrors { message } } }"""


def section(prev):
    if not prev or prev.startswith(("None", "No customer")):
        return ""
    text = MARK + "\n" + prev
    if len(text) > LIMIT:
        text = text[:LIMIT].rsplit("\n#", 1)[0]
    return text


def main():
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stats, after = {"orders": 0, "updated": 0, "failed": 0}, None
    while True:
        page = gql(Q, {"a": after, "q": f"created_at:>'{since}' AND -source_name:woocommerce"})["orders"]
        for o in page["nodes"]:
            stats["orders"] += 1
            old = (o["note"] or "").rstrip()
            own = old.split(OLD_MARK)[0].split(MARK)[0].rstrip()  # the customer's / staff's own note
            note = "\n\n".join(x for x in (own, section((o["prev"] or {}).get("value"))) if x)
            if note == old:
                continue
            if stats["updated"] < 2:
                log("example", o["name"], note.replace("\n", " | ")[:300])
            if not DRY:
                errs = gql(UPDATE, {"i": {"id": o["id"], "note": note}})["orderUpdate"]["userErrors"]
                if errs:
                    log("orderUpdate", o["name"], errs)
                    stats["failed"] += 1
                    continue
            stats["updated"] += 1
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    log("order-note", stats)


if __name__ == "__main__":
    main()
