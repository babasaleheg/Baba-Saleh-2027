"""Full read-only store audit (stock, prices and offers, categories, size guides, SEO and Arabic).

    python3 store_audit.py [offers_rules.json]   # writes $DATA_DIR/store_audit.json and prints a summary

Changes nothing. Each finding lists the products by title so a person (or the nightly) can act.
"""
import json, os, re, sys
from collections import Counter, defaultdict

from categorize import TAX, TYPE_CAT
from seo_bilingual import resources
from sync import gql, log

D = os.environ.get("DATA_DIR", "woo_data")
OCTOBER = "gid://shopify/Location/95443550256"
Q = """query($a: String) { products(first: 8, after: $a, query: "status:active OR status:draft") {
  pageInfo { hasNextPage endCursor }
  nodes { id title handle status vendor productType tags descriptionHtml seo { title description }
    media(first: 10) { nodes { alt mediaContentType } }
    guide: metafield(namespace: "babasaleh", key: "size_guide") { value }
    options { name values }
    variants(first: 100) { nodes { title sku price compareAtPrice inventoryPolicy
      inventoryItem { tracked inventoryLevels(first: 8) { nodes { location { id }
        quantities(names: ["available", "on_hand", "committed"]) { name quantity } } } } } } } } }"""


def size_guide(p):
    """Same choice as sections/size-guide.liquid: None when the product shows no guide."""
    if p["guide"]:
        return "own"
    opt = next((o for o in p["options"] if "size" in o["name"].lower() or "مقاس" in o["name"]), None)
    if not opt:
        return None
    first = (opt["values"][0] if opt["values"] else "").upper().strip()
    ptype = (p["productType"] or "").lower()
    foot = "dept:footwear" in p["tags"] or any(k in ptype for k in ("shoe", "slipper", "sandal"))
    cloth = "dept:clothing" in p["tags"] or any(k in ptype for k in ("swimwear", "tracksuit", "shirt", "pants", "shorts", "jacket", "bra"))
    letter = any(c in first for c in "XSML")
    num = 0 if letter else int(re.match(r"\d+", first[:2]).group()) if re.match(r"\d+", first[:2]) else 0
    kids, women, men = "for:kids" in p["tags"], "for:women" in p["tags"], "for:men" in p["tags"]
    if foot:
        if kids:
            return "kids-shoes"
        return "adult-shoes" if men or women or not 0 < num < 36 else "kids-shoes"
    if cloth:
        if kids:
            return "kids-clothing"
        if women and not men:
            return "womens-clothing"
        return "mens-clothing" if men or not 0 < num <= 18 else "kids-clothing"
    return "none-for-this-type"


def main():
    rules = json.load(open(sys.argv[1])) if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) else None
    products, after = [], None
    while True:
        page = gql(Q, {"a": after})["products"]
        products += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    ar = resources("PRODUCT")
    F = defaultdict(list)
    active = [p for p in products if p["status"] == "ACTIVE"]
    seen_titles = Counter(p["title"].strip().lower() for p in active)
    for p in active:
        t, tags = p["title"], p["tags"]
        vs = p["variants"]["nodes"]
        # --- stock
        for v in vs:
            name = f"{t} – {v['title']}" if v["title"] != "Default Title" else t
            item = v["inventoryItem"]
            if not item["tracked"]:
                F["stock: not tracked"].append(name)
            if v["inventoryPolicy"] != "DENY":
                F["stock: sells when sold out (policy CONTINUE)"].append(name)
            for lvl in item["inventoryLevels"]["nodes"]:
                q = {x["name"]: x["quantity"] for x in lvl["quantities"]}
                if lvl["location"]["id"] == OCTOBER:
                    if q.get("available", 0) < 0:
                        F["stock: October available below 0 (oversold)"].append(f"{name} ({q['available']})")
                elif q.get("committed", 0) > 0:
                    F["stock: open orders still assigned to a non-October location"].append(name)
        # --- prices
        for v in vs:
            name = f"{t} – {v['title']}" if v["title"] != "Default Title" else t
            price, cap = float(v["price"] or 0), float(v["compareAtPrice"] or 0)
            if price <= 0:
                F["price: 0 on a live product"].append(name)
            if cap and cap <= price:
                F["price: crossed-out price not higher than the price"].append(f"{name} ({price:g} / {cap:g})")
        prices = {float(v["price"]) for v in vs}
        if len(vs) > 1 and len(prices) > 1 and max(prices) > 3 * min(prices):
            F["price: sizes/colours with very different prices (check)"].append(f"{t} ({min(prices):g}–{max(prices):g})")
        # --- categories
        cats = [x for x in tags if x.startswith("cat:")]
        if len(cats) != 1:
            F["category: not exactly one cat: tag"].append(f"{t} {cats}")
        elif cats[0] in TAX:
            want = TAX[cats[0]]
            if p["productType"] != want["type"]:
                F["category: product type doesn't match its category"].append(f"{t} ({p['productType']} vs {want['type']})")
            missing = [x for x in want["tags"] if x not in tags]
            if missing:
                F["category: missing department/group tags"].append(f"{t} {missing}")
        auds = [x for x in tags if x.startswith("for:")]
        if len(auds) > 1:
            F["category: more than one audience tag"].append(f"{t} {auds}")
        if any(x in tags for x in ("dept:clothing", "dept:footwear")) or "swim" in (p["productType"] or "").lower() and "wear" in (p["productType"] or "").lower():
            if not auds:
                F["category: clothing/shoes/swimwear without men/women/kids"].append(t)
        if seen_titles[t.strip().lower()] > 1:
            F["catalog: same title on several live products"].append(t)
        # --- size guide
        g = size_guide(p)
        if g == "none-for-this-type" and any(x in tags for x in ("dept:clothing", "dept:footwear")):
            F["size guide: clothing/shoes with sizes but no guide"].append(t)
        if g == "kids-clothing" and "for:men" in tags or g == "kids-clothing" and "for:women" in tags:
            F["size guide: adult product gets the kids' chart (number sizes)"].append(t)
        if g in ("mens-clothing", "womens-clothing") and "for:kids" in tags:
            F["size guide: kids' product gets an adult chart (letter sizes)"].append(t)
        if g == "mens-clothing" and "for:women" in tags:
            F["size guide: women's product gets the men's chart"].append(t)
        if g == "adult-shoes" and "for:kids" in tags:
            F["size guide: kids' shoes get the adult shoe chart"].append(t)
        # --- SEO + images
        seo = p["seo"] or {}
        if not seo.get("title"):
            F["seo: no search title"].append(t)
        elif len(seo["title"]) > 75:
            F["seo: search title over 75 characters"].append(f"{t} ({len(seo['title'])})")
        if not seo.get("description"):
            F["seo: no search description"].append(t)
        if len(re.sub("<[^>]+>", "", p["descriptionHtml"] or "").strip()) < 40:
            F["seo: description missing or very short"].append(t)
        imgs = [m for m in p["media"]["nodes"] if m["mediaContentType"] == "IMAGE"]
        if not imgs:
            F["seo: no image"].append(t)
        elif any(not (m["alt"] or "").strip() for m in imgs):
            F["seo: image without alt text"].append(t)
        if re.search(r"-\d+$", p["handle"]) or re.fullmatch(r"[\d-]+", p["handle"]):
            F["seo: web address ends in a number or is only numbers"].append(f"{t} (/{p['handle']})")
        # --- Arabic
        r = ar.get(p["id"], {"ar": {}, "content": {}})
        for key, label in (("title", "title"), ("body_html", "description"), ("meta_title", "search title"), ("meta_description", "search description")):
            if (r["content"].get(key) or ("",))[0] and (not r["ar"].get(key) or not r["ar"][key][0]):
                F[f"arabic: no Arabic {label}"].append(t)
            elif r["ar"].get(key) and r["ar"][key][1]:
                F[f"arabic: Arabic {label} out of date"].append(t)
        art = (r["ar"].get("title") or ("",))[0]
        if art and re.search(r"[A-Za-z]{4,}", art) and not re.search(r"[؀-ۿ]", art):
            F["arabic: Arabic title has no Arabic letters"].append(f"{t} → {art}")
    # --- November offers: store price vs offer sheet
    if rules:
        byid = {p["id"]: p for p in products}
        for rule in rules["products"]:
            p = byid.get(f"gid://shopify/Product/{rule['id']}")
            if not p:
                F["offers: product in the offer sheet not found"].append(rule["h"]); continue
            for v in p["variants"]["nodes"]:
                if "price" in rule:
                    want = rule["price"]
                else:
                    parts = [v["title"].strip()] + [x.strip() for x in v["title"].split(" / ")]  # sizes like "28/29" stay whole
                    want = next((rule["sizes"][x] for x in parts if x in rule["sizes"]), rule["sizes"].get("*"))
                if not want or want[1] >= want[0]:
                    continue
                if abs(float(v["price"]) - want[1]) > 0.01 or abs(float(v["compareAtPrice"] or 0) - want[0]) > 0.01:
                    F["offers: store price differs from the offer sheet"].append(
                        f"{p['title']} – {v['title']} (store {float(v['price']):g}/{float(v['compareAtPrice'] or 0):g}, sheet {want[1]:g}/{want[0]:g})")
    out = {k: v for k, v in sorted(F.items())}
    json.dump(out, open(os.path.join(D, "store_audit.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"store-audit {len(active)} live products, {len(products) - len(active)} drafts")
    for k, v in out.items():
        print(f"{len(v):5}  {k}" + (f"   e.g. {v[:3]}" if v else ""))


if __name__ == "__main__":
    main()
