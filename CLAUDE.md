# Baba Saleh Sports Egypt – store notes

Shopify store: babasaleh.myshopify.com (Basic plan, EGP, Egypt). Owner: support@babasaleh.com.

## How to work with the owner
- Always reply briefly.
- Never tell the owner to edit theme code or settings themselves (Oct 28). Don't make extra theme copies unless asked. The connector blocks live-theme edits and theme publishing; say so once, briefly.
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
- Accessory sizes: custom metaobject `accessory_size` + product metafield `babasaleh.accessory_size` (name "Size (accessories)", no category limit). Shopify's own "Accessory size" (shopify.accessory-size) only works for category Clothing Accessories (aa-1-18) and errors with "Owner subtype does not match" elsewhere. Oct 15: Venum headgear moved to the custom list; owner deleted Shopify's Accessory size definition.
- Color swatches: theme snippet `color-hex` maps color names (EN/AR, keyword fallback) to hex.
- Reviews: Judge.me (stars gold, form: stars, name, email, comment). Old reviews were metaobjects `customer_review` (imported to Judge.me).
- Product gallery: slider with arrows on desktop.
- Email templates: built in scratchpad (9 templates). Shopify notification emails cannot load live products.
- Oct 16: Arabic-locale customers got Shopify's default Arabic email (the 'ar' translation of each EmailTemplate overrides the custom one). Registered full Arabic RTL versions via translationsRegister (resource type EMAIL_TEMPLATE) for the 7 pasted templates: order confirmation, shipping, out for delivery, canceled, refund, delivered, welcome (welcome = same bilingual body). Not pasted yet: abandoned checkout, staff new order. If the owner edits an English template later, the Arabic one must be re-registered (new digest).

## Open to-dos (Oct 15 2026)
- Oct 28: عروض نوفمبر (Nov 1–7). Collection `november-offers` (73 products, yellow hero + countdown) and theme "Baba Saleh 2027 – November offers" (167216709680, PUBLISHED by owner Oct 28; does NOT include the Order source snippet; live theme can't be edited via the connector – pending change: menu link from now instead of Nov 1, file offers/2026-11-week1/theme/snippets/nov-offers-link.liquid.pending): yellow menu link on desktop + mobile drawer, shown all November (Nov 1–30 Cairo; `?nov=preview` to see early). Page stays up all November; discounts run per week (week 1 = Nov 1–7, owner sends week 2 data later; update the hero's start/end/dates/offer settings and collection products each week). Collection sorted price low to high (sold-out last, theme rule); infinite scroll is the theme's auto load-more. Owner: do not change anything else in the theme. Owner publishes. Prices: scheduled tasks apply sale prices 2026-10-31T22:00Z and revert 2026-11-07T22:00Z (details in offers/2026-11-week1/). Compare-at = the PDF's old price (owner, Oct 28). Cards show PDF before/after, % ribbon and EGP saved; "up to" % is computed from the week's prices.
- Oct 16: draft theme "Baba Saleh 2027 – Order source" (166808813616, copy of live Speed 2): snippet `order-source` (rendered from tracking.liquid body) saves cart attributes Order source / First source / Campaign / Landing page from utm_*, gclid/fbclid/ttclid or referrer (else Direct). Shows on each web order under Additional details. Tested on preview. Owner publishes.
- Oct 15: "Speed" theme published (live). New draft "Baba Saleh 2027 – Speed 2" (166776471600): smaller card images (widths 200–900, mobile sizes 36vw; WebP from Shopify at 640w was ~93KB), collection banner image sized to its 160px box, hero collage only the main image high priority, GTM loads after page load. Test: collection LCP after server 2.5s -> 1.5s (slow-phone emulation). Owner publishes.
- Oct 15: "Header links" theme was published (now live). New draft "Baba Saleh 2027 – Speed" (166775652400): hero text shows without waiting for JS (LCP), only first hero slide images eager, first 4 product cards skip reveal animation + first 2 fetchpriority high, card hover photos skipped on phones and loaded after page load on desktop. Owner publishes.
- Draft theme "Baba Saleh 2027 – Header links" (166769459248): header links next to search, events photos (card images + gallery), FAQ padding, join-us role dedupe + email-CV button. Also 13-photo events gallery, smart 404, title fix. Owner publishes.
- Theme uploads: use stagedUploadsCreate (PUT via curl) + themeFilesUpsert body type URL (no need to inline big files).
- 404s: all 1003 redirects tested live (Oct 15): every one returns 301; 23 pointed at draft/renamed products and were re-pointed. Shopify redirects have no wildcards, so the draft theme 404 page handles the rest: strips `/page/N` (old paginated categories), `/shop/...` goes to all products, `/brand/x`, `/tag/x` and dead product links go to search, and pushes GTM event `page_404` (page_404_path). Oct 15: added 236 redirects from the Search Console 404/5xx exports (406 of 416 URLs now 301; the rest are junk like /wp-json, /*). Draft theme also strips /en/, and sends /shop?... (served the home page = soft 404s) to all products with noindex. /en and /sitemap_index.xml redirects added. Bulk mutations are blocked: create redirects with aliased urlRedirectCreate calls (80 per call). Re-test: bulk-export redirects, curl each (scratchpad redir/test.py).
- Fixed double-escaped page titles ("&amp;amp;") in snippets/meta-tags (draft theme).
- Sender email: domain authentication done (Oct 15). DNS at GoDaddy; mailbox on Microsoft 365. DMARC changed from p=quarantine to p=none (Oct 15) because store emails went to Junk. Next: Microsoft 365 Tenant Allow/Block > Spoofed senders: allow babasaleh.com via shopifyemail.com. Email logo now has styled alt text for clients that block images.
- Customers get no email for newsletter signup / contact form / job form: Shopify sends none by default. Newsletter: Shopify Email "Welcome new subscribers" automation. Contact/job: needs a form app with auto-reply.
- Cancel order (done Oct 15): order confirmation email has a "Cancel order / إلغاء الطلب" button next to "View order status" (opens /pages/contact-us?topic=cancel&order=..&email=.., form prefilled, topic "Cancel order") and a WhatsApp button; staff cancel in admin. Contact page change is in the draft theme. Order status page and new customer accounts can't be edited from the theme (would need an app/checkout extension).
