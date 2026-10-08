"""Convert the WooCommerce Store API dump into Shopify import files.

Usage: python3 -I build_shopify_csv.py <raw_dir> <out_dir>

Writes:
  products.csv     Shopify product import (products, variants, prices, stock, images)
  redirects.csv    Shopify URL redirect import (old WooCommerce URLs -> new Shopify URLs)
  collections.json Category tree, used to create one smart collection per category tag
  report.md        Everything that needed a judgement call during conversion
"""
import csv
import glob
import html
import json
import os
import re
import sys
import urllib.parse

RAW, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)

COLUMNS = [
    "Handle", "Title", "Body (HTML)", "Vendor", "Type", "Tags", "Published",
    "Option1 Name", "Option1 Value", "Option2 Name", "Option2 Value",
    "Option3 Name", "Option3 Value",
    "Variant SKU", "Variant Grams", "Variant Inventory Tracker", "Variant Inventory Qty",
    "Variant Inventory Policy", "Variant Fulfillment Service", "Variant Price",
    "Variant Compare At Price", "Variant Requires Shipping", "Variant Taxable",
    "Image Src", "Image Position", "Image Alt Text", "Variant Image",
    "SEO Title", "SEO Description", "Status",
]
# Placeholder brand values used on the WooCommerce site.
NO_BRAND = {"brands", ""}
DEFAULT_VENDOR = "Baba Saleh"
UNLIMITED = 9999  # Store API reports this maximum when stock is not managed

report = {"split_stock": [], "dropped_options": [], "untracked": [], "missing_variation": [],
          "no_image": [], "no_sku": []}


def text(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def image_url(src):
    """Full-size Jetpack CDN URL (the origin is behind a Cloudflare challenge)."""
    u = urllib.parse.urlsplit(html.unescape(src))
    return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, "ssl=1", ""))


def stock(item):
    """(tracked, quantity) from the public Store API fields."""
    m = re.match(r"\s*(\d+)\s+in stock", item["stock_availability"]["text"] or "")
    if m:
        return True, int(m.group(1))
    if not item.get("is_in_stock", True) or "out-of-stock" in item["stock_availability"]["class"]:
        return True, 0
    maximum = item["add_to_cart"]["maximum"]
    if maximum and maximum < UNLIMITED:
        return True, maximum
    return False, None


def price_fields(item):
    p = item["prices"]
    price, regular = p["price"], p["regular_price"]
    compare = regular if regular and price and int(regular) > int(price) else ""
    return price, compare


def vendor(item):
    names = [b["name"] for b in item.get("brands", []) if b["name"].strip().lower() not in NO_BRAND]
    return names[0].title() if names else DEFAULT_VENDOR


products = []
for f in sorted(glob.glob(os.path.join(RAW, "products_p*.json"))):
    products += json.load(open(f, encoding="utf-8"))
variations = {}
for f in glob.glob(os.path.join(RAW, "variations", "*.json")):
    v = json.load(open(f, encoding="utf-8"))
    variations[v["id"]] = v
categories = {c["id"]: c for c in json.load(open(os.path.join(RAW, "products_categories.json")))}

rows = []
redirects = []
for p in products:
    handle = urllib.parse.unquote(p["slug"])
    title = text(p["name"])
    cats = [c["id"] for c in p["categories"]]
    cat_names = [text(categories[c]["name"]) if c in categories else text(c["name"]) for c in cats]
    # Product type = the deepest category (one whose parent is also assigned, else the first).
    deepest = [c for c in cats if c in categories and categories[c]["parent"] in cats] or cats[:1]
    ptype = text(categories[deepest[0]]["name"]) if deepest and deepest[0] in categories else ""
    tags = list(dict.fromkeys(cat_names + [text(t["name"]) for t in p.get("tags", [])]))

    body = p["description"] or p["short_description"]
    seo_desc = text(p["short_description"] or p["description"])[:320]
    images = [image_url(i["src"]) for i in p["images"]]
    if not images:
        report["no_image"].append(title)
    base = {
        "Handle": handle, "Title": title, "Body (HTML)": body, "Vendor": vendor(p), "Type": ptype,
        "Published": "TRUE", "SEO Title": title, "SEO Description": seo_desc, "Status": "active",
    }
    redirects.append((urllib.parse.urlsplit(p["permalink"]).path, f"/products/{handle}"))

    # Build variant list: [(option values dict, source item)]
    variants = []
    option_names = []
    if p["type"] == "variable" and p["variations"]:
        # Map attribute slug values back to display names.
        names = {}
        for a in p["attributes"]:
            names[a["name"]] = {t["slug"]: text(t["name"]) for t in a["terms"]}
        for v in p["variations"]:
            # A None value is WooCommerce's "any <attribute>": expand it to every term.
            combos = [{}]
            for a in v["attributes"]:
                raw = a["value"]
                if raw is None:
                    choices = list(names.get(a["name"], {}).values()) or ["Any"]
                else:
                    choices = [names.get(a["name"], {}).get(raw) or text(urllib.parse.unquote(raw))]
                combos = [dict(c, **{a["name"]: ch}) for c in combos for ch in choices]
            for vals in combos:
                variants.append((vals, variations.get(v["id"]), v["id"]))
        all_names = list(dict.fromkeys(n for vals, _, _ in variants for n in vals))
        # Options with a single value become tags, so the product fits Shopify's 3-option limit.
        option_names = [n for n in all_names if len({vals.get(n) for vals, _, _ in variants}) > 1]
        for n in all_names:
            if n not in option_names:
                tags.append(variants[0][0].get(n, ""))
        if len(option_names) > 3:
            report["dropped_options"].append(f"{title}: kept {option_names[:3]}, merged {option_names[3:]}")
            keep, extra = option_names[:2], option_names[2:]
            merged = " / ".join(extra)
            for vals, _, _ in variants:
                vals[merged] = " / ".join(vals.get(n, "") for n in extra)
            option_names = keep + [merged]
        # Drop duplicate option combinations created by "any value" variations.
        seen, uniq = set(), []
        for item in variants:
            key = tuple(item[0].get(n) for n in option_names)
            if key not in seen:
                seen.add(key)
                uniq.append(item)
        variants = uniq
        if not option_names:  # every attribute had one value: treat as a single-variant product
            variants = variants[:1]
    if not variants:
        variants = [({}, p, p["id"])]

    parent_tracked, parent_qty = stock(p)
    split_stock = False
    base["Tags"] = ", ".join(t for t in dict.fromkeys(tags) if t)
    for i, (vals, item, vid) in enumerate(variants):
        if item is None:
            report["missing_variation"].append(f"{title} (variation {vid})")
            item = p
        tracked, qty = stock(item)
        if not tracked and parent_tracked and item is not p:
            # WooCommerce tracks stock on the parent product; Shopify only per variant.
            tracked, qty, split_stock = True, parent_qty, True
        price, compare = price_fields(item)
        if not price:
            price, compare = price_fields(p)
        sku = item.get("sku") or p.get("sku") or ""
        if not sku:
            report["no_sku"].append(title)
        var_img = image_url(item["images"][0]["src"]) if item is not p and item.get("images") else ""
        row = dict(base) if i == 0 else {"Handle": handle}
        if option_names:
            for n, name in enumerate(option_names[:3], 1):
                if i == 0:
                    row[f"Option{n} Name"] = name
                row[f"Option{n} Value"] = vals.get(name, "")
        else:
            row["Option1 Name"], row["Option1 Value"] = "Title", "Default Title"
        row.update({
            "Variant SKU": sku, "Variant Grams": "0",
            "Variant Inventory Tracker": "shopify" if tracked else "",
            "Variant Inventory Qty": str(qty) if tracked else "",
            "Variant Inventory Policy": "deny" if tracked else "continue",
            "Variant Fulfillment Service": "manual", "Variant Price": price,
            "Variant Compare At Price": compare, "Variant Requires Shipping": "TRUE",
            "Variant Taxable": "TRUE", "Variant Image": var_img,
        })
        if not tracked:
            report["untracked"].append(f"{title}" + (f" — {' / '.join(vals.values())}" if vals else ""))
        rows.append(row)
    if split_stock:
        report["split_stock"].append(f"{title}: {parent_qty} (product total) put on each of {len(variants)} variants")

    # Product images: the first one sits on the first variant row; the rest get their own rows.
    all_imgs = list(dict.fromkeys(images + [r["Variant Image"] for r in rows if r["Handle"] == handle and r.get("Variant Image")]))
    first = next(r for r in rows if r["Handle"] == handle)
    for pos, src in enumerate(all_imgs, 1):
        target = first if pos == 1 else {"Handle": handle}
        target.update({"Image Src": src, "Image Position": str(pos), "Image Alt Text": title})
        if pos > 1:
            rows.append(target)

with open(os.path.join(OUT, "products.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, COLUMNS, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)

# Category pages -> collections.
coll = []
for c in categories.values():
    slug = urllib.parse.unquote(c["slug"])
    coll.append({"id": c["id"], "title": text(c["name"]), "handle": slug, "tag": text(c["name"]),
                 "parent": c["parent"], "count": c["count"], "description": c.get("description", ""),
                 "image": image_url(c["image"]["src"]) if c.get("image") else None})
    path = urllib.parse.urlsplit(c.get("permalink") or c.get("link") or "").path
    if path:
        redirects.append((path, f"/collections/{slug}"))
json.dump(coll, open(os.path.join(OUT, "collections.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

for page in ("about-baba-saleh", "contact-us", "returns-policy", "terms-conditions",
             "privacy-policy", "event-production"):
    redirects.append((f"/{page}/", f"/pages/{page}"))
redirects += [("/refund_returns/", "/pages/returns-policy"),
              ("/maadi-branch-hiring/", "/pages/contact-us"), ("/october-branch-hiring/", "/pages/contact-us"),
              ("/categories/", "/collections"),
              ("/shop/", "/collections/all"), ("/product-category/", "/collections"),
              ("/my-account/", "/account"), ("/wishlist/", "/collections/all")]
with open(os.path.join(OUT, "redirects.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["Redirect from", "Redirect to"])
    w.writerows(dict(redirects).items())

n_var = sum(1 for r in rows if r.get("Variant Price"))
with open(os.path.join(OUT, "report.md"), "w", encoding="utf-8") as f:
    f.write(f"# Conversion report\n\n{len(products)} products, {n_var} variants, "
            f"{sum(1 for r in rows if r.get('Image Src'))} images, {len(dict(redirects))} redirects.\n")
    titles = {
        "split_stock": "Stock tracked on the whole product in WooCommerce (same count copied to every variant — please correct)",
        "untracked": "Stock not tracked in WooCommerce (imported as untracked, always sellable)",
        "dropped_options": "More than 3 options (extra options merged into the third)",
        "missing_variation": "Variation could not be downloaded (used parent price/stock)",
        "no_image": "No images", "no_sku": "No SKU",
    }
    for k, t in titles.items():
        f.write(f"\n## {t} — {len(report[k])}\n\n")
        f.writelines(f"- {x}\n" for x in report[k])
print(open(os.path.join(OUT, "report.md")).read()[:1500])
