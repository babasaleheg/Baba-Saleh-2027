"""Photo contact sheets for checking categories by eye.

Each sheet shows up to 30 products of one category: photo, title, category, audience (for:)
and extra swimwear sections (x:). Used for the full audit and, nightly, for products added
or changed in the last day, so a person (or the nightly assistant) can spot items in the wrong
category or audience from the photo (e.g. an adult model in Kids' Swimwear).

    python3 photo_sheets.py               # every active product, grouped by category
    python3 photo_sheets.py --days 1      # only products created/updated in the last day
    python3 photo_sheets.py --cat kids-swimwear
Writes PNGs to $DATA_DIR/sheets/ and prints their paths.
"""
import argparse, io, os, textwrap, urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFont

from sync import gql

D = os.environ.get("DATA_DIR", "woo_data")
OUT = os.path.join(D, "sheets")
CACHE = os.path.join(D, "thumbs")
STORE = "https://babasaleh.com/cdn/shop/files/"
COLS, ROWS, TW, TH, LH = 6, 5, 200, 200, 64

Q = """query($a: String, $q: String) { products(first: 250, after: $a, query: $q) { pageInfo { hasNextPage endCursor }
  nodes { id title tags featuredMedia { preview { image { url } } } } } }"""


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=float)
    ap.add_argument("--cat")
    args = ap.parse_args()
    q = "status:active"
    if args.days:
        since = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        q += f" AND (created_at:>'{since}' OR updated_at:>'{since}')"
    products, after = [], None
    while True:
        page = gql(Q, {"a": after, "q": q})["products"]
        products += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(CACHE, exist_ok=True)
    groups = defaultdict(list)
    for p in products:
        cat = next((t[4:] for t in p["tags"] if t.startswith("cat:")), "NONE")
        if not args.cat or cat == args.cat:
            groups[cat].append(p)
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
                dr.rectangle([x, y, x + TW - 1, y + TH + LH - 1], outline="#e5e5e5")
            path = os.path.join(OUT, f"{cat}_{start // (COLS * ROWS) + 1}.png")
            sheet.save(path)
            paths.append(path)
    print("\n".join(paths))
    print(f"{len(paths)} sheets, {sum(len(v) for v in groups.values())} products")


if __name__ == "__main__":
    main()
