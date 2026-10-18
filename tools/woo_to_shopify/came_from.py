"""Show where each order came from (Google, Instagram, ChatGPT, direct...) on the order page.

Writes the order metafield babasaleh.came_from ("Came from", pinned so it shows on the order
page) and the same on the draft orders that hold cancelled WooCommerce orders.

    python3 came_from.py            # new Shopify orders (from Shopify's visit tracking)
    python3 came_from.py --woo      # also past WooCommerce orders (from Woo's order attribution)
    python3 came_from.py --dry-run

Orders that already have a value are left alone, so it is safe to run every night.
"""
import json, os, sys

from sync import gql, log

D = os.environ.get("DATA_DIR", "woo_data")
NS, KEY = "babasaleh", "came_from"
DRY = "--dry-run" in sys.argv

DEFINE = """mutation($d: MetafieldDefinitionInput!) { metafieldDefinitionCreate(definition: $d) {
  createdDefinition { id } userErrors { code message } } }"""
SET = """mutation($m: [MetafieldsSetInput!]!) { metafieldsSet(metafields: $m) { userErrors { field message } } }"""
ORDERS_Q = """query($a: String) { orders(first: 100, after: $a, reverse: true) { pageInfo { hasNextPage endCursor }
  nodes { id name came: metafield(namespace: "babasaleh", key: "came_from") { value }
    customerJourneySummary { ready
      firstVisit { source sourceType referrerUrl utmParameters { source medium campaign } }
      lastVisit { source sourceType referrerUrl utmParameters { source medium campaign } } } } } }"""
HAS_Q = """query($ids: [ID!]!) { nodes(ids: $ids) { id ... on Order { came: metafield(namespace: "babasaleh", key: "came_from") { value } }
  ... on DraftOrder { came: metafield(namespace: "babasaleh", key: "came_from") { value } } } }"""

NAMES = [  # (text found in the source / referrer, label), most specific first
    ("googlequicksearchbox", "Google app"), ("com.google.android.gm", "Gmail"), ("mail.google", "Gmail"),
    ("chatgpt", "ChatGPT"), ("openai", "ChatGPT"), ("perplexity", "Perplexity"), ("gemini", "Gemini"),
    ("instagram", "Instagram"), ("ig", "Instagram"), ("facebook", "Facebook"), ("fb", "Facebook"),
    ("tiktok", "TikTok"), ("youtube", "YouTube"), ("linktr.ee", "Linktree"), ("wl.co", "WhatsApp"),
    ("whatsapp", "WhatsApp"), ("wa.me", "WhatsApp"), ("bing", "Bing"), ("brave", "Brave search"),
    ("yahoo", "Yahoo"), ("duckduckgo", "DuckDuckGo"), ("google", "Google"),
]
PAID = {"cpc", "ppc", "paid", "paid_social", "paidsocial", "ads", "ad", "display", "paid-social"}


def label(source, kind=None, medium=None, campaign=None):
    """A short, human name for a traffic source."""
    s = (source or "").strip().lower()
    kind = (kind or "").lower()
    if not s or s in {"(direct)", "direct", "typein", "(none)"}:
        return "Direct"
    name = next((n for k, n in NAMES if (s == k if len(k) <= 2 else k in s)), source.strip())
    if name == "Google":
        name = "Google search" if kind in {"organic", "seo", ""} and (medium or "").lower() not in PAID else "Google"
    if (medium or "").lower() in PAID or kind in {"sem", "paid"}:
        name += " ad"
    if campaign and not campaign.isdigit() and campaign.lower() not in {"google_cpc", "(not set)"}:
        name += f" – {campaign}"  # Meta ad ids are just numbers: leave them out
    return name


def ensure_definitions():
    for owner in ("ORDER", "DRAFTORDER"):
        d = {"name": "Came from", "namespace": NS, "key": KEY, "type": "single_line_text_field", "ownerType": owner,
             "description": "Where the customer came from before ordering (Google, Instagram, ChatGPT, direct...)", "pin": True}
        if DRY:
            continue
        errs = gql(DEFINE, {"d": d})["metafieldDefinitionCreate"]["userErrors"]
        if errs and not any(e["code"] == "TAKEN" for e in errs):
            log("definition", owner, errs)


def write(rows, stats):
    for i in range(0, len(rows), 25):
        batch = [{"ownerId": oid, "namespace": NS, "key": KEY, "type": "single_line_text_field", "value": v[:255]}
                 for oid, v in rows[i:i + 25]]
        if not DRY:
            errs = gql(SET, {"m": batch})["metafieldsSet"]["userErrors"]
            if errs:
                log("metafieldsSet", errs)
                stats["failed"] += len(batch)
                continue
        stats["set"] += len(batch)


def visit_label(v):
    if not v:
        return None
    utm = v.get("utmParameters") or {}
    return label(utm.get("source") or v.get("source") or v.get("referrerUrl"), v.get("sourceType"), utm.get("medium"), utm.get("campaign"))


def shopify_orders(stats):
    rows, after = [], None
    while True:
        page = gql(ORDERS_Q, {"a": after})["orders"]
        for o in page["nodes"]:
            if o["came"]:
                continue
            j = o["customerJourneySummary"]
            if j is None or not j["ready"]:
                continue  # Shopify hasn't worked it out yet (or the order wasn't placed online); try tomorrow
            first, last = visit_label(j["firstVisit"]), visit_label(j["lastVisit"])
            value = first or last or "Unknown (no visit recorded)"
            if first and last and last != first:
                value += " · then came back directly" if last == "Direct" else f" · then came back via {last}"
            rows.append((o["id"], value))
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    stats["shopify_orders"] = len(rows)
    for oid, v in rows[:5]:
        log("example", oid.split("/")[-1], v)
    write(rows, stats)


def woo_orders(stats):
    done = json.load(open(f"{D}/orders_done.json"))
    rows = []
    for line in open(f"{D}/orders.ndjson"):
        o = json.loads(line)
        sid = done.get(str(o["id"]))
        if not sid:
            continue
        m = {x["key"].removeprefix("_wc_order_attribution_"): x["value"] for x in o.get("meta_data", []) if x["key"].startswith("_wc_order_attribution_")}
        if not m:
            value = "Unknown (old website, not recorded)"
        else:
            src = m.get("utm_source") if m.get("source_type") == "utm" else (m.get("utm_source") or m.get("referrer"))
            value = label(src, m.get("source_type"), m.get("utm_medium"), m.get("utm_campaign"))
            if m.get("device_type"):
                value += f" · {m['device_type'].lower()}"
        rows.append((sid, value))
    # skip ones that already have a value
    have = set()
    for i in range(0, len(rows), 250):
        for n in gql(HAS_Q, {"ids": [r[0] for r in rows[i:i + 250]]})["nodes"]:
            if n and n.get("came"):
                have.add(n["id"])
    rows = [r for r in rows if r[0] not in have]
    stats["woo_orders"] = len(rows)
    write(rows, stats)


def main():
    stats = {"set": 0, "failed": 0}
    ensure_definitions()
    if "--woo" in sys.argv:
        woo_orders(stats)
    shopify_orders(stats)
    log("came-from", stats)


if __name__ == "__main__":
    main()
