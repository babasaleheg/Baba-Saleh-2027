"""Bilingual (English + Arabic) SEO and alt text for every product, image and collection.

Usage:
    python3 seo_bilingual.py            # apply
    DRY_RUN=1 python3 seo_bilingual.py  # report only

Rules (safe to run on every sync, so new products are covered automatically):
- English SEO title/description: filled when empty (sync.py seo does the same).
- English image alt: "<title> – <category>[ – <brand>]" (+ " (n)" for extra photos); set when
  the alt is empty or was generated from the title, never when someone wrote their own.
- Arabic (translations, locale "ar"): SEO title, SEO description and image alt built from the
  Arabic product title and the Arabic name of the product's category collection; collection
  SEO in Arabic from the Arabic collection title. Existing Arabic translations that are not
  outdated are kept.
- Brand names: Track is always تراك in Arabic (also fixed inside Arabic product titles).

Category = the product's category collection, resolved from its cat:/group:/dept: tags
(same mapping as snippets/product-category.liquid), else its first real collection,
else its product type.

Needs app scopes: write_products, write_files, read/write_translations, read_locales.
"""
import os, re

from sync import STORE, clip, gql, log, own_brand, product_seo_description, product_seo_title

DRY = bool(os.environ.get("DRY_RUN"))
AR = "ar"
STORE_AR = "بابا صالح"
BRANDS_AR = {"Track": "تراك", "Baba Saleh": STORE_AR}
# Wrong renderings of the brand Track seen in machine translations -> تراك
TRACK_WRONG = re.compile(r"(?<![\w؀-ۿ])(?:ال)?(?:مسار|تريك|ترك|تراكت)(?![\w؀-ۿ])")

# tag value -> collection handle (keep in sync with snippets/product-category.liquid)
LEAF = dict(x.split(":") for x in (
    "football:football-equipment,basketball:basketball-equipment,volleyball:volleyball-equipment,handball:handball-equipment,"
    "hockey:hockey-equipment,coaching:coaching-equipment,tennis:tennis-equipment,padel:padel-equipment,squash:squash-equipment,"
    "badminton:badminton-equipment,table-tennis:ping-pong-equipment,speedball:speed-ball-equipment,boxing:boxing-mma,"
    "karate:karate-equipment,taekwondo:taekwondo-equipment,skating:roller-skating-equipment,skateboards:skateboard,"
    "scooters:scooters,cycling:cycling,billiards:billiard-equipment,ballet:ballet-equipment,camping:camping-equipment,"
    "weights:weights-and-bars,gym-machines:gym-equipment,resistance-bands:resistance-band,yoga:yoga-equipment,"
    "jump-ropes:jump-ropes,fitness-accessories:gym-accessories,supports:medical-equipment,goggles:goggles,swim-caps:swim-caps,"
    "swim-training:swim-training,diving:diving-snorkeling,swim-accessories:swim-accessories,swim-safety:life-jackets-swim-rings,"
    "pool-floats:floats,beach-toys:beach-toys,beach-bags-hats:beach-bag-sea-hat,men-swimwear:men-swimwear,"
    "women-swimwear:women-swimwear,kids-swimwear:kids-swimwear,tracksuits:tracksuits,t-shirts:shirts,shorts:shorts,pants:pants,"
    "jackets:jackets,sports-bras:sports-bras,running-shoes:running-shoes,football-shoes:football-shoes,slippers:slippers,"
    "beach-shoes:beach-shoes,backpacks:bags-backpacks,handbags:handbags,water-bottles:water-bottles,hats:hats,flags:flags,"
    "toys:kids-toys,games:games,trophies:trophies-cups,medals:medals").split(","))
GROUP = dict(x.split(":") for x in "team-sports:team-sports,racket-sports:racket-equipment,martial-arts:martial-arts,"
             "wheels:skates-scooters-bikes,swimwear:swimwear".split(","))
DEPT = dict(x.split(":") for x in "sports:sports,fitness:fitness,swimming:swimming-equipment,beach:beach-equipment,"
            "clothing:sportswear,footwear:shoes,accessories:accessories,kids-toys:toys-2026,trophies:trophy-cups-medals".split(","))
SKIP_COLLECTIONS = {"frontpage", "sale", "all"}

PRODUCTS_Q = """query($after: String) { products(first: 50, after: $after) {
  pageInfo { hasNextPage endCursor }
  nodes { id title vendor productType tags description seo { title description }
    collections(first: 10) { nodes { handle } }
    media(first: 50) { nodes { id alt mediaContentType } } } } }"""
COLLECTIONS_Q = """query($after: String) { collections(first: 100, after: $after) {
  pageInfo { hasNextPage endCursor } nodes { id handle title productsCount { count } } } }"""
RESOURCES_Q = """query($type: TranslatableResourceType!, $after: String) {
  translatableResources(resourceType: $type, first: 100, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes { resourceId translatableContent { key value digest } translations(locale: "ar") { key value outdated } } } }"""
RESOURCES_BY_ID_Q = """query($ids: [ID!]!) { translatableResourcesByIds(resourceIds: $ids, first: 250) {
  nodes { resourceId translatableContent { key value digest } translations(locale: "ar") { key value outdated } } } }"""
REGISTER = """mutation($id: ID!, $t: [TranslationInput!]!) { translationsRegister(resourceId: $id, translations: $t) {
  userErrors { field message } } }"""
PRODUCT_SEO_UPDATE = """mutation($p: ProductUpdateInput!) { productUpdate(product: $p) { userErrors { field message } } }"""
FILE_ALT_UPDATE = """mutation($files: [FileUpdateInput!]!) { fileUpdate(files: $files) { userErrors { field message } } }"""


def resources(rtype):
    """resourceId -> {"content": {key: (value, digest)}, "ar": {key: (value, outdated)}}"""
    out, after = {}, None
    while True:
        page = gql(RESOURCES_Q, {"type": rtype, "after": after})["translatableResources"]
        for n in page["nodes"]:
            out[n["resourceId"]] = {"content": {c["key"]: (c["value"], c["digest"]) for c in n["translatableContent"]},
                                    "ar": {t["key"]: (t["value"], t["outdated"]) for t in n["translations"]}}
        if not page["pageInfo"]["hasNextPage"]:
            return out
        after = page["pageInfo"]["endCursor"]


def resources_by_id(ids):
    out = {}
    for i in range(0, len(ids), 250):
        for n in gql(RESOURCES_BY_ID_Q, {"ids": ids[i:i + 250]})["translatableResourcesByIds"]["nodes"]:
            out[n["resourceId"]] = {"content": {c["key"]: (c["value"], c["digest"]) for c in n["translatableContent"]},
                                    "ar": {t["key"]: (t["value"], t["outdated"]) for t in n["translations"]}}
    return out


def register(rid, res, values, stats, force=()):
    """Write Arabic translations for keys whose Arabic is missing/outdated (or listed in force)."""
    batch = []
    for key, value in values.items():
        if not value or key not in res["content"]:
            continue
        current = res["ar"].get(key)
        if current and not current[1] and key not in force:
            continue  # someone's (or an earlier run's) up-to-date translation: keep it
        if current and current[0] == value and not current[1]:
            continue
        batch.append({"locale": AR, "key": key, "value": value, "translatableContentDigest": res["content"][key][1]})
    if batch and not DRY:
        r = gql(REGISTER, {"id": rid, "t": batch})["translationsRegister"]
        if r["userErrors"]:
            log("translation failed", rid, r["userErrors"])
            return
    stats["ar_fields"] += len(batch)


def brand_ar(vendor):
    return BRANDS_AR.get(vendor, vendor)


def fix_track(text):
    return TRACK_WRONG.sub("تراك", text) if text else text


def category_handle(p):
    tags = {t.split(":", 1)[0]: t.split(":", 1)[1] for t in p["tags"] if ":" in t}
    for key, table in (("cat", LEAF), ("group", GROUP), ("dept", DEPT)):
        if tags.get(key) in table:
            return table[tags[key]]
    for c in p["collections"]["nodes"]:
        if c["handle"] not in SKIP_COLLECTIONS:
            return c["handle"]
    return None


def is_generated_alt(alt, p):
    """Alt text that a script produced from the title (safe to replace); hand-written alt is kept."""
    alt = (alt or "").strip()
    return not alt or alt.startswith(p["title"])


def main():
    stats = {"products": 0, "en_seo": 0, "en_alt": 0, "ar_fields": 0, "no_ar_title": 0, "track_fixed": 0, "collections": 0}
    cols, after = {}, None
    while True:
        page = gql(COLLECTIONS_Q, {"after": after})["collections"]
        cols.update({c["handle"]: c for c in page["nodes"]})
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    col_tr = resources("COLLECTION")
    ar_col_title = {h: (col_tr.get(c["id"], {}).get("ar", {}).get("title") or (None,))[0] for h, c in cols.items()}

    # ---- collections: Arabic SEO
    for h, c in cols.items():
        res = col_tr.get(c["id"])
        title_ar = ar_col_title.get(h)
        if not res or not title_ar:
            continue
        register(c["id"], res, {
            "meta_title": clip(f"{title_ar} | {STORE_AR} مصر", 70),
            "meta_description": clip(f"تسوق {title_ar} من {STORE_AR}: {c['productsCount']['count']} منتج، "
                                     "الدفع عند الاستلام وشحن سريع لجميع محافظات مصر.", 160),
        }, stats)
        stats["collections"] += 1

    # ---- products
    prod_tr = resources("PRODUCT")
    after = None
    while True:
        page = gql(PRODUCTS_Q, {"after": after})["products"]
        for p in page["nodes"]:
            stats["products"] += 1
            handle = category_handle(p)
            category = cols[handle]["title"] if handle in cols else (p["productType"] or "Sports gear")
            category_ar = ar_col_title.get(handle) or ""
            brand = "" if own_brand(p) else f" – {p['vendor']}"

            # English SEO (fill empty only)
            seo = {"title": p["seo"]["title"] or product_seo_title(p), "description": p["seo"]["description"] or product_seo_description(p)}
            if seo != p["seo"] and not DRY:
                gql(PRODUCT_SEO_UPDATE, {"p": {"id": p["id"], "seo": seo}})
                stats["en_seo"] += 1

            # English alt text linked to the category
            images = [m for m in p["media"]["nodes"] if m["mediaContentType"] == "IMAGE"]
            base = clip(f"{p['title']} – {category}{brand}", 480)
            files = []
            for i, m in enumerate(images):
                alt = base if i == 0 else f"{base} ({i + 1})"
                if is_generated_alt(m["alt"], p) and m["alt"] != alt:
                    files.append({"id": m["id"], "alt": alt})
            if files and not DRY:
                r = gql(FILE_ALT_UPDATE, {"files": files})["fileUpdate"]
                if r["userErrors"]:
                    log("alt failed", p["title"], r["userErrors"])
            stats["en_alt"] += len(files)

            # Arabic
            res = prod_tr.get(p["id"])
            title_ar = (res or {}).get("ar", {}).get("title", (None,))[0] if res else None
            if not title_ar:
                stats["no_ar_title"] += 1
                continue
            # Only Track-branded products: elsewhere words like مسار may be correct
            track_related = p["vendor"] == "Track" or re.search(r"\bTrack\b", p["title"])
            fixed = fix_track(title_ar) if track_related else title_ar
            force = ()
            if track_related and "تراك" not in fixed and re.search(r"\bTrack\b", p["title"]):
                fixed = f"{fixed} تراك"
            if fixed != title_ar:
                stats["track_fixed"] += 1
                title_ar, force = fixed, ("title",)
            brand_part = "" if own_brand(p) else f" – {brand_ar(p['vendor'])}"
            cat_part = f" – {category_ar}" if category_ar else ""
            register(p["id"], res, {
                "title": title_ar,
                "meta_title": next((t for t in (f"{title_ar}{brand_part} | {STORE_AR} مصر", f"{title_ar}{brand_part}",
                                                f"{title_ar} | {STORE_AR} مصر") if len(t) <= 70), clip(title_ar, 70)),
                "meta_description": clip(f"{title_ar}{brand_part}{cat_part}. الدفع عند الاستلام وشحن سريع لجميع محافظات مصر من {STORE_AR}.", 160),
            }, stats, force)

            # Arabic alt text for every image
            if images:
                media_res = resources_by_id([m["id"] for m in images])
                alt_ar = clip(f"{title_ar}{cat_part}{brand_part}", 480)
                for i, m in enumerate(images):
                    mres = media_res.get(m["id"])
                    if mres:
                        register(m["id"], mres, {"alt": alt_ar if i == 0 else f"{alt_ar} ({i + 1})"}, stats)
            if stats["products"] % 100 == 0:
                log("seo-bilingual", stats)
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    log("seo-bilingual done" + (" (dry run)" if DRY else ""), stats)


if __name__ == "__main__":
    main()
