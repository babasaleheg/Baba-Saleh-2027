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
    "Tartan Men's Socks, 3 Stripe": "cat:football",
    "Silicone Sports Bottle - Brown": "cat:water-bottles",
    "Sports Training Mesh Tank Vest": "cat:coaching",
    "Bar 180 cm": "cat:weights",
    "bar 180cm": "cat:weights",
    "Bar 150cm": "cat:weights",
    "Muscle Training Bar": "cat:weights",
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
    "Color Hoop Dumbbell": "cat:weights",
    "Girls’ Samba Shoes": "cat:running-shoes",
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
}

# Products whose audience tag is wrong: title -> correct for: tag
AUDIENCE_FIXES = {
    "Women’s Dinosaur Slides": "for:women",
    "Track Women’s Swimsuit": "for:women",
    "Track Men’s 3-Line Tracksuit": "for:men",
    "Girls’ Crocs Sandals": "for:women",
    "Girls’ Samba Shoes": "for:women",
    "Girls’ Running Shoes": "for:women",
    "Goalkeeper Jersey": "for:kids",
    "Crocs – Black, Navy Blue & White": "for:kids",
    "Comfort Clogs": "for:kids",
    "Fashion Slide Slippers": "for:kids",
    "Track Half-Sleeve & Shorts Swimsuit": "for:men",
}

AUDIENCE = [(r"\b(kids?|boys?|girls?|baby|junior|children)\b", "for:kids"), (r"\b(women|women’s|women's|ladies|hijab)\b", "for:women"), (r"\b(men|men’s|men's)\b", "for:men")]

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


def plan(p, similar=None):
    cats = [t for t in p["tags"] if t.startswith("cat:")]
    target = FIXES.get(p["title"].strip())
    if target and cats == [target]:
        target = None
    if not target and cats:
        return None
    target = target or guess(p["title"], similar)
    if not target or target not in TAX:
        return ("unknown", None)
    tags = [t for t in p["tags"] if not t.startswith(TAXONOMY_PREFIXES)] + [target] + TAX[target]["tags"]
    if not any(t.startswith("for:") for t in tags):
        for rx, tag in AUDIENCE:
            if re.search(rx, p["title"].lower()):
                tags.append(tag)
                break
    return (target, {"id": p["id"], "tags": sorted(set(tags)), "productType": TAX[target]["type"]})


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
        done += 1
    # Swimwear sold in both kids' (numbers) and adult (S, M, L...) sizes shows in both sections
    for p in products:
        cat = next((t for t in p["tags"] if t.startswith("cat:")), None)
        if cat not in ("cat:kids-swimwear", "cat:men-swimwear"):
            continue
        sizes = [v["name"].strip().upper() for o in p.get("options", []) if "size" in o["name"].lower() for v in o["optionValues"]]
        kid = any(re.fullmatch(r"\d{1,2}", v) and int(v) <= 16 for v in sizes)
        adult = any(v in ("S", "M", "L", "XL", "2XL", "XXL", "3XL") for v in sizes)
        t = p["title"].lower().replace("’", "'")
        if cat == "cat:men-swimwear":
            other = "x:kids-swimwear"
        elif re.search(r"girl|women|bikini|burkini|dress|skirt", t):
            other = "x:women-swimwear"
        elif re.search(r"short|jammer|trunk|brief", t):
            other = "x:men-swimwear"
        else:
            other = None  # unisex swimsuit: no adult section is clearly right
        if other and kid and adult and other not in p["tags"]:
            log(f"{'would add' if dry else 'add'} {other:24} {p['title']}")
            if not dry:
                gql("mutation($id: ID!, $t: [String!]!) { tagsAdd(id: $id, tags: $t) { userErrors { message } } }", {"id": p["id"], "t": [other]})
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
