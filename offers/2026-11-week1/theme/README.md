Live-theme copies (theme "Baba Saleh 2027 – November offers", 167216709680) of files changed for the
November offers. The full set is on branch claude/great-gauss-bqy749.

- sections/november-offers.liquid: ticker shows one language per page, each phrase kept together.
- snippets/nov-offer-product.liquid + sections/main-product.liquid: before the week starts, product
  pages of offer products show the coming offer price (PDF old price crossed out, % and EGP saved),
  like the offer cards. From the start the real prices/compare-at take over. Update nov_start weekly.
  It renders snippets/nov-offer-prices.liquid, which only exists in the November theme, so the repo's
  own sections/main-product.liquid doesn't include this render.
