"""Which colour each product photo shows, so the product page shows only the chosen colour's photos.

Writes the product metafield $app:babasaleh.media_colors (JSON, read by the theme's main-product
section) as {"<media id>": "<colour>"}. A photo belongs to a colour when:
  1. it is the photo of a variant of that colour (set in Shopify), or
  2. it is a copy of such a photo (same file name before the "_<id>" Shopify adds), or
  3. its alt text names exactly one of the colours, or
  4. it was checked by eye and listed in colour_labels.json ({"<handle>": {"<media id>": "<colour>" | "all"}}),
     which also corrects variants that point at another colour's photo.
Photos that match no colour clearly are left out: the page shows them with every colour (size charts,
details). Products where fewer than two colours have their own photo are left out: all photos show.

    python3 variant_images.py            # nightly (daily.sh): new and changed products
    python3 variant_images.py --all      # recompute every product
    python3 variant_images.py --dry-run --only <handle>
"""
import json, os, re, sys
from datetime import datetime, timedelta, timezone

from sync import gql, log

NS, KEY = "$app:babasaleh", "media_colors"
DRY, ALL = "--dry-run" in sys.argv, "--all" in sys.argv
ONLY = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
COLOR_NAMES = ("color", "colour", "اللون", "eyewear frame color")
LABELS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "colour_labels.json"))) \
    if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "colour_labels.json")) else {}

DEFINE = """mutation($d: MetafieldDefinitionInput!) { metafieldDefinitionCreate(definition: $d) {
  createdDefinition { id } userErrors { code message } } }"""
SET = """mutation($m: [MetafieldsSetInput!]!) { metafieldsSet(metafields: $m) { userErrors { field message } } }"""
DELETE = """mutation($m: [MetafieldIdentifierInput!]!) { metafieldsDelete(metafields: $m) { userErrors { message } } }"""
Q = """query($a: String, $q: String) { products(first: 20, after: $a, query: $q) { pageInfo { hasNextPage endCursor }
  nodes { id handle options { name values } mc: metafield(namespace: "$app:babasaleh", key: "media_colors") { value }
    media(first: 50) { nodes { id alt preview { image { url } } } }
    variants(first: 100) { nodes { selectedOptions { name value } media(first: 1) { nodes { id } } } } } } }"""


def num(gid):
    return gid.split("/")[-1]


def file_base(url):
    name = re.sub(r"\.\w+$", "", url.split("?")[0].split("/")[-1])
    return name.split("_")[0]



def assign(p):
    """{media id: colour} for one product, or None when the page should show every photo."""
    copt = next((o for o in p["options"] if o["name"].lower() in COLOR_NAMES), None)
    if not copt or len(copt["values"]) < 2:
        return None
    media = [(m["id"], m["alt"] or "", ((m.get("preview") or {}).get("image") or {}).get("url") or "") for m in p["media"]["nodes"]]
    owner = {}
    for v in p["variants"]["nodes"]:
        colour = next((o["value"] for o in v["selectedOptions"] if o["name"] == copt["name"]), None)
        if colour and v["media"]["nodes"]:
            owner.setdefault(v["media"]["nodes"][0]["id"], colour)
    if len(set(owner.values())) < 2:
        return None
    by_file = {file_base(u): owner[i] for i, _, u in media if i in owner and u}
    for i, alt, u in media:
        if i in owner:
            continue
        if u and file_base(u) in by_file:
            owner[i] = by_file[file_base(u)]
            continue
        hit = [c for c in copt["values"] if re.search(r"(?<!\w)" + re.escape(c.lower()) + r"(?!\w)", alt.lower())]
        if len(hit) == 1:
            owner[i] = hit[0]
            continue
    labels = LABELS.get(p["handle"], {})
    for i, _, _ in media:  # photos checked by eye (colour_labels.json) win over everything above
        c = labels.get(num(i))
        if c == "all":
            owner.pop(i, None)
        elif c in copt["values"]:
            owner[i] = c
    return {num(i): c for i, c in owner.items()}


def main():
    if not DRY:
        errs = gql(DEFINE, {"d": {"name": "Photo colours", "namespace": NS, "key": KEY, "type": "json", "ownerType": "PRODUCT",
                                  "access": {"admin": "MERCHANT_READ", "storefront": "PUBLIC_READ"},
                                  "description": "Which colour each product photo shows (product page shows only the chosen colour's photos)"}}
                   )["metafieldDefinitionCreate"]["userErrors"]
        if errs and not any(e["code"] == "TAKEN" for e in errs):
            log("definition", errs)
    q = f"handle:{ONLY}" if ONLY else ("status:active OR status:draft" if ALL else f"(status:active OR status:draft) AND updated_at:>'{(datetime.now(timezone.utc) - timedelta(days=2)).strftime('%Y-%m-%dT%H:%M:%SZ')}'")
    stats, after, sets, dels = {"products": 0, "colour photos": 0, "set": 0, "cleared": 0, "unchanged": 0}, None, [], []
    while True:
        page = gql(Q, {"a": after, "q": q})["products"]
        for p in page["nodes"]:
            stats["products"] += 1
            m = assign(p)
            old = (p["mc"] or {}).get("value")
            if m is None:
                if old:
                    dels.append({"ownerId": p["id"], "namespace": NS, "key": KEY})
                continue
            stats["colour photos"] += 1
            value = json.dumps(m, ensure_ascii=False, sort_keys=True)
            if old and json.loads(old) == m:
                stats["unchanged"] += 1
                continue
            if ONLY or stats["set"] < 2:
                log("example", p["handle"], value[:300])
            sets.append({"ownerId": p["id"], "namespace": NS, "key": KEY, "type": "json", "value": value})
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    if not DRY:
        for i in range(0, len(sets), 25):
            errs = gql(SET, {"m": sets[i:i + 25]})["metafieldsSet"]["userErrors"]
            if errs:
                log("metafieldsSet", errs[:3])
        for i in range(0, len(dels), 25):
            gql(DELETE, {"m": dels[i:i + 25]})
    stats["set"], stats["cleared"] = len(sets), len(dels)
    log("variant-images", stats)


if __name__ == "__main__":
    main()
