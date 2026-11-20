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
HEAVY = {  # exact titles always heavy (full review Nov 20 2026)
    "Olympic Hex Bar", "Volleyball Posts", "Kids’ Ride-On ATV Car", "Basketball Backboard with Rim",
    "Kids’ Basketball – 160 cm", "Rebound Ball Stand", "Boxing Speed Ball 125 cm", "Kids’ Punching Ball – 125 cm",
    "Airplane Kids’ Tricycle", "Kids’ Robot Tricycle with Seat", "Kids’ Tricycle with Seat & Backrest",
    "Balloon Kids’ Balance Bike", "Kids’ Balance Bike", "18 mm Flooring per Square Meter",
    # owner, Nov 20 2026: these are heavy too
    "Dome-Shaped Tent – 6 People", "Dome-Shaped Tent – 8 People", "Easy Open Camping Tent", "Triceps Bar",
    "Zigzag Bar 25 mm", "Kids’ Ride-On Car", "Kids’ Excavator Ride-On Car", "2-Wheel Scooter", "Large Trophy 95 cm",
    "Volleyball Net with Wire", "Mini Tennis Net", "Kids’ Boxing Stand",
}
LIGHT = {"Boxing Sandbag", "Venum Punching Bag", "Training Sandbag"}  # small, light

RULES = [  # (title pattern, minimum price or 0)
    (r"standing (sand|punching) ?bag|standing punching|boxing dummy|combat training sandbag|pear-shaped sandbag|speed bag with stand", 0),
    (r"(punching bag|sandbag).*(\b1 m\b|\b1[0-9]{2} ?cm)", 0),
    (r"\bbench\b", 1500),
    (r"trampoline", 0),
    (r"table tennis table|game table|billiards? table|air hockey table|pool table", 0),
    (r"\bgoal\b(?!keeper)", 3000),
    (r"basketball (hoop|stand)", 1500),
    (r"dumbbell rack|weight rack|squat rack|power rack|smith machine|treadmill|exercise bike|spinning bike|elliptical|rowing machine|multi[- ]?gym|home gym|bars station|pull-up station|power tower|battle rope", 0),
    (r"olympic bar|\bbar 1[2-9]0 ?cm", 0),
]
KG = re.compile(r"(\d+(?:\.\d+)?)\s*kg", re.I)

Q = """query($a: String) { products(first: 100, after: $a, query: "status:active OR status:draft") {
  pageInfo { hasNextPage endCursor } nodes { id title tags variants(first: 100) { nodes { id title price inventoryItem { measurement { weight { value unit } } } } } } } }"""


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


WEIGHTED = re.compile(r"dumbbell|kettlebell|weight plate|medicine ball", re.I)   # sold per size: each size gets its real weight
NOT_WEIGHTED = re.compile(r"rack|holder|foam|water", re.I)
W_Q = """query($a: String) { products(first: 100, after: $a, query: "(title:*dumbbell* OR title:*Dumbbell* OR title:*kettlebell* OR title:*Kettlebell* OR title:*Plate* OR title:*plate* OR title:*Medicine* OR title:*medicine*) AND (status:active OR status:draft)") {
  pageInfo { hasNextPage endCursor } nodes { id title variants(first: 100) { nodes { id title
  inventoryItem { measurement { weight { value unit } } } } } } } }"""
W_SET = """mutation($p: ID!, $v: [ProductVariantsBulkInput!]!) { productVariantsBulkUpdate(productId: $p, variants: $v) {
  userErrors { message } } }"""


def kg_of(v):
    w = (v["inventoryItem"]["measurement"] or {}).get("weight") or {}
    return float(w.get("value") or 0) * {"GRAMS": 0.001, "POUNDS": 0.4536, "OUNCES": 0.02835}.get(w.get("unit"), 1)


def fix_weight(p, want, dry):
    """The shipping collections go by weight per size (5 kg and up = heavy). Heavy products get
    30 kg on every size; other products (not dumbbells/kettlebells, which get their real weight)
    must stay under 5 kg."""
    if WEIGHTED.search(p["title"]) and not NOT_WEIGHTED.search(p["title"]):
        return
    todo = []
    for v in p["variants"]["nodes"]:
        kg = kg_of(v)
        if want and kg < 5:
            todo.append({"id": v["id"], "inventoryItem": {"measurement": {"weight": {"value": 30, "unit": "KILOGRAMS"}}}})
        elif not want and kg >= 5:
            todo.append({"id": v["id"], "inventoryItem": {"measurement": {"weight": {"value": 0, "unit": "KILOGRAMS"}}}})
    if todo and not dry:
        gql(W_SET, {"p": p["id"], "v": todo})


def set_weights(dry):
    """Dumbbells and kettlebells: each size's weight from its title (e.g. 10 kg). The shipping
    collections use it per size: 5 kg and more = heavy shipping, lighter = light shipping."""
    after, n = None, 0
    while True:
        page = gql(W_Q, {"a": after})["products"]
        for p in page["nodes"]:
            if not WEIGHTED.search(p["title"]) or NOT_WEIGHTED.search(p["title"]):
                continue
            todo = []
            for v in p["variants"]["nodes"]:
                m = KG.search(v["title"] or "") or KG.search(p["title"])
                if not m:
                    continue
                kg = float(m.group(1))
                w = (v["inventoryItem"]["measurement"] or {}).get("weight") or {}
                have = float(w.get("value") or 0) * (1 if w.get("unit") in (None, "KILOGRAMS") else 0.001 if w.get("unit") == "GRAMS" else 0.4536)
                if abs(have - kg) > 0.01:
                    todo.append({"id": v["id"], "inventoryItem": {"measurement": {"weight": {"value": kg, "unit": "KILOGRAMS"}}}})
            if todo:
                n += len(todo)
                if not dry:
                    gql(W_SET, {"p": p["id"], "v": todo})
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    return n


def main():
    dry = "--dry-run" in sys.argv
    after, added, removed, n = None, [], [], 0
    while True:
        page = gql(Q, {"a": after})["products"]
        for p in page["nodes"]:
            n += 1
            want, has = heavy(p), TAG in p["tags"]
            fix_weight(p, want, dry)
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
    weights = set_weights(dry)
    log(f"heavy-shipping {{'products': {n}, 'marked': {len(added)}, 'unmarked': {len(removed)}, 'sizes weighed': {weights}}}")


if __name__ == "__main__":
    main()
