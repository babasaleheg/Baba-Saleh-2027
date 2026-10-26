"""Photo contact sheets for checking categories by eye.

Each sheet shows up to 30 products of one category: photo, title, category, audience (for:)
and extra swimwear sections (x:). Used for the full audit and, nightly, for products added
or changed in the last day, so a person (or the nightly assistant) can spot items in the wrong
category or audience from the photo (e.g. an adult model in Kids' Swimwear).

    python3 photo_sheets.py               # every active product, grouped by category
    python3 photo_sheets.py --days 1      # only products created in the last day
    python3 photo_sheets.py --cat kids-swimwear
    python3 photo_sheets.py --flagged     # only products whose price is far from similar ones
    python3 photo_sheets.py --days 1 --rotate   # nightly: new products + a seventh of all categories
Writes PNGs to $DATA_DIR/sheets/ and prints their paths.
"""
import argparse, io, os, re, statistics, textwrap, urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFont

from sync import gql

D = os.environ.get("DATA_DIR", "woo_data")
OUT = os.path.join(D, "sheets")
CACHE = os.path.join(D, "thumbs")
CHECKED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "price_checked.txt")
STORE = "https://babasaleh.com/cdn/shop/files/"
COLS, ROWS, TW, TH, LH = 6, 5, 200, 200, 64

Q = """query($a: String, $q: String) { products(first: 250, after: $a, query: $q) { pageInfo { hasNextPage endCursor }
  nodes { id title handle tags createdAt updatedAt priceRangeV2 { minVariantPrice { amount } } featuredMedia { preview { image { url } } } } } }"""


def font(size):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def thumb(p):
    url = (((p.get("featuredMedia") or {}).get("preview") or {}).get("image") or {}).get("url")
    if not url:
        return None
    name = url.split("/files/")[-1].split("?")[0]
    path = os.path.join(CACHE, name.replace("/", "_") + ".png")
    if not os.path.exists(path):
        try:
            data = urllib.request.urlopen(f"{STORE}{name}?width={TW * 2}", timeout=30).read()
            img = Image.open(io.BytesIO(data)).convert("RGB")
            img.thumbnail((TW, TH))
            img.save(path)
        except Exception:
            return None
    return Image.open(path)


def kind(title):
    """The product's kind: last word of the name before any size/colour part ("Door Pull-Up Bar 100 cm" -> "bar")."""
    name = re.split(r"\s[–-]\s|,|\(|\d", title.lower().replace("’", "'"))[0]
    words = re.findall(r"[a-z][a-z'-]+", name)
    return words[-1].rstrip("s") if words else ""


def price(p):
    return float(p["priceRangeV2"]["minVariantPrice"]["amount"])


def price_flags(items):
    """Products priced under a quarter or over 4x the median of 3+ same-category products of the same kind."""
    flags = {}
    for p in items:
        k = kind(p["title"])
        peers = [price(o) for o in items if o is not p and k and kind(o["title"]) == k and price(o) > 0]
        if len(peers) >= 3 and price(p) > 0:
            med = statistics.median(peers)
            if price(p) < med / 4 or price(p) > med * 4:
                flags[p["id"]] = med
    return flags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=float)
    ap.add_argument("--cat")
    ap.add_argument("--flagged", action="store_true", help="only price-flagged products, on their own sheets")
    ap.add_argument("--rotate", action="store_true",
                    help="with --days: also every product of a seventh of the categories (a different seventh each day), "
                         "so every product's photo is looked at again once a week")
    args = ap.parse_args()
    q = "status:active"
    products, after = [], None
    while True:
        page = gql(Q, {"a": after, "q": q})["products"]
        products += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(CACHE, exist_ok=True)
    by_cat = defaultdict(list)
    for p in products:
        by_cat[next((t[4:] for t in p["tags"] if t.startswith("cat:")), "NONE")].append(p)
    checked = set(open(CHECKED, encoding="utf-8").read().splitlines()) if os.path.exists(CHECKED) else set()
    flags = {pid: med for items in by_cat.values() for pid, med in price_flags(items).items()}
    flags = {pid: med for pid, med in flags.items() if next(p["title"] for p in products if p["id"] == pid) not in checked}
    since = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y-%m-%dT%H:%M:%SZ") if args.days else ""
    # new products only: the nightly scripts touch every product, so updatedAt says nothing
    groups = {cat: [p for p in items if p["createdAt"] > since or p["id"] in flags]
              for cat, items in by_cat.items() if not args.cat or cat == args.cat}
    if args.rotate:
        cats = sorted(by_cat)
        today = datetime.now(timezone.utc).toordinal() % 7
        for cat in cats[today::7]:
            if not args.cat or cat == args.cat:
                groups[cat] = by_cat[cat]
    if args.flagged:
        groups = {"price-flagged": [p for items in by_cat.values() for p in items if p["id"] in flags]}
    groups = {cat: items for cat, items in groups.items() if items}
    products = [p for items in groups.values() for p in items]
    with ThreadPoolExecutor(12) as ex:
        thumbs = dict(zip([p["id"] for p in products], ex.map(thumb, products)))
    small, tiny = font(13), font(11)
    paths = []
    for cat in sorted(groups):
        items = sorted(groups[cat], key=lambda p: p["title"])
        for start in range(0, len(items), COLS * ROWS):
            chunk = items[start:start + COLS * ROWS]
            rows = (len(chunk) + COLS - 1) // COLS
            sheet = Image.new("RGB", (COLS * TW, 30 + rows * (TH + LH)), "white")
            dr = ImageDraw.Draw(sheet)
            dr.text((8, 6), f"{cat}  ({start + 1}-{start + len(chunk)} of {len(items)})", fill="black", font=font(16))
            for i, p in enumerate(chunk):
                x, y = (i % COLS) * TW, 30 + (i // COLS) * (TH + LH)
                im = thumbs.get(p["id"])
                if im:
                    sheet.paste(im, (x + (TW - im.width) // 2, y + (TH - im.height) // 2))
                else:
                    dr.rectangle([x + 4, y + 4, x + TW - 4, y + TH - 4], outline="red")
                    dr.text((x + 60, y + 90), "NO PHOTO", fill="red", font=small)
                aud = ",".join(t[4:] for t in p["tags"] if t.startswith("for:")) or "-"
                extra = ",".join(t[2:].replace("-swimwear", "") for t in p["tags"] if t.startswith("x:") and "swimwear" in t)
                lines = textwrap.wrap(p["title"], 28)[:2]
                for j, line in enumerate(lines):
                    dr.text((x + 4, y + TH + 2 + j * 15), line, fill="black", font=small)
                dr.text((x + 4, y + TH + 34), f"#{start + i + 1} for:{aud}" + (f" +{extra}" if extra else ""), fill="#b45309", font=tiny)
                flag = flags.get(p["id"])
                dr.text((x + 4, y + TH + 48), f"{price(p):g} EGP" + (f"  PRICE? peers ~{flag:g}" if flag else ""),
                        fill="red" if flag else "#555", font=tiny)
                dr.rectangle([x, y, x + TW - 1, y + TH + LH - 1], outline="#e5e5e5")
            path = os.path.join(OUT, f"{cat}_{start // (COLS * ROWS) + 1}.png")
            sheet.save(path)
            paths.append(path)
    with open(os.path.join(OUT, "price_flags.txt"), "w") as f:
        for cat, items in sorted(by_cat.items()):
            for p in items:
                if p["id"] in flags:
                    f.write(f"{p['title']} | {cat} | {price(p):g} EGP | similar ~{flags[p['id']]:g} EGP | /products/{p['handle']}\n")
    print("\n".join(paths))
    print(f"price flags: {len(flags)} (see {OUT}/price_flags.txt)")
    print(f"{len(paths)} sheets, {sum(len(v) for v in groups.values())} products")


if __name__ == "__main__":
    main()
