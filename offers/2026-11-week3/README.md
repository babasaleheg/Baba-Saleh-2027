# عروض نوفمبر – week 3 (Sat Nov 14 – Fri Nov 20 2026), website only

Owner (Nov 14): bring back the November offers with a new look for week 3. Week-1 offers continue
except the robes (البرنس); week-2 offers continue except the bags (الشنط); plus the week-3 PDF list
(`pdf-rows.json`, 76 codes, mostly kids' toys: 63 matched to website variants, 13 not on the website).
Website only (owner's choice): branch prices are not changed.

- Applied Nov 14 ~13:40 Cairo: `plan.json` (913 variants, 189 products). price = offer price,
  compareAt = the old price. Originals (the prices just before) in `originals.json`.
  Before that, the staff portal's nightly price check (05:56 Cairo) had already put the portal's prices
  back, which are the week-1/2 offer prices for 673 variants, without a struck-through price.
- Staff portal: PR babasaleheg/babasaleh-staff-portal#150 (migration 0060 `website_price_holds`). The
  913 variants are held until 2026-11-20, so the portal's daily price check leaves them alone.
- Skipped: 9 goggle variants whose website price matches neither the offer price nor the old price,
  and the hand exercise ball (no discount).
- Collection `november-offers`: 71 products added, 12 removed (11 bags, hand ball) → 189.
- Theme 167216709680 (copies in `theme/`): new hero section `nov-week3` (ink and yellow, week badge,
  countdown to the end) on `collection.november-offers`; `nov-offer-prices` / `nov-offer-top`
  regenerated; home banner Nov 14 – 20 titled "عروض نوفمبر · الأسبوع التالت".
  The old `november-offers` section is left in the theme.
- End: page and banner switch off by themselves at 1795212000 (Nov 21 00:00 Cairo). A scheduled task at
  2026-11-20T22:00Z restores `originals.json` with compareAt cleared.
