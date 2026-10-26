"""Real "sold in the last 30 days" numbers for the product page badge.

Counts units sold per product in orders placed in the last 30 days (by order date, so imported
old orders are not counted; cancelled orders left out) and
stores the number in the product metafield babasaleh.sold_30d; products that sold nothing
are reset to 0. The theme shows "Sold N times in the last 30 days" only from 5 up. Runs nightly.

    python3 sold_counter.py
"""
from collections import Counter
from datetime import datetime, timedelta, timezone

from sync import gql, log

ORDERS_Q = """query($a: String, $q: String) { orders(first: 100, after: $a, query: $q) { pageInfo { hasNextPage endCursor }
  nodes { cancelledAt lineItems(first: 100) { nodes { quantity product { id } } } } } }"""
CURRENT_Q = """query($a: String) { products(first: 250, after: $a) { pageInfo { hasNextPage endCursor }
  nodes { id metafield(namespace: "babasaleh", key: "sold_30d") { value } } } }"""
DEFINE = """mutation($d: MetafieldDefinitionInput!) { metafieldDefinitionCreate(definition: $d) {
  createdDefinition { id } userErrors { code message } } }"""
SET = """mutation($m: [MetafieldsSetInput!]!) { metafieldsSet(metafields: $m) { userErrors { field message } } }"""


def main():
    gql(DEFINE, {"d": {"name": "Sold in the last 30 days", "namespace": "babasaleh", "key": "sold_30d",
                       "type": "number_integer", "ownerType": "PRODUCT", "access": {"storefront": "PUBLIC_READ"},
                       "description": "Units sold in the last 30 days (sold_counter.py, nightly)"}})
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    sold, after = Counter(), None
    while True:
        page = gql(ORDERS_Q, {"a": after, "q": f"processed_at:>'{since}'"})["orders"]
        for o in page["nodes"]:
            if o["cancelledAt"]:
                continue
            for li in o["lineItems"]["nodes"]:
                if li["product"]:
                    sold[li["product"]["id"]] += li["quantity"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    current, after = {}, None
    while True:
        page = gql(CURRENT_Q, {"a": after})["products"]
        for p in page["nodes"]:
            current[p["id"]] = int((p["metafield"] or {}).get("value") or 0)
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    changes = [{"ownerId": pid, "namespace": "babasaleh", "key": "sold_30d", "type": "number_integer", "value": str(sold.get(pid, 0))}
               for pid, have in current.items() if have != sold.get(pid, 0)]
    for i in range(0, len(changes), 25):
        errs = gql(SET, {"m": changes[i:i + 25]})["metafieldsSet"]["userErrors"]
        if errs:
            log("sold-counter errors", errs[:3])
    log(f"sold-counter {{'products sold': {len(sold)}, '5+ sold': {sum(1 for v in sold.values() if v >= 5)}, 'updated': {len(changes)}}}")


if __name__ == "__main__":
    main()
