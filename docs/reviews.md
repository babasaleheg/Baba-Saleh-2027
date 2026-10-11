# Product reviews (no app)

Customers rate a product 1–5 stars and leave a short comment. Nothing appears until you approve it,
and products with no approved review show no stars at all (no "0 reviews", no empty stars, no empty
rating in Google's structured data).

## How it works

```
Customer ──"Write a review" (Shopify contact form + hCaptcha)──▶ email to the store
You      ──approve in admin, or `sync.py reviews-add`──────────▶ product_review metaobject (status: approved)
sync.py reviews-sync (by hand or nightly) ─────────────────────▶ product metafields ──▶ theme + JSON-LD
```

- **Submitting**: the form under the product (`sections/product-reviews.liquid`) is Shopify's native
  contact form, so Shopify adds hCaptcha and its own spam filtering. The theme adds two checks of its own: a hidden
  honeypot field (`contact[website]`) and a minimum of 3 seconds between page load and submit. The
  email you receive includes `type: review`, the product title, handle, ID and URL, the rating, the comment,
  the name, the email and the language.
- **Storing**: each review is a `product_review` metaobject (admin → **Content → Metaobjects → Product reviews**).
- **Showing**: `reviews-sync` writes three metafields on each product. The theme reads only these, so it adds no network requests:
  the reviews section (average, count, 5→1 star bars, list with "Show more"), stars + count under
  the product title and on product cards, and `AggregateRating` + `Review` in the Product JSON-LD.

## Data model

**Metaobject `product_review`** (storefront access: public read; publishable: Active = approved)

| Field | Type | Notes |
| --- | --- | --- |
| `product` | product reference | required |
| `rating` | rating, scale 1–5 | required |
| `title` | single line text | optional, max 120 |
| `body` | multi-line text | max 500 |
| `author_name` | single line text | shown as written; empty → "Customer" |
| `verified_buyer` | true/false | shows the "Verified buyer" badge |
| `submitted_at` | date and time | shown as the review date |
| `status` | single line text, choices `pending` / `approved` / `rejected` | only `approved` is shown |

**Product metafields** (written by `reviews-sync`; don't edit them by hand)

| Metafield | Type | Value |
| --- | --- | --- |
| `reviews.rating` | rating (1–5) | average of approved reviews, 1 decimal |
| `reviews.rating_count` | integer | number of approved reviews |
| `babasaleh.reviews` | list of `product_review` references | approved, newest first, at most 100 |

`reviews.rating` / `reviews.rating_count` are Shopify's standard review metafields, which Shopify
and Google Shopping understand. If a product has none of the three metafields, it shows no rating.

## Moderating a review (about 1 minute)

1. Open the review email. Spam? Delete it. Done.
2. Admin → **Content → Metaobjects → Product reviews → Add entry**: choose the product and fill in the
   rating, comment (`body`) and name, plus `submitted_at` (the email date). Tick `verified_buyer` if they ordered
   the product. Set **status = approved** and save.
   *Or*, from a terminal:
   ```bash
   python3 tools/woo_to_shopify/sync.py reviews-add HANDLE 5 "Ahmed M." "Great ball, true to size" --verified
   ```
   (`--title "…"` and `--date 2026-10-11` are optional. This also syncs that product immediately.)
3. Run `python3 tools/woo_to_shopify/sync.py reviews-sync`, or wait for the nightly run. The stars appear.

To hide a review later, set its status to `rejected` (or `pending`) and run `reviews-sync` again. The
product's average, count and list are recalculated. If it was the last approved review, the product's metafields are removed
and the stars disappear.

## Commands

All commands are in `tools/woo_to_shopify/sync.py` and are safe to re-run.

| Command | What it does |
| --- | --- |
| `reviews-setup` | One-off: creates the `product_review` metaobject definition and the three product metafield definitions (pinned, storefront-readable). It skips any that already exist. |
| `reviews-sync` | Reads every review. Approved reviews are set to Active and all others to Draft. It writes `reviews.rating`, `reviews.rating_count` and `babasaleh.reviews` only on products whose values changed, and clears them on products with no approved review left. |
| `reviews-add HANDLE RATING NAME COMMENT [--title T] [--verified] [--date YYYY-MM-DD]` | Creates an approved review and syncs that product. |

Nightly run (cron example, 03:17 Cairo time):

```
17 3 * * * cd /path/to/repo/tools/woo_to_shopify && SHOPIFY_CLIENT_ID=… SHOPIFY_CLIENT_SECRET=… python3 sync.py reviews-sync
```

## Access scopes

The Dev Dashboard app used by `sync.py` needs these scopes, in addition to the ones it already has:

- `write_metaobject_definitions`: `reviews-setup`
- `write_metaobjects`: `reviews-sync`, `reviews-add`
- `write_products`: already granted; needed to write the product metafields

After adding the scopes, release a new app version and reinstall/approve it on the store.

## Theme pieces

| File | Role |
| --- | --- |
| `sections/product-reviews.liquid` | Reviews section + "Write a review" form (added to `templates/product.json` after the product) |
| `snippets/rating-stars.liquid` | Inline SVG stars with partial fill and a spoken label ("Rated 4.5 out of 5, 12 reviews") |
| `sections/main-product.liquid`, `snippets/product-card.liquid` | Compact stars + count, only when `reviews.rating_count > 0` |
| `snippets/structured-data.liquid` | `aggregateRating` + up to 10 `review` entries, only when there are approved reviews |
| `assets/theme.js` | `<product-reviews>` ("Show more") and `<review-form>` (honeypot + 3-second check, shows the result after the post) |
| `locales/*.json` | `reviews.*` strings (English + Arabic) and `date_formats.review_date` |
