# White Friday – عروض الجمعة البيضاء (Sat Nov 21 – Mon Nov 30 2026), website only

Owner (Nov 21): extend all current November offers to the end of November as "White Friday", with a
big facelift (popping shapes, circles, icons, vectors, motion).

- Prices: the same 920 variants as week 3 (`../2026-11-week3/plan.json`) re-applied Nov 21, 0 errors.
  Staff-portal holds (`website_price_holds`) extended to 2026-11-30. Highest real discount: 29%.
- Theme 167216709680 (copies in `theme/`):
  - `snippets/wf-shapes.liquid`: decorative layer (sun circle, dashed ring, yellow ring, dots, zigzag,
    sparkles, price tag and bag icons, -29% burst). Brand colours only; no motion with reduced-motion.
  - `sections/white-friday.liquid`: offers-page hero (marquee, outline + highlighted title, countdown
    with exact deadline, CTA, perks, category chips, cards pop in on scroll).
  - `sections/wf-home-banner.liquid`: home banner with countdown and "Biggest discounts" rail.
  - `sections/wf-strip.liquid`: black strip with live countdown on every page (not on the offers page).
  - `snippets/nov-offers-link.liquid`: menu pill "White Friday" / "الجمعة البيضاء".
  - `templates/collection.november-offers.json`, `sections/header-group.json` (old nov-home and 11.11
    strip removed from the header group; their section files stay in the theme).
- Collection `november-offers` renamed "White Friday" (AR "عروض الجمعة البيضاء") with new SEO.
- End: everything hides itself at 1796076000 (Dec 1 00:00 Cairo). Scheduled task
  "White Friday end: restore prices" (2026-11-30T22:05Z) restores `originals.json` with compareAt cleared.

## Nov 27 change (owner): Mega Sale today only, then November Sale, then normal
- Fri Nov 27 (until 1795816800 = Nov 28 00:00 Cairo): "Mega Sale · White Friday – today only" on the strip,
  home banner, offers-page hero, menu pill, announcement bar and home sale section.
- Nov 28 – 30 (until 1796076000): the yellow November Sale look (`nov-week3` hero, `nov-home-banner`,
  a second `wf-strip` "عروض نوفمبر"), all switched by time in the theme; `switch.py nov` (scheduled
  Nov 27 22:01Z) renames the collection and sets the bar / home section text.
- Dec 1: sections hide themselves; `switch.py end` (scheduled Nov 30 22:07Z) removes the sale line and hides
  the home sale section; "White Friday end: restore prices" restores the prices.
