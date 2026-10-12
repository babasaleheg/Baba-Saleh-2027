"""Register Arabic for the info-page texts in a theme (hero, stats, ribbons, CTAs...).

    python3 translate_pages.py            # live theme
    python3 translate_pages.py <theme_id> # e.g. an unpublished preview

Texts come from page_translations_ar.json (English -> Arabic). Existing, up-to-date Arabic is kept.
"""
import json, os, sys

from seo_bilingual import REGISTER, resources_by_id
from sync import gql, log

HERE = os.path.dirname(os.path.abspath(__file__))
AR = json.load(open(os.path.join(HERE, "page_translations_ar.json"), encoding="utf-8"))


def main():
    if len(sys.argv) > 1:
        tid = f"gid://shopify/OnlineStoreTheme/{sys.argv[1]}"
    else:
        themes = gql("{ themes(first: 20) { nodes { id role } } }")["themes"]["nodes"]
        tid = next(t["id"] for t in themes if t["role"] == "MAIN")
    res = resources_by_id([tid])[tid]
    todo = []
    for key, (value, digest) in res["content"].items():
        if not key.startswith("section.page.") or value not in AR:
            continue
        current = res["ar"].get(key)
        if current and not current[1] and current[0] == AR[value]:
            continue
        todo.append({"key": key, "value": AR[value], "locale": "ar", "translatableContentDigest": digest})
    for i in range(0, len(todo), 100):
        out = gql(REGISTER, {"id": tid, "t": todo[i:i + 100]})["translationsRegister"]
        if out["userErrors"]:
            log(f"errors: {out['userErrors'][:3]}")
    log(f"{tid}: registered {len(todo)} Arabic page texts")


if __name__ == "__main__":
    main()
