"""Show the customer's earlier orders in the order's Note, so staff see them in the phone app.

The phone app doesn't show order metafields, but it shows the Note. Below the customer's own
note (kept as is, on top) this adds, only for returning customers:

    Previous orders:
    #3289 · 31 Oct 2026 · EGP 435 · Shipped
      1× Track 3D Slip Swimsuit - Green / M

(from the read-only "Previous orders" field written by came_from.py). It also fills "Came from"
and "Visit details" under the order's Additional details, which the phone app shows too. That part is rewritten on
every run; first orders get nothing. Orders of the last 30 days are kept up to date.

    python3 order_note.py            # hourly and nightly, after came_from.py
    python3 order_note.py --dry-run
"""
import re, sys
from datetime import datetime, timedelta, timezone

from sync import gql, log

DRY = "--dry-run" in sys.argv
MARK = "Previous orders:"
OLD_MARK = "── Baba Saleh info (updated automatically) ──"  # earlier, longer version (removed)
LIMIT = 3000
Q = """query($a: String, $q: String) { orders(first: 50, after: $a, query: $q, reverse: true) { pageInfo { hasNextPage endCursor }
  nodes { id name note customAttributes { key value }
    notes: metafields(first: 10, namespace: "$app:babasaleh") { nodes { key value } } } } }"""
UPDATE = """mutation($i: OrderInput!) { orderUpdate(input: $i) { userErrors { message } } }"""


def section(prev):
    if not prev or prev.startswith(("None", "No customer")):
        return ""
    text = MARK + "\n" + prev
    if len(text) > LIMIT:
        text = text[:LIMIT].rsplit("\n#", 1)[0]
    return text


def additional_details(m):
    """The two lines shown under "Additional details" on the order (also in the phone app):
    Came from      Facebook ad, then ordered from an Instagram link
    Visit details  Landed on Vests collection; ordered 17 days later; 4 visits; first order"""
    out = {}
    came = m.get("came_from")
    if came:
        came = re.sub(r"Google (search|app|)\s*– sag_organic", "Google Shopping (free listing)", came)
        came = came.replace(" · then came back directly", ", then came back directly")
        out["Came from"] = re.sub(r" · then came back via (.+)$", r", then ordered from \1", came)
    parts = []
    if m.get("landing_page"):
        page = m["landing_page"]
        parts.append("Landed on the home page" if page.lower().startswith("home page") else "Landed on " + page)
    if m.get("time_to_order"):
        parts.append("ordered " + m["time_to_order"].replace(" after the first visit", " later"))
    if m.get("visits"):
        parts.append(m["visits"])
    if m.get("customer_order"):
        parts.append("first order" if m["customer_order"] == "1st order" else m["customer_order"])
    if parts:
        out["Visit details"] = "; ".join(parts)
    return out


def main():
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stats, after = {"orders": 0, "updated": 0, "failed": 0}, None
    while True:
        page = gql(Q, {"a": after, "q": f"created_at:>'{since}' AND -source_name:woocommerce"})["orders"]
        for o in page["nodes"]:
            stats["orders"] += 1
            old = (o["note"] or "").rstrip()
            own = old.split(OLD_MARK)[0].split(MARK)[0].rstrip()  # the customer's / staff's own note
            m = {x["key"]: x["value"] for x in o["notes"]["nodes"]}
            note = "\n\n".join(x for x in (own, section(m.get("previous_orders"))) if x)
            attrs = {a["key"]: a["value"] for a in o["customAttributes"]}
            want = {**attrs, **additional_details(m)}
            if note == old and want == attrs:
                continue
            if stats["updated"] < 2:
                log("example", o["name"], note.replace("\n", " | ")[:300])
            if not DRY:
                inp = {"id": o["id"], "note": note}
                if want != attrs:
                    inp["customAttributes"] = [{"key": k, "value": v} for k, v in want.items()]
                errs = gql(UPDATE, {"i": inp})["orderUpdate"]["userErrors"]
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
