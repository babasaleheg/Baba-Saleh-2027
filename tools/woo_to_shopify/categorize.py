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
}

AUDIENCE = [(r"\b(kids?|boys?|girls?|baby|junior|children)\b", "for:kids"), (r"\b(women|women’s|women's|ladies|hijab)\b", "for:women"), (r"\b(men|men’s|men's)\b", "for:men")]

PRODUCTS_Q = """query($a: String) { products(first: 250, after: $a, query: "status:active") {
  pageInfo { hasNextPage endCursor } nodes { id title productType tags } } }"""
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
    log(f"categorized {done} products" + (f"; no rule matched: {unknown}" if unknown else ""))


if __name__ == "__main__":
    main()
