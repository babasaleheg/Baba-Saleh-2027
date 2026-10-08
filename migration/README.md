# WooCommerce → Shopify migration (babasaleh.com)

Everything public on babasaleh.com (WordPress + WooCommerce on Kinsta), converted for the new
Shopify store. Pulled from the WooCommerce Store API and WordPress REST API on 2026-10-08.

## Status

Already done in the Shopify store (x1hnz9-tu.myshopify.com):

- [x] **66 collections**: one smart collection per WooCommerce category (product tag = category name,
  same handle as the old category slug, same image), plus **Sale** (any product with a compare-at
  price). All published to the Online Store. They fill up automatically as soon as products are imported.
- [x] **6 pages**: About us, Contact us (FAQ), Returns Policy, Terms & Conditions, Privacy Policy,
  Event Production & Custom Printing.
- [x] **44 page/homepage images** copied into Shopify Files (`shopify/media_map.json`), so the pages
  don't depend on the old server.

Your turn:

1. **Import products**: Shopify admin → Products → Import → upload `shopify/products.csv`. Leave
   "Publish new products to all sales channels" on. Shopify emails you when it finishes (703 products
   take a few minutes) and lists any rows it rejected.
2. **Import redirects** when you point babasaleh.com at Shopify: Online Store → Navigation →
   URL redirects → Import → `shopify/redirects.csv`.
3. **Customers / orders**: send the WooCommerce exports and they get converted the same way.

## What's here

| File | What it is | How it gets into Shopify |
| --- | --- | --- |
| `shopify/products.csv` | 703 products, 2,685 variants (sizes/colours), prices, sale prices, SKUs, stock, 3,830 images, vendor (brand), type and category tags | Admin → **Products → Import** |
| `shopify/collections.json` | The 65 WooCommerce categories | Created as smart collections (product tag = category name) |
| `shopify/pages/*.html`, `shopify/pages.json` | About, Contact/FAQ, Returns, Terms, Privacy, Event Production | Created as Shopify pages |
| `shopify/redirects.csv` | 782 old URLs → new URLs (`/product/x/` → `/products/x`, `/product-category/…/x/` → `/collections/x`) | Admin → **Online Store → Navigation → URL redirects → Import** (do this when the domain moves) |
| `shopify/homepage.json` | Homepage layout: slideshow, featured categories, product tabs, banners, brand logos | Used to build the Shopify theme homepage |
| `shopify/report.md` | Every judgement call made during conversion | Review |
| `raw/` | Untouched API dumps, so the conversion can be re-run | — |
| `scripts/` | The scripts that produced all of the above | — |

Re-run end to end:

```sh
python3 -I scripts/fetch_variations.py raw        # resumable
python3 -I scripts/build_shopify_csv.py raw shopify
python3 -I scripts/build_pages.py raw shopify
```

## Conversion rules

- **Prices** are EGP, same as the store currency. A WooCommerce sale price becomes the Shopify price and
  the regular price becomes the compare-at price.
- **Stock** comes from WooCommerce's public "N in stock" figure. Products whose stock WooCommerce does not
  track (185 variants, listed in the report) are imported untracked, so they stay sellable as before.
- **Options**: an attribute with a single value on a product (for example Gender: Women) becomes a tag
  instead of an option. Shopify allows 3 options per product; no product needed more after this.
  WooCommerce "any size" variations are expanded into one variant per size.
- **Images** point at the Jetpack CDN copy (`i0.wp.com`), because the origin site is behind a Cloudflare
  challenge that would block Shopify's image download. Shopify copies them at import, so they survive the
  old site going offline.
- **Vendor** is the WooCommerce brand; products on the placeholder brand "Brands" or none get "Baba Saleh".
- **Handles** keep the WooCommerce slugs so the redirects line up and SEO is kept.

## Not covered by the public API (needs a WooCommerce admin export)

- **Customers** and **orders**: WooCommerce → Users / Orders export, or a migration app such as
  Shopify's *Store Migration* app or Matrixify.
- **Product weights** (for shipping rates): not public, imported as 0 g.
- **Hidden, draft or private products**: only published products were visible.
- **Job application forms** (Maadi and October branch hiring pages) were WPForms; recreate them with a
  Shopify form app.
