# عروض نوفمبر – week 2 (Thu Nov 5 – Fri Nov 13 2026)

Source: owner's PDF "عروض الجمعة الاسبوع الثاني" (`pdf-rows.json`: after, before, name, code).
Owner: start today (Nov 5), run until next Friday (Nov 13). Week-1 offers continue to Nov 13 too,
except the Track 3D robe (ends Nov 7).

- Applied Nov 5: price = PDF after, compareAt = PDF before (`plan.json`), 524 variants / 51 products.
  Codes matched to variant SKUs (`a#b` SKUs split; a variant on two codes takes the code whose PDF
  "before" equals its price). 31 codes are not on the website (not listed in Shopify). Skipped 237411
  (PDF would raise its price above the website's 990). One-Piece Kids' Swimsuit was 375 on the site, PDF
  says 295 before / 250 after: 250 with 295 crossed out, as the PDF.
- Originals saved in `originals.json` (taken just before applying).
- Theme 167216709680 (copies in `theme/`): week-2 handles added to `snippets/nov-offer-prices.liquid`;
  offers page hero and home banner end 1794607200 (Nov 14 00:00 Cairo), dates "Until Friday, Nov 13".
- Products added to the `november-offers` collection.
- Scheduled: Nov 7 22:00Z robe price restore + robe out of the snippet/collection; Nov 13 22:00Z week-1
  revert (moved from Nov 7); Nov 13 22:05Z Carbon restore; Nov 13 22:10Z week-2 revert from `originals.json`.
