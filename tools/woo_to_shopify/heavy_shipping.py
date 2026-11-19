"""Heavy / light shipping class for every product, now and for new ones (runs nightly in daily.sh).

A product is heavy when its title and price say it is big or heavy (standing sandbags, big punching
bags, benches, trampolines, tables, goals, racks, long bars, gym machines...) or when every size of
it weighs 10 kg or more. Heavy products get the tag `ship:heavy`; the others lose it.
The shipping collections follow the tag by themselves:
  "Heavy items (shipping)"  = tagged ship:heavy  -> the heavy rate in each market (250 / 350 / 450)
  "Light items (shipping)"  = everything else    -> the light rate in each market
Corrections: put an exact title in HEAVY or LIGHT below.
"""
import re
import sys

from sync import gql, log

TAG = "ship:heavy"
HEAVY = set()  # exact titles always heavy
LIGHT = {"Boxing Sandbag", "Venum Punching Bag", "Training Sandbag", "Kids’ Boxing Stand"}  # small, light

RULES = [  # (title pattern, minimum price or 0)
    (r"standing (sand|punching) ?bag|standing punching|boxing dummy|combat training sandbag|pear-shaped sandbag|speed bag with stand", 0),
    (r"(punching bag|sandbag).*(\b1 m\b|\b1[0-9]{2} ?cm)", 0),
    (r"\bbench\b", 1500),
    (r"trampoline", 0),
    (r"table tennis table|game table|billiards? table|air hockey table|pool table", 0),
    (r"\bgoal\b(?!keeper)", 3000),
    (r"basketball (hoop|stand)", 1500),
    (r"dumbbell rack|weight rack|squat rack|power rack|smith machine|treadmill|exercise bike|spinning bike|elliptical|rowing machine|multi[- ]?gym|home gym", 0),
    (r"olympic bar|\bbar 1[2-9]0 ?cm", 0),
]
KG = re.compile(r"(\d+(?:\.\d+)?)\s*kg", re.I)

Q = """query($a: String) { products(first: 100, after: $a, query: "status:active OR status:draft") {
  pageInfo { hasNextPage endCursor } nodes { id title tags variants(first: 100) { nodes { title price } } } } }"""


def heavy(p):
    t = p["title"].strip()
    if t in LIGHT:
        return False
    if t in HEAVY:
        return True
    low = t.lower()
    prices = [float(v["price"]) for v in p["variants"]["nodes"]] or [0]
    for rx, min_price in RULES:
        if re.search(rx, low) and min(prices) >= min_price:
            return True
    if "cat:gym-machines" in p["tags"] and min(prices) >= 3000:
        return True
    # every size 10 kg or more (the size is in the variant title, or in the product title for one-size items)
    kgs = [KG.search(v["title"] or "") or KG.search(t) for v in p["variants"]["nodes"]]
    return all(kgs) and min(float(m.group(1)) for m in kgs) >= 10


def main():
    dry = "--dry-run" in sys.argv
    after, added, removed, n = None, [], [], 0
    while True:
        page = gql(Q, {"a": after})["products"]
        for p in page["nodes"]:
            n += 1
            want, has = heavy(p), TAG in p["tags"]
            if want and not has:
                added.append(p["title"])
                if not dry:
                    gql("mutation($id: ID!, $t: [String!]!) { tagsAdd(id: $id, tags: $t) { userErrors { message } } }", {"id": p["id"], "t": [TAG]})
            elif has and not want:
                removed.append(p["title"])
                if not dry:
                    gql("mutation($id: ID!, $t: [String!]!) { tagsRemove(id: $id, tags: $t) { userErrors { message } } }", {"id": p["id"], "t": [TAG]})
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    for t in added:
        log(f"{'would mark' if dry else 'marked'} heavy: {t}")
    for t in removed:
        log(f"{'would unmark' if dry else 'unmarked'} heavy: {t}")
    log(f"heavy-shipping {{'products': {n}, 'marked': {len(added)}, 'unmarked': {len(removed)}}}")


if __name__ == "__main__":
    main()
