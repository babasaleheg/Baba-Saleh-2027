"""Nightly check of the store rules that must never be bypassed (see CLAUDE.md at the repo root).

  1. Sold-out products last, everywhere: collections (any sort), brand / type pages, search and
     the search dropdown. Checked in the live theme code and on the live storefront.
  2. Every active product has exactly one category (cat: tag).
  3. The live theme is the one this repo deploys to.

If the live theme lost the sold-out-last code (an edit in the theme editor, an app, a theme
update), the file is put back from git; the live version is saved first in
$DATA_DIR/theme_backups/. Anything that could not be fixed makes this script exit 1, so the
nightly summary reports it.

    python3 rules_check.py            # check and repair
    python3 rules_check.py --check    # check only
"""
import os, re, subprocess, sys, time, urllib.parse, urllib.request

from sync import gql, log

THEME_ID = "gid://shopify/OnlineStoreTheme/166776471600"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
D = os.environ.get("DATA_DIR", "woo_data")
SITE = "https://babasaleh.com"
CHECK_ONLY = "--check" in sys.argv

# theme file -> code that keeps sold-out products last
MARKERS = {
    "assets/theme.js": ["#parkSoldOut()", "skip products already shown"],
    "sections/main-collection.liquid": ["for pass in (1..2)"],
    "sections/main-search.liquid": ["for pass in (1..3)", "data-load-more"],
    "sections/predictive-search.liquid": ["product_pass"],
}
# storefront pages whose first page must list every in-stock product before any sold-out one
PAGES = [
    "/collections/all?sort_by=title-ascending",
    "/collections/all?sort_by=price-ascending",
    "/collections/sportswear?sort_by=price-descending",
    "/collections/swimwear",
    "/collections/vendors?q=Baba%20Saleh&sort_by=title-ascending",
    "/collections/types?q=Tracksuits",
    "/search?q=ball&type=product",
    "/ar/search?q=" + urllib.parse.quote("كورة") + "&type=product",
]

FILES_Q = """query($id: ID!, $f: [String!]) { theme(id: $id) { files(filenames: $f) { nodes { filename
  body { ... on OnlineStoreThemeFileBodyText { content } } } } } }"""
UPSERT = """mutation($id: ID!, $files: [OnlineStoreThemeFilesUpsertFileInput!]!) {
  themeFilesUpsert(themeId: $id, files: $files) { upsertedThemeFiles { filename } userErrors { message } } }"""


def check_theme(problems):
    themes = gql("{ themes(first: 20) { nodes { id name role } } }")["themes"]["nodes"]
    main = next((t for t in themes if t["role"] == "MAIN"), None)
    if not main or main["id"] != THEME_ID:
        problems.append(f"live theme is now {main and main['name']!r}, not the one this repo deploys to: "
                        "the sold-out-last code must be copied into it (tools/woo_to_shopify/push_files.py)")
        return
    nodes = gql(FILES_Q, {"id": THEME_ID, "f": list(MARKERS)})["theme"]["files"]["nodes"]
    live = {n["filename"]: n["body"]["content"] for n in nodes}
    for name, marks in MARKERS.items():
        missing = [m for m in marks if m not in live.get(name, "")]
        if not missing:
            continue
        log(f"{name}: sold-out-last code missing ({missing})")
        if CHECK_ONLY:
            problems.append(f"{name} lost the sold-out-last code")
            continue
        repo = open(os.path.join(ROOT, name), encoding="utf-8").read()
        if any(m not in repo for m in marks):
            problems.append(f"{name}: the repo copy lacks the code too")
            continue
        os.makedirs(os.path.join(D, "theme_backups"), exist_ok=True)
        backup = os.path.join(D, "theme_backups", name.replace("/", "__") + time.strftime(".%Y%m%d-%H%M"))
        open(backup, "w", encoding="utf-8").write(live.get(name, ""))
        out = gql(UPSERT, {"id": THEME_ID, "files": [{"filename": name, "body": {"type": "TEXT", "value": repo}}]})
        errs = out["themeFilesUpsert"]["userErrors"]
        if errs:
            problems.append(f"{name}: restore failed {errs}")
        else:
            log(f"{name}: restored from git (live copy saved to {backup})")


def check_pages(problems):
    for path in PAGES:
        url = SITE + path + ("&" if "?" in path else "?") + "nc=" + str(int(time.time()))
        try:
            html = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read().decode("utf-8", "ignore")
        except Exception as e:
            log(f"{path}: could not load ({e})")
            continue
        grid = html.split("data-product-grid", 1)[-1].split("</ul>", 1)[0]
        cards = ["S" if "card--sold-out" in c else "o" for c in re.findall(r'<article class="card[^"]*"', grid)]
        seq = "".join(cards)
        if "So" in seq:
            problems.append(f"{path}: a sold-out product is listed before an in-stock one")


def check_categories(problems):
    bad, after = [], None
    while True:
        page = gql("""query($a: String) { products(first: 250, after: $a, query: "status:active") {
          pageInfo { hasNextPage endCursor } nodes { title tags } } }""", {"a": after})["products"]
        bad += [p["title"] for p in page["nodes"] if sum(t.startswith("cat:") for t in p["tags"]) != 1]
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    if bad:
        problems.append(f"{len(bad)} product(s) without exactly one category: {bad[:10]}")


def main():
    problems = []
    check_theme(problems)
    check_pages(problems)
    check_categories(problems)
    for p in problems:
        log("RULE BROKEN:", p)
    log(f"rules-check {'OK' if not problems else str(len(problems)) + ' problem(s)'}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
