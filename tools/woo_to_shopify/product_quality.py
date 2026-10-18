"""Nightly product quality pass: fixes what can be fixed safely, reports the rest.

    python3 product_quality.py            # fix + write quality_report.json
    python3 product_quality.py --dry-run  # only report what would change

Fixes (active and draft products):
  - Titles: HTML entities, underscores and doubled spaces cleaned; all-lowercase titles capitalised.
  - Options: "size" -> "Size"; weight-only sizes -> "Weight"; team/sponsor "colours" -> "Design".
  - Option values: one spelling per size ("2X Large" -> "2XL", "Large" -> "L", "28_29" -> "28/29",
    "10 KG" -> "10 kg") and per colour ("navy blue" -> "Navy Blue", known typos fixed).
  - Arabic for option names and colour/size words (Color -> اللون, Navy Blue -> كحلي, ...).
  - Web addresses: numbers-only handles and "-2"/"-3" duplicates get a readable, unique handle
    built from the title plus brand/colour/category; Shopify redirects the old address.
  - Empty descriptions get a short English + Arabic description from the category.

Reported for review (quality_report.json): missing Arabic titles, no image, price 0, no category.
"""
import html, json, os, re, sys
from collections import Counter

from seo_bilingual import REGISTER, resources
from sync import gql, log

HERE = os.path.dirname(os.path.abspath(__file__))
TAX = json.load(open(os.path.join(HERE, "taxonomy.json"), encoding="utf-8"))
REPORT = os.path.join(os.environ.get("DATA_DIR", os.path.join(HERE, "woo_data")), "quality_report.json")

PRODUCTS_Q = """query($a: String) { products(first: 100, after: $a, query: "status:active OR status:draft") {
  pageInfo { hasNextPage endCursor }
  nodes { id title handle status vendor productType tags descriptionHtml totalInventory
    options { id name optionValues { id name } }
    featuredMedia { id } variants(first: 100) { nodes { price sku } } } } }"""
UPDATE = """mutation($p: ProductUpdateInput!) { productUpdate(product: $p) { product { handle } userErrors { field message } } }"""
OPTION_UPDATE = """mutation($pid: ID!, $o: OptionUpdateInput!, $v: [OptionValueUpdateInput!]) {
  productOptionUpdate(productId: $pid, option: $o, optionValuesToUpdate: $v) { userErrors { field message } } }"""

SMALL = {"and", "or", "of", "with", "for", "in", "on", "the", "a", "an", "to", "&"}
COLORS = {
    "black": ("Black", "أسود"), "white": ("White", "أبيض"), "off white": ("Off White", "أوف وايت"), "red": ("Red", "أحمر"),
    "blue": ("Blue", "أزرق"), "navy blue": ("Navy Blue", "كحلي"), "navy": ("Navy Blue", "كحلي"), "baby blue": ("Baby Blue", "لبني"),
    "light blue": ("Light Blue", "أزرق فاتح"), "green": ("Green", "أخضر"), "mint green": ("Mint Green", "أخضر نعناعي"),
    "olive green": ("Olive Green", "زيتي"), "yellow": ("Yellow", "أصفر"), "soft yellow": ("Soft Yellow", "أصفر فاتح"),
    "orange": ("Orange", "برتقالي"), "dot orange": ("Dotted Orange", "برتقالي منقط"), "pink": ("Pink", "وردي"),
    "light pink": ("Light Pink", "وردي فاتح"), "fuchsia": ("Fuchsia", "فوشيا"), "purple": ("Purple", "بنفسجي"),
    "gray": ("Gray", "رمادي"), "grey": ("Gray", "رمادي"), "dark gray": ("Dark Gray", "رمادي غامق"), "dark grey": ("Dark Gray", "رمادي غامق"),
    "brown": ("Brown", "بني"), "light brown": ("Light Brown", "بني فاتح"), "beige": ("Beige", "بيج"), "dark beige": ("Dark Beige", "بيج غامق"),
    "burgundy": ("Burgundy", "نبيتي"), "gold": ("Gold", "ذهبي"), "rose gold": ("Rose Gold", "ذهبي وردي"), "silver": ("Silver", "فضي"),
    "multicolor": ("Multicolor", "متعدد الألوان"), "multicolour": ("Multicolor", "متعدد الألوان"), "turquoise": ("Turquoise", "تركواز"),
}
DESIGNS = {"qatar alrways": "Qatar Airways", "emirates fly better": "Emirates Fly Better"}
LETTER_SIZES = {"xxs": "2XS", "xs": "XS", "s": "S", "small": "S", "m": "M", "medium": "M", "l": "L", "large": "L",
                "xl": "XL", "x large": "XL", "x-large": "XL", "xxl": "2XL", "2x large": "2XL", "2xl": "2XL", "xxxl": "3XL",
                "3x large": "3XL", "3xl": "3XL", "4x large": "4XL", "4xl": "4XL", "5xl": "5XL", "6xl": "6XL", "7xl": "7XL",
                "8xl": "8XL", "2xs": "2XS", "3xs": "3XS", "free size": "One Size", "one size": "One Size", "onesize": "One Size"}
OPTION_AR = {"Size": "المقاس", "Color": "اللون", "Weight": "الوزن", "Design": "التصميم", "Gender": "النوع", "Brand": "الماركة"}
VALUE_AR = {en: ar for en, ar in COLORS.values()} | {"One Size": "مقاس واحد", "Men": "رجالي", "Women": "حريمي", "Kids": "أطفال", "Unisex": "للجنسين"}

DEPT_TEXT = {  # short, honest category descriptions (EN, AR)
    "dept:sports": ("Sports equipment chosen for training and match days.", "معدات رياضية مختارة للتمرين وأيام المباريات."),
    "dept:fitness": ("Fitness gear for home workouts and the gym.", "مستلزمات لياقة للتمرين في البيت والجيم."),
    "dept:swimming": ("Swimming gear for training, lessons and the pool.", "مستلزمات سباحة للتدريب والدروس وحمام السباحة."),
    "dept:beach": ("Beach and pool fun for the whole family.", "متعة الشاطئ وحمام السباحة لكل العائلة."),
    "dept:clothing": ("Comfortable sportswear for training and everyday wear.", "ملابس رياضية مريحة للتمرين والاستخدام اليومي."),
    "dept:footwear": ("Footwear for sport and everyday comfort.", "أحذية للرياضة والراحة اليومية."),
    "dept:accessories": ("Sports accessories for training and travel.", "إكسسوارات رياضية للتمرين والسفر."),
    "dept:kids-toys": ("Toys and games for active, playful kids.", "ألعاب للأطفال النشيطين ومحبي اللعب."),
    "dept:trophies": ("Awards for tournaments, schools and clubs.", "جوائز للبطولات والمدارس والأندية."),
}


def clean_title(t):
    s = html.unescape(t).replace("’", "’")
    s = re.sub(r"(?<=[A-Za-z])_(?=[A-Za-z])", "-", s) if re.search(r"\bT_shirt", s, re.I) else s.replace("_", " ")
    s = re.sub(r"\s{2,}", " ", s).strip()
    if s == s.lower() and re.search(r"[a-z]", s):
        words = s.split(" ")
        s = " ".join(w if (i and w in SMALL) else w[:1].upper() + w[1:] for i, w in enumerate(words))
    return s


def slug(text):
    s = html.unescape(text).lower().replace("’", "").replace("'", "").replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return re.sub(r"-{2,}", "-", s)[:80].strip("-")


def norm_size(v):
    s = v.strip()
    low = s.lower()
    if low in LETTER_SIZES:
        return LETTER_SIZES[low]
    m = re.fullmatch(r"(\d+)[_/\-](\d+)", s)
    if m and int(m.group(1)) >= 20:  # shoe / waist ranges: 28_29, 36-38 -> 28/29, 36/38
        return f"{m.group(1)}/{m.group(2)}"
    m = re.fullmatch(r"([\d.]+(?:\s*-\s*[\d.]+)?)\s*(kg|kgs|lb|lbs|cm|m)", low)
    if m:
        unit = {"kgs": "kg", "lbs": "lb"}.get(m.group(2), m.group(2))
        return f"{m.group(1).replace(' ', '')} {unit}"
    return s


def is_weight(values):
    return values and all(re.fullmatch(r"[\d.\s-]+(kg|lb)", v.lower().replace("kgs", "kg")) for v in values)


def plan_options(p):
    """[(option_id, new_name or None, [(value_id, new_value)])] for options that change."""
    out = []
    for o in p["options"]:
        name, vals = o["name"].strip(), o["optionValues"]
        if name == "Title":
            continue
        low = name.lower()
        new_name = None
        changes = []
        if low in ("size", "sizes", "المقاس"):
            fixed = [(v["id"], norm_size(v["name"])) for v in vals]
            if is_weight([f for _, f in fixed]):
                new_name = "Weight"
            elif name != "Size":
                new_name = "Size"
            changes = [(vid, f) for (vid, f), v in zip(fixed, vals) if f != v["name"]]
        elif "colo" in low:
            known = [v for v in vals if v["name"].strip().lower() in COLORS]
            if len(known) < len(vals) / 2:
                new_name = "Design"
                changes = [(v["id"], DESIGNS[v["name"].strip().lower()]) for v in vals if v["name"].strip().lower() in DESIGNS]
            else:
                if name != "Color":
                    new_name = "Color"
                for v in vals:
                    c = COLORS.get(v["name"].strip().lower())
                    if c and c[0] != v["name"]:
                        changes.append((v["id"], c[0]))
        if new_name or changes:
            # never create two values with the same name inside one option
            names = Counter((dict(changes).get(v["id"], v["name"])) for v in vals)
            if any(n > 1 for n in names.values()):
                changes = []
            if new_name or changes:
                out.append((o["id"], new_name, changes))
    return out


def plan_handle(p, taken):
    h = p["handle"]
    if not (re.fullmatch(r"[\d-]+", h) or re.search(r"-\d+$", h) and not re.search(r"\d+-?(cm|kg|mm|ml|l)$", h)):
        return None
    title = clean_title(p["title"])
    if re.fullmatch(r"\d+", h.rsplit("-", 1)[-1]) and slug(title).endswith("-" + h.rsplit("-", 1)[-1]) and h.startswith(slug(title)[:20]):
        return None  # the number is part of the name (size 5, 2027, model 3115)
    colors = [v["name"] for o in p["options"] if "colo" in o["name"].lower() for v in o["optionValues"]][:2]
    vendor = p["vendor"] if p["vendor"] and p["vendor"].lower() not in title.lower() and p["vendor"] != "Baba Saleh" else ""
    sku = next((v["sku"] for v in p["variants"]["nodes"] if v["sku"]), "")
    for extra in ([], [vendor], colors, [vendor] + colors, [p["productType"]], [sku]):
        cand = slug(" ".join([title] + [e for e in extra if e]))
        if cand and cand != h and cand not in taken and not re.search(r"-\d+$", cand.removesuffix(slug(sku)) if sku else cand):
            return cand
    return None


OWN_VENDORS = {"", "baba saleh", "baba saleh sports egypt", "brands", "brand", "other"}
BRANDS = ["Venum", "Track", "Kiko", "La Mer", "Lamer", "LiveUp", "LivePro", "Kuna", "Wilson", "Dunlop", "Cougar", "Wish",
          "Everlast", "Cressi", "Spurt", "Manta", "Speedo", "Arena", "Adidas", "Nike", "Puma", "Reebok", "Asics", "New Balance",
          "Skechers", "Mikasa", "Molten", "Spalding", "Donic", "Butterfly", "Stiga", "Yonex", "Head", "Babolat", "Clinch",
          "Reusch", "Fox 40", "Arawaza", "Wesing", "Kimo", "Mosha", "Gamma", "Odea", "Mondial", "Heats", "Manizia", "Fox"]
BRAND_NAMES = {"lamer": "La Mer", "la mer": "La Mer", "liveup": "LiveUp", "livepro": "LivePro", "fox": "Fox"}


def plan_vendor(p, title):
    """Products filed under the store name (or "Brands") get the brand their title names, e.g. Venum."""
    if (p["vendor"] or "").strip().lower() not in OWN_VENDORS:
        return None
    for b in BRANDS:
        if re.search(rf"(?<![\w-]){re.escape(b)}(?![\w-])", title, re.I):
            if b.lower() in {"head", "fox"} and not re.match(rf"{b}\b", title, re.I):
                continue  # "Head Guard", "Fox" only when the title starts with the brand
            name = BRAND_NAMES.get(b.lower(), b)
            return name if name != p["vendor"] else None
    return "Baba Saleh" if p["vendor"] != "Baba Saleh" else None


REORDER = """mutation($pid: ID!, $o: [OptionReorderInput!]!) { productOptionsReorder(productId: $pid, options: $o) {
  userErrors { field message } } }"""
LETTER_ORDER = ["XXXS", "XXS", "XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL", "6XL", "7XL", "8XL", "9XL", "10XL"]


def size_key(name):
    """Sort key: letter sizes XS..10XL, then numbers low to high (28/29, 6-8, 10 kg, 2Y), One Size last."""
    v = norm_size(name).upper().replace(" ", "") if name else ""
    v = {"XXL": "2XL", "XXXL": "3XL", "XXXXL": "4XL", "XXXXXL": "5XL", "2XS": "XXS", "3XS": "XXXS"}.get(v, v)
    if v in LETTER_ORDER:
        return (0, LETTER_ORDER.index(v), "")
    m = re.match(r"(\d+(?:[.,]\d+)?)", v)
    if m:
        return (1, float(m.group(1).replace(",", ".")), v)
    if "ONE" in v or "FREE" in v:
        return (3, 0, v)
    return (2, 0, v)


def plan_order(p):
    """Size / weight options whose values are out of order -> reorder input, else None."""
    out, changed = [], False
    for o in p["options"]:
        values = o["optionValues"]
        name = o["name"].lower()
        if any(k in name for k in ("size", "مقاس", "weight", "وزن")) and len(values) > 1:
            ordered = sorted(values, key=lambda v: size_key(v["name"]))
            if [v["id"] for v in ordered] != [v["id"] for v in values]:
                changed = True
                values = ordered
        out.append({"id": o["id"], "values": [{"id": v["id"]} for v in values]})
    return out if changed else None


def main():
    dry = "--dry-run" in sys.argv
    after, products = None, []
    while True:
        page = gql(PRODUCTS_Q, {"a": after})["products"]
        products += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    taken = {p["handle"] for p in products}
    stats = Counter()

    for p in products:
        upd = {"id": p["id"]}
        title = clean_title(p["title"])
        if title != p["title"]:
            upd["title"] = title
            stats["titles cleaned"] += 1
        vendor = plan_vendor(p, title)
        if vendor:
            upd["vendor"] = vendor
            stats["brands set"] += 1
        new_handle = plan_handle(p, taken)
        if new_handle:
            upd["handle"], upd["redirectNewHandle"] = new_handle, True
            taken.discard(p["handle"])
            taken.add(new_handle)
            stats["web addresses made readable"] += 1
        if len(re.sub(r"<[^>]+>", "", p["descriptionHtml"] or "").strip()) < 30:
            dept = next((t for t in p["tags"] if t in DEPT_TEXT), None)
            if dept:
                en, _ = DEPT_TEXT[dept]
                upd["descriptionHtml"] = f"<p>{html.escape(title)} – {en} Delivery across Egypt with cash on delivery.</p>"
                stats["descriptions added"] += 1
        if len(upd) > 1:
            log(f"{'would update' if dry else 'update'} {p['title'][:50]} -> {', '.join(k for k in upd if k != 'id')}")
            if not dry:
                errs = gql(UPDATE, {"p": upd})["productUpdate"]["userErrors"]
                if errs:
                    log(f"  error: {errs}")
        for oid, new_name, changes in plan_options(p):
            stats["options tidied"] += 1
            log(f"{'would tidy' if dry else 'tidy'} options of {p['title'][:40]}: {new_name or ''} {[c[1] for c in changes]}")
            if not dry:
                o = {"id": oid} | ({"name": new_name} if new_name else {})
                v = [{"id": vid, "name": n} for vid, n in changes]
                errs = gql(OPTION_UPDATE, {"pid": p["id"], "o": o, "v": v or None})["productOptionUpdate"]["userErrors"]
                if errs:
                    log(f"  error: {errs}")

        order = plan_order(p)
        if order:
            stats["sizes put in order"] += 1
            if not dry:
                errs = gql(REORDER, {"pid": p["id"], "o": order})["productOptionsReorder"]["userErrors"]
                if errs:
                    log(f"  reorder error {p['title'][:40]}: {errs}")

    # Arabic for option names, colour words and new descriptions
    if not dry:
        for rtype, table in (("PRODUCT_OPTION", OPTION_AR), ("PRODUCT_OPTION_VALUE", VALUE_AR)):
            for rid, res in resources(rtype).items():
                val = res["content"].get("name")
                if val and val[0] in table and (not res["ar"].get("name") or res["ar"]["name"][1]):
                    gql(REGISTER, {"id": rid, "t": [{"key": "name", "value": table[val[0]], "locale": "ar", "translatableContentDigest": val[1]}]})
                    stats[f"arabic {rtype.lower().replace('product_', '')}s"] += 1
        prod_res = resources("PRODUCT")
        by_id = {p["id"]: p for p in products}
        for rid, res in prod_res.items():
            body = res["content"].get("body_html")
            p = by_id.get(rid)
            if not p or not body or "Delivery across Egypt with cash on delivery." not in body[0]:
                continue
            if res["ar"].get("body_html") and not res["ar"]["body_html"][1]:
                continue
            dept = next((t for t in p["tags"] if t in DEPT_TEXT), None)
            ar_title = (res["ar"].get("title") or ("",))[0] or clean_title(p["title"])
            ar = f"<p>{html.escape(ar_title)} – {DEPT_TEXT[dept][1]} توصيل لكل مصر مع الدفع عند الاستلام.</p>"
            gql(REGISTER, {"id": rid, "t": [{"key": "body_html", "value": ar, "locale": "ar", "translatableContentDigest": body[1]}]})
            stats["arabic descriptions"] += 1
    else:
        prod_res = resources("PRODUCT")

    # Report what needs a human (or the nightly assistant) to decide
    report = {"no_arabic_title": [], "no_image": [], "price_zero_active": [], "no_category": []}
    for p in products:
        res = prod_res.get(p["id"], {"ar": {}})
        if not res["ar"].get("title") or res["ar"]["title"][1]:
            report["no_arabic_title"].append({"id": p["id"], "title": clean_title(p["title"])})
        if not p["featuredMedia"] and p["status"] == "ACTIVE":
            report["no_image"].append(p["title"])
        if p["status"] == "ACTIVE" and any(float(v["price"]) == 0 for v in p["variants"]["nodes"]):
            report["price_zero_active"].append(p["title"])
        if not any(t.startswith("cat:") for t in p["tags"]):
            report["no_category"].append(p["title"])
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    json.dump(report, open(REPORT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"quality {dict(stats)} | to review: " + ", ".join(f"{k}={len(v)}" for k, v in report.items()) + f" -> {REPORT}")


if __name__ == "__main__":
    main()
