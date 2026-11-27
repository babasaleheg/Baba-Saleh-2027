"""Sale wording outside the time-switched sections (owner, Nov 27 2026):
  wf   = Fri Nov 27 only: "Mega Sale · White Friday – today only"
  nov  = Nov 28 – 30:     "November Sale – until Nov 30"
  end  = from Dec 1:      the sale line leaves the announcement bar, the home sale section is hidden
Changes the offers collection's name (EN + AR), the announcement bar's sale message (block a3) and the
home page sale section (index.json flash_sale), with their Arabic translations. The banners, strip,
offers-page hero and menu link switch by themselves (see theme/). Run from tools/woo_to_shopify:

    python3 ../../offers/2026-11-white-friday/switch.py nov
"""
import json, sys, time

sys.path.insert(0, ".")
from sync import gql, log  # noqa: E402
from deploy_theme import THEMES_Q, FILE_BODY_Q, UPSERT  # noqa: E402

COLL = "gid://shopify/Collection/492369248304"
REG = """mutation($id: ID!, $t: [TranslationInput!]!) { translationsRegister(resourceId: $id, translations: $t) { userErrors { message } } }"""
TR_Q = """query($id: ID!) { translatableResource(resourceId: $id) { translatableContent { key value digest } } }"""

PHASES = {
    "wf": {
        "coll": ("White Friday – Mega Sale", "ميجا سيل الجمعة البيضاء"),
        "a3": ("Mega Sale · White Friday – today only, up to 29% off", "ميجا سيل الجمعة البيضاء – النهارده بس، خصم لحد 29%"),
        "flash": {"eyebrow": ("Today only", "النهارده بس"), "heading": ("Mega Sale · White Friday", "ميجا سيل الجمعة البيضاء"),
                  "text": ("Up to 29% off kids’ toys, swim and gym gear. Today only, until 11:59 pm.", "خصم لحد 29% على ألعاب الأطفال ومستلزمات السباحة والجيم. النهارده بس لحد 11:59 مساءً."),
                  "button_label": ("Shop the Mega Sale", "تسوق الميجا سيل"), "end_date": "2026-11-27 23:59:59 +0200"},
    },
    "nov": {
        "coll": ("November Sale", "عروض نوفمبر"),
        "a3": ("November Sale – up to 29% off until Nov 30", "عروض نوفمبر – خصم لحد 29% لحد 30 نوفمبر"),
        "flash": {"eyebrow": ("Until Nov 30", "لحد 30 نوفمبر"), "heading": ("November Sale", "عروض نوفمبر"),
                  "text": ("Up to 29% off kids’ toys, swim and gym gear. Last day Monday, Nov 30, 11:59 pm.", "خصم لحد 29% على ألعاب الأطفال ومستلزمات السباحة والجيم. آخر يوم الاثنين 30 نوفمبر، 11:59 مساءً."),
                  "button_label": ("Shop the November Sale", "تسوق عروض نوفمبر"), "end_date": "2026-11-30 23:59:59 +0200"},
    },
}


def theme():
    return next(t for t in gql(THEMES_Q)["themes"]["nodes"] if t["role"] == "MAIN")["id"]


def load(tid, name):
    s = gql(FILE_BODY_Q, {"id": tid, "names": [name]})["theme"]["files"]["nodes"][0]["body"]["content"]
    i = s.index("{\n") if s.lstrip().startswith("/*") else 0
    return s[:i], json.loads(s[i:])


def save(tid, name, hdr, data):
    errs = gql(UPSERT, {"id": tid, "files": [{"filename": name, "body": {"type": "TEXT", "value": hdr + json.dumps(data, ensure_ascii=False, indent=2)}}]})["themeFilesUpsert"]["userErrors"]
    if errs:
        sys.exit(f"{name}: {errs}")


def arabic(rid, wanted):
    """wanted: {key prefix: (english now in the setting, arabic)}; waits until Shopify shows the new English."""
    for _ in range(20):
        content = gql(TR_Q, {"id": rid})["translatableResource"]["translatableContent"]
        t, ok = [], True
        for prefix, (en, ar) in wanted.items():
            c = next((c for c in content if c["key"].startswith(prefix)), None)
            if not c or c["value"] != en:
                ok = False
                break
            t.append({"locale": "ar", "key": c["key"], "value": ar, "translatableContentDigest": c["digest"]})
        if ok:
            errs = gql(REG, {"id": rid, "t": t})["translationsRegister"]["userErrors"]
            if errs:
                sys.exit(f"{rid}: {errs}")
            return
        time.sleep(3)
    sys.exit(f"{rid}: Shopify did not show the new text, Arabic not registered")


def main(phase):
    tid = theme()
    num = tid.rsplit("/", 1)[1]
    hg_id = f"gid://shopify/OnlineStoreThemeSectionGroup/header-group?theme_id={num}"
    ix_id = f"gid://shopify/OnlineStoreThemeJsonTemplate/index?theme_id={num}"
    hdr, hg = load(tid, "sections/header-group.json")
    ihdr, ix = load(tid, "templates/index.json")
    ann = hg["sections"]["announcement"]
    fs = ix["sections"]["flash_sale"]
    if phase == "end":
        ann["block_order"] = [b for b in ann["block_order"] if b != "a3"]
        fs["disabled"] = True
        save(tid, "sections/header-group.json", hdr, hg)
        save(tid, "templates/index.json", ihdr, ix)
        log("sale wording removed (announcement a3, home sale section hidden)")
        return
    p = PHASES[phase]
    en, ar = p["coll"]
    gql("""mutation($i: CollectionInput!) { collectionUpdate(input: $i) { userErrors { message } } }""",
        {"i": {"id": COLL, "title": en, "seo": {"title": f"{en} – up to 29% off | Baba Saleh"}}})
    content = {c["key"]: c for c in gql(TR_Q, {"id": COLL})["translatableResource"]["translatableContent"]}
    gql(REG, {"id": COLL, "t": [{"locale": "ar", "key": k, "value": v, "translatableContentDigest": content[k]["digest"]}
                                for k, v in (("title", ar), ("meta_title", f"{ar} – خصم لحد 29% | بابا صالح"))]})
    ann["blocks"]["a3"]["settings"].update({"text": p["a3"][0], "icon": "bolt", "link": "shopify://collections/november-offers"})
    if "a3" not in ann["block_order"]:
        ann["block_order"].insert(2, "a3")
    fs.pop("disabled", None)
    for k, v in p["flash"].items():
        fs["settings"][k] = v if isinstance(v, str) else v[0]
    fs["settings"]["collection"] = "november-offers"
    save(tid, "sections/header-group.json", hdr, hg)
    save(tid, "templates/index.json", ihdr, ix)
    arabic(hg_id, {"section.sections/header-group.json.announcement.a3.text": p["a3"]})
    arabic(ix_id, {f"section.index.json.flash_sale.{k}": v for k, v in p["flash"].items() if not isinstance(v, str)})
    log(f"sale wording set to {phase}")


if __name__ == "__main__":
    main(sys.argv[1])
