# Gratis.Testen — alle Gratis-testen- und Geld-zurück-Aktionen in Deutschland

Collects every running "gratis testen" / Geld-zurück campaign from five German
deal sources, merges the duplicates, and renders one self-contained page with
images that refreshes every Monday.

```bash
.venv/bin/python run.py            # scrape + merge + images -> data/latest.json, web/img/
.venv/bin/python run.py --cached   # re-merge the last scrape (data/raw.json) without fetching
.venv/bin/python build_site.py     # render                  -> web/index.html
```

`web/index.html` carries its data and images inline (~2 MB): open it directly,
no server needed.

## Sources

| Source | How it is read | Gives |
|---|---|---|
| Sparwelt `/gratis/cashback` | `__NUXT_DATA__` JSON in the page | title, text, campaign link, image, dates |
| DealDoktor `/gratis-testen/` | category `<h2>` + `<ul>`, then each deal page | curated list, image (`og:image`), link via `/goto/` redirect |
| DailyDeal | WordPress API `wp/v2/product?search=gratis testen`, then each post | image, link; end date read from prose |
| Geldschnurrbart | the "Aktuelle Aktionen" table | ~15 hand-checked campaigns, no links |
| mydealz community sheet | public Google Sheet, `gviz/tq?tqx=out:csv` per tab | quota, start time, receipt type, deadlines |

The sheet is linked from the Geldschnurrbart article and maintained by mydealz
users; its "Gebrauchsgegenstände" tab (TV/camera rebates of 30–2000 €) is
deliberately skipped — those are rebates, not free trials.

None of the sources needs a browser, so the weekly run is plain Python.

## Merging

The same campaign shows up in up to five sources under different names
("BiFi TASTY BITES gratis testen" / "Bifi Tasty Bites"). `run.py` merges

1. by campaign URL — host alone for dedicated promo domains, host + path for
   platforms that host many campaigns (`oca-services.com`, `for-me-online.de`,
   `erlebe-haleon.de`, …);
2. by product name tokens, after stripping filler words.

Two offers from the *same* source are never merged (Sparwelt lists "JACOBS
Ganze Bohne – 5 €" and "– 3 €" separately), except DailyDeal posts that point
at the identical campaign page.

The four curated lists only carry running campaigns, so their dates win; the
latest end date among them is used because one list is sometimes stale.
DailyDeal is an archive: an offer only it knows is kept if its parsed end date
is still ahead, or — undated — if it was posted in the last 30 days.

Types: **100 % zurück**, **Teil-Cashback**, **Gratisprobe**, **Produkttest**
(REWE/dm, apply and get picked), **Geld-zurück-Garantie** (refund only if
unhappy). Prämien and Gewinnspiele are dropped.

## Weekly refresh

`.github/workflows/weekly.yml` runs Mondays 04:40 UTC on GitHub Actions and
deploys `web/index.html` straight to GitHub Pages (`actions/deploy-pages`), so
nothing generated is ever committed. Images are cached between runs.

Baseline (KW 41/2026): ~225 raw entries → ~88 running campaigns, about half
of them 100 % refunds. A source dropping to 0 in the run summary means its
reader broke — most likely a layout change on that site.
