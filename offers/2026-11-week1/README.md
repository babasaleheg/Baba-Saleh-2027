# عروض نوفمبر – Nov 1–7 2026

Source: owner's PDF "عروض الاسبوع الاول من نوفمبر" (110 rows, `pdf-rows.json`).

- Collection `november-offers` (عروض نوفمبر, 73 products, template `collection.november-offers`).
- Draft theme "Baba Saleh 2027 – November offers" (167216709680): hero section `november-offers`,
  menu link snippet `nov-offers-link` (desktop pill + mobile drawer card), header edits. Copies in `theme/`.
  Link shows all November (Nov 1–30 Cairo); `?nov=preview` shows it early. Page sorted price low to high, infinite scroll.
  Week 1 discounts: Nov 1–7. Week 2 data comes from the owner later.
- Prices: `rules.json` ([PDF old, PDF sale]). Apply at 2026-10-31T22:00Z: price = sale, compareAt = PDF old price.
- Page cards show the PDF old price crossed out, sale price, % ribbon and "You save" from `snippets/nov-offer-prices.liquid` (made from rules.json as `nov-data.json`); "up to" % is the highest in that file (25%, ASIS). For week 2 replace that snippet and the hero dates/start/end.
  Revert at 2026-11-07T22:00Z from `originals.json` (saved at apply time).
- Not on the store: carbon stretch shorts 2339021x, carbon swimsuit 2359010x/2359011x/2359012x, socks 403401/403402/402405/402406.
  Draft products skipped: 331122 (Front Swimming Snorkel), 331509 (Mondial 337).
- Home page: section `nov-home-banner` in the header group (renders on the home page only, until the week ends):
  mega countdown, "up to" %, button to the page, 16 biggest discounts (`snippets/nov-offer-top.liquid`).
- Card dressing shared in `snippets/nov-offer-cards.liquid`. Before Nov 1 the cards on the page and banner have no
  add-to-cart button and say "Offer starts Nov 1".
