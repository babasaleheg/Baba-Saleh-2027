"""Daily check: every active product has SEO title, meta description and image alt text in English
and Arabic, and an Arabic title and description (rule 5). Runs after sync.py seo / seo_bilingual.py,
which fill the gaps; anything still missing here is reported (woo_data/seo_audit.json).

    python3 seo_audit.py
"""
import json, os, re

from sync import gql, log

D = os.environ.get("DATA_DIR", "woo_data")
P_Q = """query($a: String) { products(first: 100, after: $a, query: "status:active") { pageInfo { hasNextPage endCursor }
  nodes { id title seo { title description } media(first: 20) { nodes { id alt mediaContentType } } } } }"""
T_Q = """query($ids: [ID!]!) { translatableResourcesByIds(first: 250, resourceIds: $ids) { nodes { resourceId
  translatableContent { key value } translations(locale: "ar") { key value outdated } } } }"""
LATIN = re.compile(r"[A-Za-z]{4,}")
BRANDS = re.compile(r"\b(Track|Mondial|Cressi|Venum|Wilson|Joola|Sponeta|LivePro|Molten|Everlast|Speedo|Arena|Adidas|Nike|Puma|ASIS|Crocs|Disney|Stitch|Kiko|Molten|Dunlop|Donic|Bosu|TRX|LaMer|La Mer)\b", re.I)


def english_left(text, english=""):
    """Arabic text that still has English words (other than brand names / codes, i.e. words that
    also stand in the English title, like Kuna, Wesing or Derby Star)."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    keep = {w.lower() for w in re.findall(r"[A-Za-z]+", english or "")}
    return any(w.lower() not in keep for w in LATIN.findall(BRANDS.sub("", text)))


def main():
    products, after = [], None
    while True:
        page = gql(P_Q, {"a": after})["products"]
        products += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    issues = {k: [] for k in ("en_seo_title", "en_meta_description", "en_alt", "ar_title", "ar_description",
                              "ar_seo_title", "ar_meta_description", "ar_alt", "ar_has_english")}
    media_ids = []
    for p in products:
        # an empty SEO title is fine: Shopify then uses the product title (it stores an equal one as empty)
        if not (p["seo"]["title"] or "").strip() and len(p["title"]) > 70:
            issues["en_seo_title"].append(p["title"])
        if not (p["seo"]["description"] or "").strip():
            issues["en_meta_description"].append(p["title"])
        imgs = [m for m in p["media"]["nodes"] if m["mediaContentType"] == "IMAGE"]
        if any(not (m["alt"] or "").strip() for m in imgs):
            issues["en_alt"].append(p["title"])
        media_ids += [(p["title"], m["id"]) for m in imgs]
    by_id = {p["id"]: p for p in products}
    ids = list(by_id)
    for i in range(0, len(ids), 250):
        for n in gql(T_Q, {"ids": ids[i:i + 250]})["translatableResourcesByIds"]["nodes"]:
            title = by_id[n["resourceId"]]["title"]
            content = {c["key"]: c["value"] for c in n["translatableContent"]}
            ar = {t["key"]: t["value"] for t in n["translations"] if t["value"] and not t["outdated"]}
            if not ar.get("title"):
                issues["ar_title"].append(title)
            if content.get("body_html") and not ar.get("body_html"):
                issues["ar_description"].append(title)
            if not ar.get("meta_title") and not ar.get("title"):
                issues["ar_seo_title"].append(title)
            if not ar.get("meta_description"):
                issues["ar_meta_description"].append(title)
            if any(english_left(ar.get(k), title) for k in ("title", "meta_title", "meta_description")):
                issues["ar_has_english"].append(title)
    # Arabic image alt text (MEDIA_IMAGE translations)
    mids = [m for _, m in media_ids]
    titles = dict((m, t) for t, m in media_ids)
    missing_alt = set()
    for i in range(0, len(mids), 250):
        for n in gql(T_Q, {"ids": mids[i:i + 250]})["translatableResourcesByIds"]["nodes"]:
            ar = {t["key"]: t["value"] for t in n["translations"] if t["value"] and not t["outdated"]}
            if not ar.get("alt"):
                missing_alt.add(titles.get(n["resourceId"], n["resourceId"]))
    issues["ar_alt"] = sorted(missing_alt)
    json.dump(issues, open(os.path.join(D, "seo_audit.json"), "w"), ensure_ascii=False, indent=1)
    counts = {k: len(v) for k, v in issues.items() if v}
    log(f"seo-audit {{'products': {len(products)}, 'images': {len(mids)}, 'gaps': {counts or 'none'}}}")


if __name__ == "__main__":
    main()
