"""Make Arabic (and Egyptian) search find the right products.

Shopify search matches whole words in the title and tags. Shoppers type everyday Egyptian
words ("كورة", "جزمة", "ترنج") while titles use another spelling ("كرة", "حذاء", "ترينج"),
so those searches miss most products. For every product this adds the other spellings of
the words in its English or Arabic name as search tags (only tags from the lists below are
ever added), and removes words from the lists that no longer fit (e.g. after a product is
renamed). Runs nightly.

    python3 search_words.py            # add missing search words
    python3 search_words.py --dry-run
"""
import re, sys
from collections import Counter

from seo_bilingual import resources
from sync import gql, log

DRY = "--dry-run" in sys.argv

# (English words in the title, Arabic spellings: all of them become search tags)
GROUPS = [
    (r"\bfootball|soccer", ["كرة قدم", "كورة", "كوره", "فوتبول"]),
    (r"\bballs?\b", ["كرة", "كورة", "كوره", "كور", "بول"]),
    (r"basketball", ["كرة سلة", "باسكت", "باسكت بول", "سلة"]),
    (r"volleyball", ["كرة طائرة", "فولي", "فوليبول", "طايرة"]),
    (r"handball", ["كرة يد", "هاند بول", "هاندبول"]),
    (r"table tennis|ping ?pong", ["تنس طاولة", "بينج بونج", "بنج بونج", "تنس طاوله"]),
    (r"\btennis\b(?! table)", ["تنس", "تنس ارضي"]),
    (r"padel", ["بادل", "باديل"]),
    (r"squash", ["اسكواش", "سكواش"]),
    (r"badminton", ["ريشة", "بادمنتون", "تنس ريشة"]),
    (r"racket|racquet", ["مضرب", "راكيت", "مضارب"]),
    (r"boxing|punch|sandbag|mma", ["ملاكمة", "بوكس", "بوكسينج", "كيس ملاكمة"]),
    (r"gloves?", ["جوانتي", "جوانتى", "جلافز", "قفاز", "قفازات"]),
    (r"^(?!.*(oscar|trophy|award)).*(shoes?|sneakers?|running trainers?)", ["حذاء", "جزمة", "جزمه", "كوتشي", "كوتشى", "سنيكرز"]),
    (r"slippers?|sandals?|slides?|flip.?flops?|crocs|clogs", ["شبشب", "صندل", "كروكس", "شباشب"]),
    (r"tracksuit|track suit", ["ترنج", "ترينج", "تريننج", "بدلة رياضية", "بدلة رياضيه"]),
    (r"t-?shirt|\btee\b|jersey|polo", ["تيشيرت", "تيشرت", "تي شيرت", "فانلة", "فانله"]),
    (r"pants|trousers|leggings?|joggers?", ["بنطلون", "بنطال", "ليجن", "ليجنز", "سويت بانتس"]),
    (r"shorts", ["شورت", "شورتات"]),
    (r"jacket|hoodie", ["جاكيت", "جاكت", "هودي", "سويت شيرت"]),
    (r"sports bra|\bbra\b", ["برا رياضي", "توب رياضي"]),
    (r"swimsuit|swimwear|swim shorts?|swim set|bikini|jammers?|swim brief", ["مايوه", "مايو", "ملابس سباحة", "لبس بحر"]),
    (r"burkini|modest swim", ["بوركيني", "بوركينى", "مايوه شرعي", "مايوه محجبات"]),
    (r"goggles", ["نظارة سباحة", "نضارة", "نظارة", "نضارة سباحة"]),
    (r"swim(ming)? cap", ["بونيه", "بونيه سباحة", "غطاء رأس سباحة"]),
    (r"float|swim ring|arm ?bands?|inflatable|life jacket", ["عوامة", "عوامات", "عوامه", "بلبول", "سترة نجاة"]),
    (r"fins\b", ["زعانف", "فينز", "زعنفة"]),
    (r"snorkel|diving", ["غطس", "سنوركل", "شنوركل"]),
    (r"dumbbells?|kettlebell|weights?|plates?|barbell|\bbar\b", ["دمبل", "دمبلز", "دامبل", "أثقال", "اوزان", "وزن", "حديد"]),
    (r"resistance band|loop band|power band|toning tube|expander", ["استك", "استيك", "حبل مقاومة", "باند", "مطاط"]),
    (r"jump rope|skipping rope", ["نط حبل", "حبل نط", "حبل", "نطاطة"]),
    (r"yoga|pilates|mat\b", ["يوجا", "يوغا", "مات", "حصيرة", "مرتبة"]),
    (r"bench|pull.?up|treadmill|machine|station", ["جهاز", "اجهزة رياضية", "بنش", "عقلة"]),
    (r"knee|ankle|elbow|wrist|back support|brace|kinesiology", ["رباط", "دعامة", "ركبة", "شداد", "حزام ظهر"]),
    (r"bottle|shaker", ["زجاجة", "زمزمية", "ازازة", "قزازة", "شيكر", "مية"]),
    (r"backpack|\bbags?\b", ["شنطة", "شنطه", "حقيبة", "شنط", "باك باك"]),
    (r"\bcap\b|\bhat\b", ["كاب", "طاقية", "قبعة", "برنيطة"]),
    (r"trophy|trophies|\bcup\b|oscar", ["كأس", "كاس", "كؤوس", "درع", "اوسكار"]),
    (r"medal", ["ميدالية", "ميداليات", "مدالية"]),
    (r"scooter", ["سكوتر", "اسكوتر", "سكوتير"]),
    (r"bicycle|\bbike\b|tricycle|balance bike", ["عجلة", "عجله", "دراجة", "بسكلتة", "عجلة اطفال"]),
    (r"skate|roller", ["باتيناج", "سكيت", "سكيتنج", "اسكيت"]),
    (r"skateboard|penny board", ["سكيت بورد", "لوح تزلج"]),
    (r"toy|blocks|doll|\bcars?\b|puzzle", ["لعبة", "لعب", "العاب", "ألعاب", "لعب اطفال"]),
    (r"water gun|blaster", ["مسدس مية", "مسدس مياه", "رشاش مية"]),
    (r"tent|camping|sleeping bag", ["خيمة", "خيمه", "تخييم", "رحلات"]),
    (r"whistle", ["صفارة", "صفاره"]),
    (r"cone|hurdle|ladder|agility", ["اقماع", "قمع", "سلم تدريب", "حواجز"]),
    (r"socks", ["شراب", "جوارب", "شرابات"]),
    (r"flag", ["علم", "اعلام", "علم مصر"]),
    (r"chess|darts?|board game|bingo", ["شطرنج", "سهام", "ألعاب جماعية"]),
    (r"billiard|pool cue", ["بلياردو", "بلياردو عصا", "سنوكر"]),
    (r"karate|judo|taekwondo|kung fu", ["كاراتيه", "جودو", "تايكوندو", "كونغ فو", "فنون قتالية"]),
    (r"head ?guard|mouth guard|shin guard|chest guard", ["واقي", "واقى", "حامي"]),
    (r"kids|children|baby|junior", ["اطفال", "أطفال"]),
    (r"\bboys?\b|boys'", ["ولادي", "ولادى", "اطفال"]),
    (r"\bgirls?\b|girls'", ["بناتي", "بناتى", "اطفال"]),
    (r"women|ladies", ["حريمي", "حريمى", "نسائي"]),
    (r"(?<!wo)\bmen\b|(?<!wo)men's", ["رجالي", "رجالى"]),
]
ALL_WORDS = {w for _, words in GROUPS for w in words}

PRODUCTS_Q = """query($a: String) { products(first: 250, after: $a, query: "status:active") {
  pageInfo { hasNextPage endCursor } nodes { id title tags } } }"""
TAGS_REMOVE = """mutation($id: ID!, $t: [String!]!) { tagsRemove(id: $id, tags: $t) { userErrors { message } } }"""
TAGS_ADD = """mutation($id: ID!, $t: [String!]!) { tagsAdd(id: $id, tags: $t) { userErrors { message } } }"""


def normalize(text):
    """Arabic letters folded so spelling variants compare equal (أ/إ/آ->ا, ة->ه, ى->ي)."""
    text = re.sub("[أإآ]", "ا", text or "")
    return text.replace("ة", "ه").replace("ى", "ي").lower()


def words_for(title_en, title_ar):
    en = (title_en or "").lower().replace("’", "'")
    ar = normalize(title_ar)
    out = set()
    for rx, words in GROUPS:
        if re.search(rx, en):
            out.update(words)
        elif any(normalize(w) in ar for w in words) and not re.search(r"oscar|trophy|award", en):
            out.update(words)
    return out


def main():
    ar_titles = {rid: (r["ar"].get("title") or (None,))[0] for rid, r in resources("PRODUCT").items()}
    after, stats = None, Counter()
    while True:
        page = gql(PRODUCTS_Q, {"a": after})["products"]
        for p in page["nodes"]:
            stats["products"] += 1
            want = words_for(p["title"], ar_titles.get(p["id"]))
            missing = sorted(want - set(p["tags"]))
            stale = sorted((set(p["tags"]) & ALL_WORDS) - want)
            if stale:
                stats["words removed"] += len(stale)
                if not DRY:
                    gql(TAGS_REMOVE, {"id": p["id"], "t": stale})
                elif stats["words removed"] <= 40:
                    log(p["title"], "-", stale)
            if not missing:
                continue
            stats["products updated"] += 1
            stats["words added"] += len(missing)
            if not DRY:
                errs = gql(TAGS_ADD, {"id": p["id"], "t": missing})["tagsAdd"]["userErrors"]
                if errs:
                    log("tags failed", p["title"], errs)
            elif stats["products updated"] <= 5:
                log(p["title"], "+", missing[:12])
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    log("search-words", dict(stats))


if __name__ == "__main__":
    main()
