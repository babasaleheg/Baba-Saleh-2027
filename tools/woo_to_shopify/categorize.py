"""Keep every active product in the right category.

Categories (collections) are filled by tags: one `cat:` tag per product, plus the `dept:` /
`group:` tags that cat belongs to (taxonomy.json) and `for:men|women|kids` from the title.

    python3 categorize.py           # tag products that have no category, apply FIXES
    python3 categorize.py --dry-run # only print what would change

Products added later (staff portal, Shopify admin) without tags get the category of the most
similar existing product name (82% right when tested on the current catalogue), falling back to
the keyword RULES, so they show up in the menu, filters and Google categories automatically.
"""
import json, math, os, re, sys
from collections import Counter

from sync import gql, log

HERE = os.path.dirname(os.path.abspath(__file__))
TAX = json.load(open(os.path.join(HERE, "taxonomy.json"), encoding="utf-8"))

# Title keywords -> category, most specific first.
RULES = [
    (r"badminton", "cat:badminton"), (r"padel", "cat:padel"), (r"squash", "cat:squash"),
    (r"table tennis|ping ?pong", "cat:table-tennis"), (r"speed ?ball", "cat:speedball"), (r"tennis", "cat:tennis"),
    (r"basketball", "cat:basketball"), (r"volleyball", "cat:volleyball"), (r"handball", "cat:handball"), (r"hockey", "cat:hockey"),
    (r"goalkeeper|shin guard|football|soccer", "cat:football"),
    (r"punching|boxing|mma|kick ?pad|focus mitt", "cat:boxing"), (r"taekwondo", "cat:taekwondo"), (r"karate|judo", "cat:karate"),
    (r"goggle", "cat:goggles"), (r"swim(ming)? cap", "cat:swim-caps"), (r"snorkel|diving|fins\b", "cat:diving"),
    (r"life ?jacket|swim ring|arm ?band", "cat:swim-safety"), (r"kick ?board|pull ?buoy|swim(ming)? board", "cat:swim-training"),
    (r"burkini|women.*swim|swim.*women|girls.*swim", "cat:women-swimwear"), (r"kids.*swim|swim.*kids|baby.*swim", "cat:kids-swimwear"),
    (r"swim ?shorts|men.*swim|swim trunks", "cat:men-swimwear"), (r"pool float|inflatable|\bfloat\b", "cat:pool-floats"),
    (r"water gun|beach toy|sand toy", "cat:beach-toys"), (r"beach bag|sun hat", "cat:beach-bags-hats"),
    (r"tracksuit|track suit", "cat:tracksuits"), (r"hoodie|jacket", "cat:jackets"), (r"sports bra", "cat:sports-bras"),
    (r"legging|pants|trousers", "cat:pants"), (r"t-?shirt|\btop\b|jersey", "cat:t-shirts"), (r"shorts", "cat:shorts"),
    (r"football shoe|studs|turf", "cat:football-shoes"), (r"slipper|sandal|crocs|slides", "cat:slippers"),
    (r"sneaker|running shoe|shoes", "cat:running-shoes"),
    (r"dumbbell|kettlebell|barbell|weight plate|plates", "cat:weights"), (r"resistance band|loop band|mini band", "cat:resistance-bands"),
    (r"jump ?rope|skipping", "cat:jump-ropes"), (r"yoga|pilates", "cat:yoga"),
    (r"bench|pull[- ]?up|treadmill|bike trainer|machine|station", "cat:gym-machines"),
    (r"knee|ankle|wrist|elbow|back support|brace|massage", "cat:supports"),
    (r"bottle|shaker", "cat:water-bottles"), (r"backpack|sports bag|gym bag|duffel", "cat:backpacks"), (r"handbag|shoulder bag", "cat:handbags"),
    (r"\bcap\b|\bhat\b", "cat:hats"), (r"flag", "cat:flags"),
    (r"medal", "cat:medals"), (r"trophy|cup\b|shield|oscar", "cat:trophies"),
    (r"scooter", "cat:scooters"), (r"skateboard", "cat:skateboards"), (r"roller|skates", "cat:skating"), (r"bicycle|bike|cycling|helmet", "cat:cycling"),
    (r"tent|sleeping bag|camping", "cat:camping"), (r"billiard|pool cue|snooker", "cat:billiards"), (r"ballet|gymnastic", "cat:ballet"),
    (r"cone|agility|ladder|whistle|hurdle|coach", "cat:coaching"),
    (r"puzzle|board game|cards|chess|domino|game", "cat:games"), (r"toy|blocks|doll|car\b", "cat:toys"),
]

# Products whose existing category is wrong: title -> correct category.
FIXES = {
    "Silicone Sports Bottle - Brown": "cat:water-bottles",
    "Sports Training Mesh Tank Vest": "cat:coaching",
    "Bar 180 cm": "cat:weights",
    "bar 180cm": "cat:weights",
    "Bar 150cm": "cat:weights",
    "Muscle Training Bar": "cat:fitness-accessories",
    "Hook Bar Lifting Straps": "cat:fitness-accessories",
    "Women’s Dinosaur Slides": "cat:slippers",
    "Venum Challenger Boxing Headgear – Black &amp; Gold": "cat:boxing",
    "Venum Challenger Boxing Headgear – Black & Gold": "cat:boxing",
    "Clinch Kickboxing Shin Guards": "cat:boxing",
    "Captain Armband": "cat:football",
    "Basketball & Bowling Game 2 in 1": "cat:games",
    "Venum Headguard": "cat:boxing",
    "Bandage Pair 2.5 m – Blue": "cat:boxing",
    "Disney Kids’ Swim Set": "cat:kids-swimwear",
    "Kids’ Swim Set – Black, Blue, Orange & White": "cat:kids-swimwear",
    "Kids’ Swim Set – Black, Pink & Purple": "cat:kids-swimwear",
    "Inflatable Water Ball": "cat:beach-toys",
    "Champion Water Ball": "cat:beach-toys",
    "Women’s Samba-Style Shoes": "cat:running-shoes",
    "Track Half-Sleeve & Shorts Swimsuit": "cat:men-swimwear",
    "Electric Air Pump": "cat:sports-accessories",
    "Foot Pump 25 cm": "cat:sports-accessories",
    "Large Floor Pump": "cat:sports-accessories",
    "Mini Foot Pump": "cat:sports-accessories",
    "Metal Ball Inflation Needle": "cat:sports-accessories",
    "Patinage One Row": "cat:skating",
    "Kids’ Tricycle with Seat & Backrest": "cat:cycling",
    "Airplane Kids’ Tricycle": "cat:cycling",
    "Beach Boat Tool Set": "cat:beach-toys",
    "Two-Tone Swimming Training Resistance Band": "cat:swim-training",
    "Ear and Nose Plugs Set": "cat:swim-accessories",
    "Training Speed Hoops": "cat:coaching",
    "Kepal Hand Wrist Exerciser": "cat:fitness-accessories",
    "Doubles Slalom Bag (2-Person)": "cat:games",
    "Track Women’s Swimsuit": "cat:women-swimwear",
    "Track Tight Gym Shorts": "cat:shorts",
    "Moto Boxing Mouth Guard": "cat:boxing",
    "Venum Shin Guards – Blue": "cat:boxing",
    "Venum Shin Guards – Red": "cat:boxing",
    "ZTTY Kickboxing Shin Guard": "cat:boxing",
    "Headguard with Face Shield": "cat:boxing",
    "Arawaza WKF Karate Shin Guard": "cat:karate",
    "Airplane Float – 90 cm": "cat:pool-floats",
    "Colorful Airplane Float": "cat:pool-floats",
    "Rhythmic Gymnastics Rope": "cat:ballet",
    "Gymnastics Wrist Guards": "cat:supports",
    "Kids’ Tool Set with Helmet": "cat:toys",
    "Venum MMA Shin Guards": "cat:boxing",
    "Clinch Boxing Head Guard": "cat:boxing",
    "H-Shape Soccer Coaching Board – 30 × 45 cm": "cat:coaching",
    # photo audit
    "Track 3D Slip Swimsuit": "cat:men-swimwear",
    "Track 3D Half Stretch Swim Shorts": "cat:men-swimwear",
    "Track Half-Length Swim Shorts": "cat:men-swimwear",
    "Track Girls’ Swimsuit": "cat:women-swimwear",
    "Track Kids’ 3D Swimsuit Set – Top & Pants": "cat:women-swimwear",
    "Kiko Modest Burkini Set": "cat:women-swimwear",
    "Multicolor Football, Size 5 – White": "cat:football",
    "Men’s Cowboy Hat": "cat:hats",
    "Baby Float with Canopy & Water Gun": "cat:pool-floats",
    "Hand Wraps": "cat:sports-accessories",
    "Plain Hand Wrap": "cat:sports-accessories",
    "Racket Set": "cat:beach-toys",
    "Single Racket, 27 cm": "cat:beach-toys",
    "Star Training Plate": "cat:coaching",
    "Track Weight Bench with Barbell Rack": "cat:gym-machines",
    "Kango Gloves – Pakistani": "cat:boxing",
    "One Hand Handle": "cat:weights",
    "Zigzag Bar 25 mm": "cat:weights",
    "Triceps Bar": "cat:weights",
    "Infinity Foot Tensioner": "cat:fitness-accessories",
    "Track Cable Cross Tensioner": "cat:fitness-accessories",
    "Doubles Slalom Bag (2-Person)": "cat:camping",
    "Kuna One-Sided Bouncing Ball": "cat:boxing",
    "Wolon Curve Elbow Support": "cat:martial-arts-gear",
    "Wolon Metallic Elbow Support": "cat:martial-arts-gear",
    "Cressi Clio Fins": "cat:diving",
    "Sweat T-Shirt": "cat:jackets",
    "Hooded Sweatshirt": "cat:jackets",
    "Athletics Discus": "cat:coaching",
    "Taekwondo Chest Guard – Red": "cat:taekwondo",
    "Women’s Leggings & Sports Bra Set": "cat:sports-bras",
    "Shark Beach Flip-Flops": "cat:slippers",
    "Basketball Training Agenda": "cat:coaching",
    "Track Front Swimming Snorkel": "cat:swim-training",
    "Color Weight Plates": "cat:weights",
    "Sports Wristbands – Yellow": "cat:sports-accessories",
    "Sports Wristband – White": "cat:sports-accessories",
    "Clear Mouth Guard": "cat:boxing",
    "Kepal Wrist Support Wrap": "cat:supports",
    "LiveUp Fitness Knee Pad": "cat:yoga",
    # new drafts (filed when they go live)
    "Nickel Weight Set 50 kg": "cat:weights",
    "Hexagon Dumbbell 7.5 kg": "cat:weights",
    "Hexagon Dumbbell 17.5 kg": "cat:weights",
    "Track Bathrobe M2 - Black/Grey": "cat:swim-accessories",
    "Track Bathrobe M2 - Navy/Pink": "cat:swim-accessories",
    "Hooded Zip Sweatshirt 2027": "cat:jackets",
    "Girls' Long Sleeve T-Shirt 2026": "cat:t-shirts",
    "WINNING Shaker 1000 ml": "cat:water-bottles",
    "ALIEN Shaker 500 ml": "cat:water-bottles",
    "SPORT Shaker 800 ml": "cat:water-bottles",
    "Flamingo Men's Long Towel Socks": "cat:sports-accessories",
    "Men’s Long Cotton Socks": "cat:sports-accessories",
    "Men’s Short Socks": "cat:sports-accessories",
    "Women’s Long Socks": "cat:sports-accessories",
    "Women’s Short Socks": "cat:sports-accessories",
    "Men’s Turf Football Shoes – Dotted Stars": "cat:football-shoes",
    "Men’s Turf Football Shoes – 3 Stripes": "cat:football-shoes",
    "Value Wrist Wraps": "cat:fitness-accessories",
}

# Products whose audience tag is wrong: title -> correct for: tag
AUDIENCE_FIXES = {
    "Women’s Dinosaur Slides": "for:women",
    "Track Women’s Swimsuit": "for:women",
    "Track Men’s 3-Line Tracksuit": "for:men",
    "Women’s Crocs-Style Sandals": "for:women",
    "Women’s Samba-Style Shoes": "for:women",
    "Women’s Running Shoes": "for:women",
    "Goalkeeper Jersey": "for:kids",
    "Crocs – Black, Navy Blue & White": "for:kids",
    "Comfort Clogs": "for:kids",
    "Fashion Slide Slippers": "for:kids",
    "Track Half-Sleeve & Shorts Swimsuit": "for:men",
    # photo audit: adult models (kids' sizes, if any, are sold from the adult section)
    "Track 3D Slip Swimsuit": "for:men",
    "Track 3D Half Stretch Swim Shorts": "for:men",
    "Track Half-Length Swim Shorts": "for:men",
    "Track Girls’ Swimsuit": "for:women",
    "Track Kids’ 3D Swimsuit Set – Top & Pants": "for:women",
    "Kiko Modest Burkini Set": "for:women",
    "Track Girls’ 3-Line Tracksuit": "for:women",
    "Track Girls’ Tracksuit – Burgundy, Fuchsia & Navy Blue": "for:women",
    "Girls’ Flared Leggings": "for:women",
    "Women’s Flared Leggings": "for:women",
    "Charleston Leggings Pants": "for:women",
    "Charleston Pants": "for:women",
    "Track Tracksuit": "for:men",
    "Waterproof Jacket": "for:men",
    "Sleeve T-Shirt": "for:men",
    "Track T-Shirt": "for:men",
    "Track T-Shirt – Light Brown, Brown & Blue": "for:men",
    "Combat Sports Shorts": "for:men",
    "MMA Boxing Shorts": "for:men",
    "Venum Boxing Shorts": "for:men",
    "Venum Combat Sports Shorts": "for:men",
    "Venum Combat Sports Shorts Black, Red & White": "for:men",
    "Disney Water Bottle": "for:kids",
    "Slide Sandals": "for:kids",
    "Girls’ Beach Sun Hat": "for:kids",
    "Small Football Set": "for:kids",
    "Venum Combat Sports Shorts – Black, Red & White": "for:men",
    "Gym Shorts": "for:women",
    "Women’s Leggings & Sports Bra Set": "for:women",
    "High Waist Gym Shorts": "for:women",
    "Sports Training Mesh Tank Vest": "for:men",
}

AUDIENCE = [(r"\b(kids?|boys?|girls?|baby(?! blue)|junior|children)\b", "for:kids"), (r"\b(women|women’s|women's|ladies|hijab)\b", "for:women"), (r"\b(men|men’s|men's)\b", "for:men")]

PRODUCTS_Q = """query($a: String) { products(first: 250, after: $a, query: "status:active") {
  pageInfo { hasNextPage endCursor } nodes { id title productType tags options { name optionValues { name } } } } }"""
UPDATE = """mutation($p: ProductUpdateInput!) { productUpdate(product: $p) { userErrors { field message } } }"""
TAXONOMY_PREFIXES = ("cat:", "dept:", "group:")


STOP = {"the", "and", "for", "with", "of", "in", "set", "pcs", "cm", "size", "new", "2025", "2026"}


def words(title):
    return {w for w in re.findall(r"[a-z0-9]+", title.lower().replace("’", "'")) if len(w) > 1 and w not in STOP}


class Similar:
    """Category of the most similar tagged product names (rare shared words count more)."""

    def __init__(self, products):
        self.items = [(words(p["title"]), c[0]) for p in products if (c := [t for t in p["tags"] if t.startswith("cat:")])]
        df = Counter(w for ws, _ in self.items for w in ws)
        n = len(self.items)
        self.idf = {w: math.log((n + 1) / (k + 1)) + 1 for w, k in df.items()}

    def __call__(self, title):
        q = words(title)
        scores = sorted(((sum(self.idf[w] for w in q & ws), cat) for ws, cat in self.items if q & ws), reverse=True)[:5]
        votes = Counter()
        for score, cat in scores:
            votes[cat] += score
        return votes.most_common(1)[0][0] if votes else None


def guess(title, similar=None):
    found = similar(title) if similar else None
    if found:
        return found
    t = title.lower()
    for rx, cat in RULES:
        if re.search(rx, t):
            return cat
    return None


TYPE_CAT = {v["type"]: k for k, v in TAX.items()}


def plan(p, similar=None):
    """Every product ends with exactly one cat: tag, that category's dept:/group: tags and its product type.
    Runs on every product, every night, so a category added back by another tool or by hand
    (a product in two categories, a swimsuit in Sportswear) is put right again."""
    cats = sorted({t for t in p["tags"] if t.startswith("cat:") and t in TAX})
    target = FIXES.get(p["title"].strip())
    if not target:
        if len(cats) == 1:
            target = cats[0]
        elif len(cats) > 1:
            # conflicting categories: the product type decides, then the title, then the first one
            by_type = TYPE_CAT.get(p.get("productType") or "")
            by_title = guess(p["title"], similar)
            target = by_type if by_type in cats else by_title if by_title in cats else cats[0]
        else:
            target = guess(p["title"], similar)
    if not target or target not in TAX:
        return ("unknown", None)
    tags = [t for t in p["tags"] if not t.startswith(TAXONOMY_PREFIXES)] + [target] + TAX[target]["tags"]
    if not any(t.startswith("for:") for t in tags):
        for rx, tag in AUDIENCE:
            if re.search(rx, p["title"].lower()):
                tags.append(tag)
                break
    tags = sorted(set(tags))
    if tags == sorted(set(p["tags"])) and p.get("productType") == TAX[target]["type"]:
        return None
    return (target, {"id": p["id"], "tags": tags, "productType": TAX[target]["type"]})


def main():
    dry = "--dry-run" in sys.argv
    after, products = None, []
    while True:
        page = gql(PRODUCTS_Q, {"a": after})["products"]
        products += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    similar = Similar(products)
    done, unknown = 0, []
    for p in products:
        step = plan(p, similar)
        if not step:
            continue
        cat, update = step
        if not update:
            unknown.append(p["title"])
            continue
        log(f"{'would set' if dry else 'set'} {cat:24} {p['title']}")
        if not dry:
            errs = gql(UPDATE, {"p": update})["productUpdate"]["userErrors"]
            if errs:
                log(f"  error: {errs}")
            else:
                p["tags"] = update["tags"]  # later steps below must build on the new tags, not the old ones
        done += 1
    # Each swimwear item shows in one section only (its cat:): no adult models in Kids', no kids in Women's
    for p in products:
        extra = [t for t in p["tags"] if t in ("x:men-swimwear", "x:women-swimwear", "x:kids-swimwear")]
        if extra:
            log(f"{'would remove' if dry else 'remove'} {','.join(extra):24} {p['title']}")
            if not dry:
                gql("mutation($id: ID!, $t: [String!]!) { tagsRemove(id: $id, tags: $t) { userErrors { message } } }", {"id": p["id"], "t": extra})
                p["tags"] = [t for t in p["tags"] if t not in extra]
            done += 1

    for p in products:
        want = AUDIENCE_FIXES.get(p["title"].strip())
        have = [t for t in p["tags"] if t.startswith("for:")]
        if not want and len(have) > 1:
            want = "for:kids" if "for:kids" in have else sorted(have)[0]  # girls' items are kids', not women's
        if want and have != [want]:
            log(f"{'would set' if dry else 'set'} {want:24} {p['title']}")
            if not dry:
                tags = sorted({t for t in p["tags"] if not t.startswith("for:")} | {want})
                gql(UPDATE, {"p": {"id": p["id"], "tags": tags}})
            done += 1
    log(f"categorized {done} products" + (f"; no rule matched: {unknown}" if unknown else ""))


if __name__ == "__main__":
    main()
