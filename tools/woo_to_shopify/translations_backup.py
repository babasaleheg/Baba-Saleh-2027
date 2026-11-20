"""Nightly copy of every Arabic translation, so it can be put back in one step.

    python3 translations_backup.py            # save backups/translations_ar.json (+ a dated copy)
    python3 translations_backup.py restore [FILE]   # put every saved Arabic translation back
    python3 translations_backup.py count      # Arabic translations on the store now, per type

Why: on Nov 18 2026 the store's default language was switched to Arabic in the admin, which deleted
every Arabic translation (products, collections, menus, theme text...). The backup keeps the
English source digest-free: on restore each value is matched to the current content by key, so it
works even after the English text changed (outdated ones are skipped and reported).
"""
import datetime
import gzip
import json
import os
import sys

from sync import gql, log

AR = "ar"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "backups")
TYPES = ["PRODUCT", "PRODUCT_OPTION", "PRODUCT_OPTION_VALUE", "COLLECTION", "PAGE", "ARTICLE", "BLOG",
         "MENU", "LINK", "SHOP", "SHOP_POLICY", "FILTER", "METAOBJECT", "MEDIA_IMAGE", "COLLECTION_IMAGE",
         "DELIVERY_METHOD_DEFINITION", "ONLINE_STORE_THEME", "ONLINE_STORE_THEME_JSON_TEMPLATE",
         "ONLINE_STORE_THEME_SECTION_GROUP", "ONLINE_STORE_THEME_SETTINGS_DATA_SECTIONS",
         "ONLINE_STORE_THEME_SETTINGS_CATEGORY", "ONLINE_STORE_THEME_LOCALE_CONTENT", "ONLINE_STORE_THEME_APP_EMBED"]

Q = """query($t: TranslatableResourceType!, $a: String) { translatableResources(first: 100, resourceType: $t, after: $a) {
  pageInfo { hasNextPage endCursor }
  nodes { resourceId translatableContent { key value digest } translations(locale: "ar") { key value outdated } } } }"""
REGISTER = """mutation($id: ID!, $t: [TranslationInput!]!) { translationsRegister(resourceId: $id, translations: $t) {
  userErrors { field message } } }"""


def dump(types=TYPES):
    out = {}
    for t in types:
        after, n = None, 0
        while True:
            try:
                page = gql(Q, {"t": t, "a": after})["translatableResources"]
            except RuntimeError as e:
                log(f"{t}: skipped ({str(e)[:120]})")
                break
            for node in page["nodes"]:
                tr = {x["key"]: x["value"] for x in node["translations"] if x["value"]}
                if tr:
                    src = {c["key"]: c["value"] for c in node["translatableContent"]}
                    out[node["resourceId"]] = {"type": t, "ar": tr, "en": {k: src.get(k) for k in tr}}
                    n += 1
            if not page["pageInfo"]["hasNextPage"]:
                break
            after = page["pageInfo"]["endCursor"]
    return out


def save():
    data = dump()
    locales = gql("{ shopLocales { locale primary published } }")["shopLocales"]
    snap = {"saved": datetime.datetime.utcnow().isoformat() + "Z", "shopLocales": locales, "resources": data}
    os.makedirs(OUT, exist_ok=True)
    count = {}
    for r in data.values():
        count[r["type"]] = count.get(r["type"], 0) + 1
    # never overwrite a good backup with an empty or much smaller one (e.g. right after translations were lost)
    main = os.path.join(OUT, "translations_ar.json.gz")
    if os.path.exists(main):
        old = json.load(gzip.open(main, "rt", encoding="utf-8"))
        if len(data) < 0.8 * len(old["resources"]):
            keep = os.path.join(OUT, f"translations_ar.{datetime.date.today()}.small.json.gz")
            json.dump(snap, gzip.open(keep, "wt", encoding="utf-8"), ensure_ascii=False)
            log(f"RULE BROKEN: Arabic translations dropped from {len(old['resources'])} to {len(data)} resources; "
                f"good backup kept, run: python3 translations_backup.py restore")
            return 1
    json.dump(snap, gzip.open(main, "wt", encoding="utf-8"), ensure_ascii=False)
    log(f"translations-backup {{'resources': {len(data)}, 'by type': {count}}}")
    return 0


def restore(path=None):
    path = path or os.path.join(OUT, "translations_ar.json.gz")
    snap = json.load(gzip.open(path, "rt", encoding="utf-8"))
    by_type = {}
    for rid, r in snap["resources"].items():
        by_type.setdefault(r["type"], {})[rid] = r
    done = skipped = 0
    for t, items in by_type.items():
        after = None
        while True:
            page = gql(Q, {"t": t, "a": after})["translatableResources"]
            for node in page["nodes"]:
                r = items.get(node["resourceId"])
                if not r:
                    continue
                have = {x["key"] for x in node["translations"] if x["value"] and not x["outdated"]}
                digest = {c["key"]: (c["value"], c["digest"]) for c in node["translatableContent"]}
                batch = []
                for k, v in r["ar"].items():
                    if k in have or k not in digest:
                        continue
                    if r["en"].get(k) is not None and digest[k][0] != r["en"][k]:
                        skipped += 1  # English changed since the backup: the nightly writes a fresh one
                        continue
                    batch.append({"locale": AR, "key": k, "value": v, "translatableContentDigest": digest[k][1]})
                if batch:
                    errs = gql(REGISTER, {"id": node["resourceId"], "t": batch})["translationsRegister"]["userErrors"]
                    if errs:
                        log(f"{node['resourceId']}: {errs[:1]}")
                    else:
                        done += len(batch)
            if not page["pageInfo"]["hasNextPage"]:
                break
            after = page["pageInfo"]["endCursor"]
    log(f"translations-restore {{'fields': {done}, 'skipped (English changed)': {skipped}}}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "save"
    if cmd == "restore":
        restore(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "count":
        data = dump()
        c = {}
        for r in data.values():
            c[r["type"]] = c.get(r["type"], 0) + 1
        log(f"arabic translations now: {len(data)} resources {c}")
    else:
        sys.exit(save())
