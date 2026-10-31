# Baba Saleh Sports – store rules

Shopify store babasaleh.com (Egypt, EGP, English + Arabic). Theme code is in this repo; store
tools are in `tools/woo_to_shopify/`. These rules are the owner's decisions. They are fixed:
never bypass or undo them, in any change, app, script or scheduled task.

## Fixed rules
1. **Sold-out products always last**, now and for every future product: in every collection
   (any sort the shopper picks), brand and type pages, search results and the search dropdown,
   homepage sliders and collection cards. Kept by `sync.py sort-stock` (collection order) and
   the theme (`main-collection`, `main-search`, `predictive-search`, the parking code in
   `assets/theme.js`). `rules_check.py` checks and repairs this every night.
2. **One category per product**: exactly one `cat:` tag, with the product type and `dept:` /
   `group:` tags from `taxonomy.json`. Only `categorize.py` sets categories; corrections go
   in its `FIXES` / `AUDIENCE_FIXES`. Never add tags without removing the old category.
3. **Collections hold only their own products** (no swimwear in Sportswear): rules match on
   product types or `cat:` tags, never on broad `dept:` tags. `collection_audit.py` checks.
4. Only the nightly **"Baba Saleh daily store sync"** may change product categories, tags or
   types automatically. Do not add another scheduled task or app that edits them.
5. **Arabic pages never show English text**: every product, collection and page has Arabic
   title, description and SEO. The nightly writes Arabic for anything new or edited
   (`ar_descriptions.py`, `seo_bilingual.py`).
6. **Only real numbers**: no fake counters or invented social proof ("23 people watching").
   The sales badge uses real orders from the last 30 days (`sold_counter.py`).
7. Brand yellow `#FEBD19` (never blue), Century Gothic-style font; product grids 6 columns on
   desktop, 2 on mobile; Track = تراك in Arabic; returns window 7 days; don't duplicate themes.
8. **Website stock changes only when the owner uploads an October Branch sheet (portal), or
   when the owner edits it in Shopify.** No sheet, no change. Nothing else may set or change
   inventory: no script, app, scheduled task, till sale or the staff portal's daily sync may
   overwrite a quantity the owner set (e.g. 0 = sold out), or split one item code's stock across
   colours/sizes. Tools here only read stock (`stock_from.py`). Portal: migration 0018, `lib/sync.ts`.
9. **No product is ever live at EGP 0.** A product with any variant priced 0 is set to Draft
   (nightly `zero_price.py`); it goes live again only once it has a real price.

## Working on the theme
- Live theme: `gid://shopify/OnlineStoreTheme/166776471600`. Push with
  `python3 tools/woo_to_shopify/push_files.py 166776471600 <files>` after checking the live
  file still matches git (someone may have edited it in the theme editor).
- Push a section's schema before a template that uses a new setting.
