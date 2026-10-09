# Baba Saleh 2027 — Shopify theme

A modern, bilingual (English / العربية) Online Store 2.0 theme for **Baba Saleh Sports Egypt**.

- Full RTL support: layout is written with CSS logical properties, so every section mirrors automatically when the store language is Arabic.
- Paired Latin + Arabic typefaces (Archivo + Alexandria by default; switchable in **Theme settings → Typography**).
- No JavaScript dependencies — native web components only (`assets/theme.js`).
- Passes Shopify Theme Check (only warnings are the intentional Google Fonts links, since Shopify's font library has no strong Arabic faces).

## What's included

| Area | Highlights |
| --- | --- |
| Header | Sticky glass header (hides on scroll down), 3-level mega menu with optional promo image, predictive search, one-tap **EN ⇄ ع** language switch, mobile drawer menu |
| Home | Hero slideshow (desktop/mobile images, progress dots), perks bar, shop-by-sport circles, tabbed product carousels, promo tiles, scrolling marquee, bento category grid, brand logos, image with text, newsletter |
| Product | Large-first-image gallery (swipe on mobile), colour swatches + size pills, low-stock pulse, delivery/COD/returns perks, accordions, WhatsApp/Facebook/X share, sticky add-to-cart bar, related products |
| Collection / search | Filter & sort drawer (Shopify Search & Discovery filters), active filter chips, AJAX filtering, "Load more" pagination |
| Cart | Slide-out cart drawer + cart page, free-delivery progress bar, order note |
| Global | Floating WhatsApp button, colour schemes, corner radius, pill/rounded buttons, scroll-reveal animations (respects reduced motion) |

## Setup in Shopify admin

1. **Connect the theme** — Online Store → Themes → Add theme → *Connect from GitHub* → pick this repo and branch. (Or zip the theme folders and upload.)
2. **Add Arabic** — Settings → Languages → Add language → Arabic → Publish.
3. **Translate your content** — install **Translate & Adapt** (free, by Shopify) to translate products, collections, menus and section text (hero headings, tiles, etc.). Theme UI strings (buttons, cart, filters…) are already translated in `locales/ar.json`.
4. **Menus** — Content → Menus → *Main menu*. Nest links two levels deep (e.g. *Sports → Football → Balls*) to get the mega menu.
5. **Filters** — install **Search & Discovery** and add filters (price, size, colour, product type, brand).
6. **Theme settings** — set your logo, WhatsApp number (e.g. `201001234567`), social links, free-delivery threshold and colours.
7. **Hero images** — the homepage is pre-filled with your real collections; add campaign images to the hero slides and promo tiles.

## Structure

```
layout/      theme.liquid (sets lang + dir), password.liquid
sections/    header, footer, homepage sections, main-* page sections
snippets/    product-card, price, icon, facets, cart-items, language-switcher…
templates/   JSON templates for every page type
locales/     en.default.json, ar.json, en.default.schema.json
assets/      base.css, theme.js
config/      settings_schema.json, settings_data.json
```

## Development

```bash
npm i -g @shopify/cli
shopify theme dev --store babasaleh.myshopify.com   # live preview
shopify theme check                                 # lint
```
