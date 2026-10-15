# Baba Saleh Sports Egypt – store notes

Shopify store: babasaleh.myshopify.com (Basic plan, EGP, Egypt). Owner: support@babasaleh.com.

## How to work with the owner
- Always reply briefly.
- No emojis anywhere (site, emails, copy).
- Modern, minimal design; brand colors black `#0a0a0a`, gold `#febd19`, white. Logo is black on transparent – in emails use the white-badge version `files/baba-saleh-email-logo.png`.
- Theme changes go into a duplicate theme (the live theme can't be edited via API); the owner publishes it.

## Shipping (source of truth: owner's Shipping settings, Oct 2026)
Checkout uses these rates (the newer Shopify shipping screen; not visible in the Admin API delivery profiles).
Three areas, each with Standard / Heavy / Very Heavy. Heavy covers some categories (Billiards, Games, Gym Equipment & Benches, Camping & Scouting, …); Very Heavy currently has no products.

| Area (as shown in owner's screenshots) | Standard | Heavy | Very Heavy |
|---|---|---|---|
| Area A – Cairo & Giza | EGP 85, free from EGP 2,999 · 3–5 days | EGP 250 · 5–8 days | EGP 600 · 3–5 days |
| Area B | EGP 120 · 3–5 days | EGP 180 · 5–8 days | EGP 1,000 · 8–12 days |
| Area C | EGP 140 · 5–8 days | EGP 290 · 8–12 days | EGP 1,000 · 5–8 days |

- Free delivery: orders EGP 2,999+ in Cairo & Giza only (cart bar note: "Applies to Cairo & Giza").
- Area B / C governorate lists: not confirmed yet – ask the owner.
- The older API delivery profile (zones "Cairo & Giza" 85/free ≥2,999, "Domestic" 118, "International" 990) is not what checkout charges.

## Store setup done
- Size guides: metaobjects `size_guide` (mens-clothing, womens-clothing, kids-clothing, adult-shoes, kids-shoes, standard-size-chart); theme auto-picks by `for:men|women|kids` tag and size values.
- Size option lists: metaobjects Clothing size / Kids size / Shoe size (product metafields `babasaleh.clothing_size|kids_size|shoe_size`).
- Color swatches: theme snippet `color-hex` maps color names (EN/AR, keyword fallback) to hex.
- Reviews: Judge.me (stars gold, form: stars, name, email, comment). Old reviews were metaobjects `customer_review` (imported to Judge.me).
- Product gallery: slider with arrows on desktop.
- Email templates: built in scratchpad (9 templates). Shopify notification emails cannot load live products.

## Open to-dos (Oct 15 2026)
- Draft theme "Baba Saleh 2027 – Header links" (166769459248): header links next to search, events photos (card images + gallery), FAQ padding, join-us role dedupe + email-CV button. Also 13-photo events gallery, smart 404, title fix. Owner publishes.
- Theme uploads: use stagedUploadsCreate (PUT via curl) + themeFilesUpsert body type URL (no need to inline big files).
- 404s: all 1003 redirects tested live (Oct 15): every one returns 301; 23 pointed at draft/renamed products and were re-pointed. Shopify redirects have no wildcards, so the draft theme 404 page handles the rest: strips `/page/N` (old paginated categories), `/shop/...` goes to all products, `/brand/x`, `/tag/x` and dead product links go to search, and pushes GTM event `page_404` (page_404_path). Oct 15: added 236 redirects from the Search Console 404/5xx exports (406 of 416 URLs now 301; the rest are junk like /wp-json, /*). Draft theme also strips /en/, and sends /shop?... (served the home page = soft 404s) to all products with noindex. /en and /sitemap_index.xml redirects added. Bulk mutations are blocked: create redirects with aliased urlRedirectCreate calls (80 per call). Re-test: bulk-export redirects, curl each (scratchpad redir/test.py).
- Fixed double-escaped page titles ("&amp;amp;") in snippets/meta-tags (draft theme).
- Sender email: domain authentication done (Oct 15). DMARC record not set up yet (Settings > Notifications > DMARC record setup) – likely cause of Outlook "Unverified Sender". Email logo now has styled alt text for clients that block images.
- Customers get no email for newsletter signup / contact form / job form: Shopify sends none by default. Newsletter: Shopify Email "Welcome new subscribers" automation. Contact/job: needs a form app with auto-reply.
- Cancel order (done Oct 15): order confirmation email has a "Cancel order / إلغاء الطلب" button next to "View order status" (opens /pages/contact-us?topic=cancel&order=..&email=.., form prefilled, topic "Cancel order") and a WhatsApp button; staff cancel in admin. Contact page change is in the draft theme. Order status page and new customer accounts can't be edited from the theme (would need an app/checkout extension).
