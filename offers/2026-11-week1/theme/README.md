Live-theme copies (theme "Baba Saleh 2027 – November offers", 167216709680) of files changed for the
November offers. The full set is on branch claude/great-gauss-bqy749.

- sections/header.liquid: menu spacing tightened by screen width so every link (incl. تخفيضات) fits.
- sections/nov-home-banner.liquid + november-offers.liquid: from the start (Nov 1 00:00 Cairo) the counter is hidden and the label says "The November Sale is now live" / "عروض نوفمبر بدأت دلوقتي"; an open page switches by itself (cards get add-to-cart). No English title on the Arabic home banner.
- sections/november-offers.liquid: ticker shows one language per page, each phrase kept together.
- snippets/nov-offer-product.liquid + sections/main-product.liquid: before the week starts, product
  pages of offer products show the coming offer price (PDF old price crossed out, % and EGP saved),
  like the offer cards. From the start the real prices/compare-at take over. Update nov_start weekly.
  It renders snippets/nov-offer-prices.liquid, which only exists in the November theme, so the repo's
  own sections/main-product.liquid doesn't include this render.
