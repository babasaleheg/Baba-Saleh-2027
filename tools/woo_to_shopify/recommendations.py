"""Pick "You may also like" and "Frequently bought together" products for every product.

Written to product metafields (lists of product references) that the theme renders directly,
so the product page needs no extra requests:

  babasaleh.related         up to 12 products from the same category: same audience
                            (men / women / kids) first, then closest price; in stock only
  babasaleh.bought_together 2 products customers bought with this one (from all past orders),
                            or, without enough history, best sellers from the categories that
                            are most often bought with this category (e.g. gloves -> hand wraps)

    python3 recommendations.py            # nightly
    python3 recommendations.py --dry-run  # print a few examples
"""
import math, re, sys
from collections import Counter, defaultdict

from sync import gql, log

DRY = "--dry-run" in sys.argv
NS = "babasaleh"

PRODUCTS_Q = """query($a: String) { products(first: 250, after: $a, query: "status:active") {
  pageInfo { hasNextPage endCursor }
  nodes { id title tags vendor createdAt totalInventory tracksInventory
    variants(first: 1) { nodes { availableForSale } }
    priceRangeV2 { minVariantPrice { amount } }
    rel: metafield(namespace: "babasaleh", key: "related") { value }
    fbt: metafield(namespace: "babasaleh", key: "bought_together") { value } } } }"""
ORDERS_Q = """query($a: String) { orders(first: 100, after: $a) { pageInfo { hasNextPage endCursor }
  nodes { lineItems(first: 50) { nodes { quantity product { id } } } } } }"""
DEFINE = """mutation($d: MetafieldDefinitionInput!) { metafieldDefinitionCreate(definition: $d) {
  createdDefinition { id } userErrors { code message } } }"""
SET = """mutation($m: [MetafieldsSetInput!]!) { metafieldsSet(metafields: $m) { userErrors { field message } } }"""


# Sensible add-ons per category, best first (used before order history, which is noisy for small samples)
COMPLEMENTS = {
    "boxing": ["martial-arts-gear", "jump-ropes", "speedball", "water-bottles"],
    "taekwondo": ["martial-arts-gear", "water-bottles", "backpacks"], "karate": ["martial-arts-gear", "water-bottles", "backpacks"],
    "martial-arts-gear": ["boxing", "jump-ropes", "water-bottles"], "speedball": ["boxing", "jump-ropes"],
    "football": ["football-shoes", "water-bottles", "backpacks", "coaching"], "football-shoes": ["football", "sports-accessories", "backpacks"],
    "basketball": ["water-bottles", "backpacks", "running-shoes"], "volleyball": ["supports", "water-bottles"], "handball": ["supports", "water-bottles"],
    "tennis": ["water-bottles", "sports-accessories", "backpacks"], "padel": ["water-bottles", "sports-accessories", "backpacks"],
    "squash": ["goggles", "water-bottles"], "badminton": ["water-bottles", "backpacks"], "table-tennis": ["games", "water-bottles"],
    "weights": ["fitness-accessories", "resistance-bands", "water-bottles"], "gym-machines": ["weights", "fitness-accessories", "resistance-bands"],
    "fitness-accessories": ["water-bottles", "resistance-bands", "jump-ropes"], "resistance-bands": ["yoga", "fitness-accessories", "jump-ropes"],
    "yoga": ["resistance-bands", "water-bottles", "fitness-accessories"], "jump-ropes": ["resistance-bands", "water-bottles"],
    "supports": ["fitness-accessories", "water-bottles"], "running-shoes": ["t-shirts", "shorts", "water-bottles"],
    "tracksuits": ["t-shirts", "running-shoes", "backpacks"], "t-shirts": ["shorts", "pants", "running-shoes"],
    "pants": ["t-shirts", "running-shoes"], "shorts": ["t-shirts", "running-shoes"], "jackets": ["pants", "t-shirts"],
    "sports-bras": ["pants", "yoga", "water-bottles"],
    "goggles": ["swim-caps", "swim-accessories"], "swim-caps": ["goggles", "swim-accessories"],
    "swim-accessories": ["goggles", "swim-caps"], "swim-training": ["goggles", "swim-caps"],
    "men-swimwear": ["goggles", "swim-caps", "slippers"], "women-swimwear": ["swim-caps", "goggles", "beach-bags-hats"],
    "kids-swimwear": ["goggles", "swim-safety", "pool-floats"], "swim-safety": ["goggles", "kids-swimwear"],
    "pool-floats": ["beach-toys", "swim-safety"], "beach-toys": ["pool-floats", "beach-bags-hats"],
    "beach-shoes": ["beach-bags-hats", "goggles"], "beach-bags-hats": ["slippers", "beach-shoes"], "slippers": ["beach-bags-hats", "t-shirts"],
    "diving": ["swim-accessories", "beach-shoes"], "cycling": ["water-bottles", "supports"], "scooters": ["supports", "skating"],
    "skating": ["supports", "skateboards"], "skateboards": ["supports", "skating"], "camping": ["water-bottles", "backpacks"],
    "medals": ["trophies"], "trophies": ["medals"], "coaching": ["football", "sports-accessories"],
    "backpacks": ["water-bottles"], "water-bottles": ["backpacks", "fitness-accessories"], "toys": ["games"], "games": ["toys"],
}


APPAREL = {"t-shirts", "shorts", "pants", "jackets", "tracksuits", "running-shoes", "football-shoes", "slippers", "beach-shoes", "sports-bras"}


def tag(p, prefix):
    return next((t for t in p["tags"] if t.startswith(prefix)), None)


def audience(p):
    """(age, gender) from the for: tag and the title; None where unknown."""
    t = " " + p["title"].lower().replace("’", "'") + " "
    age = "kids" if tag(p, "for:") == "for:kids" or re.search(r"\b(kids?|boys?|girls?|baby|junior|children|teens?)\b", t) else None
    gender = ("f" if re.search(r"\b(women|women's|ladies|girls?|girls'|hijab|burkini|bikini)\b", t) or tag(p, "for:") == "for:women"
              else "m" if re.search(r"\b(men|men's|boys?|boys')\b", t) or tag(p, "for:") == "for:men" else None)
    if not age and tag(p, "for:") in ("for:men", "for:women"):
        age = "adult"
    if not age and gender and re.search(r"\b(men|men's|women|women's|ladies)\b", t):
        age = "adult"
    return age, gender


def fits(a, b):
    """Can b be suggested next to a? Kids with kids, women's not next to men's."""
    (xa, xg), (ya, yg) = audience(a), audience(b)
    return (not xa or not ya or xa == ya) and (not xg or not yg or xg == yg)


def load_products():
    out, after = [], None
    while True:
        page = gql(PRODUCTS_Q, {"a": after})["products"]
        out += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return out
        after = page["pageInfo"]["endCursor"]


def load_baskets():
    baskets, sold, after = [], Counter(), None
    while True:
        page = gql(ORDERS_Q, {"a": after})["orders"]
        for o in page["nodes"]:
            ids = {li["product"]["id"] for li in o["lineItems"]["nodes"] if li["product"]}
            for li in o["lineItems"]["nodes"]:
                if li["product"]:
                    sold[li["product"]["id"]] += li["quantity"]
            if len(ids) > 1:
                baskets.append(ids)
        if not page["pageInfo"]["hasNextPage"]:
            return baskets, sold
        after = page["pageInfo"]["endCursor"]


def ensure_definitions():
    for key, name, desc in (("related", "You may also like", "Similar products shown on the product page (set nightly)"),
                            ("bought_together", "Frequently bought together", "Add-ons shown under Add to cart (set nightly)")):
        d = {"name": name, "namespace": NS, "key": key, "type": "list.product_reference", "ownerType": "PRODUCT", "description": desc}
        if not DRY:
            errs = gql(DEFINE, {"d": d})["metafieldDefinitionCreate"]["userErrors"]
            if errs and not any(e["code"] == "TAKEN" for e in errs):
                log("definition", key, errs)


def main():
    ensure_definitions()
    products = load_products()
    baskets, sold = load_baskets()
    by_id = {p["id"]: p for p in products}
    price = {p["id"]: float(p["priceRangeV2"]["minVariantPrice"]["amount"]) or 1.0 for p in products}
    in_stock = {p["id"] for p in products if p["variants"]["nodes"] and p["variants"]["nodes"][0]["availableForSale"]}
    cat = {p["id"]: tag(p, "cat:") for p in products}
    group = {p["id"]: tag(p, "group:") for p in products}
    by_cat = defaultdict(list)
    for p in products:
        by_cat[cat[p["id"]]].append(p["id"])

    # Co-purchases: product pairs, and category pairs (for products without their own history)
    pair, cat_pair = defaultdict(Counter), defaultdict(Counter)
    for ids in baskets:
        ids = [i for i in ids if i in by_id]
        for a in ids:
            for b in ids:
                if a != b:
                    pair[a][b] += 1
                    if cat[a] and cat[b] and cat[a] != cat[b]:
                        cat_pair[cat[a]][cat[b]] += 1

    # How much more often category B is in a basket with A than chance; at least 3 baskets together
    cat_baskets = Counter(c for ids in baskets for c in {cat[i] for i in ids if i in by_id} if c)
    n_baskets = max(len(baskets), 1)

    def cat_rank(c):
        lift = {d: n / (cat_baskets[c] * cat_baskets[d] / n_baskets) for d, n in cat_pair[c].items() if n >= 3}
        return [d for d, _ in sorted(lift.items(), key=lambda kv: kv[1], reverse=True)]

    def related(p):
        pid = p["id"]
        pool = [q for q in by_cat[cat[pid]] if q != pid and q in in_stock and fits(p, by_id[q])]
        score = lambda q: ((audience(by_id[q]) == audience(p)) * 2 + (by_id[q]["vendor"] == p["vendor"]) * 0.5
                           - abs(math.log(price[q] / price[pid])) + min(sold[q], 20) * 0.05)
        picks = sorted(pool, key=score, reverse=True)[:12]
        if len(picks) < 6 and group[pid]:  # small category: fill from the same sport / group
            more = [q for q in products if q["id"] not in picks and q["id"] != pid and q["id"] in in_stock
                    and group[q["id"]] == group[pid] and fits(p, q)]
            picks += [q["id"] for q in sorted(more, key=lambda q: sold[q["id"]], reverse=True)][:12 - len(picks)]
        return picks

    def bought_together(p):
        pid = p["id"]
        ok = lambda q: q != pid and q in in_stock and q in by_id and fits(p, by_id[q])
        # 1. bought together often (3+ orders), and from a category that makes sense next to this one
        good = set(COMPLEMENTS.get((cat[pid] or "").removeprefix("cat:"), []))
        hist = [(n, q) for q, n in pair[pid].items() if n >= 3 and ok(q) and (cat[q] or "").removeprefix("cat:") in good]
        picks = [q for _, q in sorted(hist, reverse=True)][:2]
        used_cats = {cat[pid]} | {cat[q] for q in picks}
        # 2. best sellers from the matching categories, then from categories customers buy with this one
        wanted = ["cat:" + c for c in COMPLEMENTS.get((cat[pid] or "").removeprefix("cat:"), [])]
        for c in wanted + [c for c in cat_rank(cat[pid]) if c not in wanted][:2 if not wanted else 0]:
            if len(picks) >= 2:
                break
            if c in used_cats:
                continue
            # a best seller from that category, ideally not dearer than this product
            pool = [q for q in by_cat[c] if ok(q) and q not in picks]
            me = audience(p)
            match = lambda q: sum(x is not None and x == y for x, y in zip(me, audience(by_id[q])))
            pool.sort(key=lambda q: (-match(q), price[q] > price[pid] * 1.2, -sold[q]))
            if me[0] == "kids" and pool and audience(by_id[pool[0]])[0] != "kids" and c.removeprefix("cat:") in APPAREL:
                continue  # no adult clothes or shoes next to kids' items
            if pool:
                picks.append(pool[0])
                used_cats.add(c)
        return picks

    rows, examples = [], 0
    for p in products:
        for key, ids, current in (("related", related(p), p["rel"]), ("bought_together", bought_together(p), p["fbt"])):
            value = "[" + ",".join(f'"{i}"' for i in ids) + "]"
            if ids and (not current or current["value"].replace(" ", "") != value):
                rows.append({"ownerId": p["id"], "namespace": NS, "key": key, "type": "list.product_reference", "value": value})
        if DRY and examples < 6 and p["id"] in pair:
            examples += 1
            log(p["title"], "| together:", [by_id[q]["title"] for q in bought_together(p)], "| related:", [by_id[q]["title"] for q in related(p)[:3]])
    stats = {"products": len(products), "orders_with_2+": len(baskets), "updates": len(rows), "failed": 0}
    if not DRY:
        for i in range(0, len(rows), 25):
            errs = gql(SET, {"m": rows[i:i + 25]})["metafieldsSet"]["userErrors"]
            if errs:
                stats["failed"] += 1
                log("metafieldsSet", errs[:2])
    log("recommendations", stats)


if __name__ == "__main__":
    main()
