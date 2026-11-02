"""Put the staff order notes into the order's Note, so they show in the Shopify phone app too.

The phone app doesn't show order metafields, but it shows the Note. Below the customer's own
note (kept as is, on top) this writes a section built from the read-only $app:babasaleh fields
(came_from.py, stock_from.py):

    ── Baba Saleh info (updated automatically) ──
    Came from: Google search · 3rd order · 6 visits
    Stock from:
      Track 3D Slip Swimsuit - Green / M ×1: October Branch 3
    Previous orders:
      #3289 · 31 Oct 2026 · EGP 435 · Shipped · Paid
      ...

Everything below the line is rewritten on every run, so edits there don't stick. Orders of the
last 30 days are kept up to date.

    python3 order_note.py            # hourly and nightly, after came_from.py and stock_from.py
    python3 order_note.py --dry-run
"""
import sys
from datetime import datetime, timedelta, timezone

from sync import gql, log

DRY = "--dry-run" in sys.argv
MARK = "── Baba Saleh info (updated automatically) ──"
LIMIT = 4500  # keep the note a readable length; the newest previous orders come first
Q = """query($a: String, $q: String) { orders(first: 50, after: $a, query: $q, reverse: true) { pageInfo { hasNextPage endCursor }
  nodes { id name note metafields(first: 10, namespace: "$app:babasaleh") { nodes { key value } } } } }"""
UPDATE = """mutation($i: OrderInput!) { orderUpdate(input: $i) { userErrors { message } } }"""


def section(m):
    head = [m.get("came_from"), m.get("customer_order"), m.get("visits")]
    lines = [MARK]
    if any(head):
        lines.append("Came from: " + " · ".join(x for x in head if x))
    if m.get("stock_from"):
        lines += ["Stock from:"] + ["  " + x for x in m["stock_from"].splitlines()]
    if m.get("previous_orders"):
        lines += ["Previous orders:"] + ["  " + x if x else "" for x in m["previous_orders"].splitlines()]
    text = "\n".join(lines)
    if len(text) > LIMIT:
        text = text[:LIMIT].rsplit("\n\n", 1)[0] + "\n  … (older orders: tap the customer)"
    return text if len(lines) > 1 else ""


def main():
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stats, after = {"orders": 0, "updated": 0, "failed": 0}, None
    while True:
        page = gql(Q, {"a": after, "q": f"created_at:>'{since}' AND -source_name:woocommerce"})["orders"]
        for o in page["nodes"]:
            stats["orders"] += 1
            m = {x["key"]: x["value"] for x in o["metafields"]["nodes"]}
            own = (o["note"] or "").split(MARK)[0].rstrip()  # the customer's / staff's own note
            info = section(m)
            note = "\n\n".join(x for x in (own, info) if x)
            if note == (o["note"] or "").rstrip():
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
