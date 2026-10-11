# Trending Niches (upgrades.xkey.co.uk)

Finds niches **early on the S-curve** (interest rising steadily for months, still small, not a news spike),
tests each one with a handful of researched pages, and scales up only the ones Google rewards.

| Part | What it does |
|---|---|
| `finder/` | Daily. Gathers candidates (Google Trends UK+US, Wikipedia most-read, category seeds in `finder/seeds.json`), reads 68 weeks of Wikipedia views for each, labels the curve stage (early / takeoff / spike / seasonal / flat / mainstream), filters out people, media and news, and ranks. Writes `state/niches.json` and `reports/niches-DATE.csv`. |
| `WRITING.md` | Brief for the scheduled Claude writer: research, write hub + 3 articles per new niche, scale winners. |
| `content/` | The articles, Markdown with front matter, one folder per niche. |
| `builder/` | Builds `site/` from `content/` (hubs, articles, sitemap, JSON-LD, noindex while hidden). |
| `feedback/` | Test-then-scale: after 28 days a tested niche is a **winner** (300+ impressions or 10+ clicks in 28 days) or, after 56 days without that, **dropped**. Needs Search Console access (`GSC_SITE` variable + `GSC_CREDENTIALS` secret). |
| `site.json` | `base_url` and `live`. While `live` is false every page is noindex and robots.txt blocks crawlers. |

Niche lifecycle: `candidate` → `testing` (writer publishes first pages) → `winner` (writer adds more pages) or `dropped`; `rejected` for unsuitable topics.

Deploy: every push to `main` is deployed by Cloudflare Workers Builds (Worker `xkey-upgrades`).

## Tests
    python3 -m unittest tests.test_finder
    (cd builder && python3 -m unittest test_build)
    (cd feedback && python3 -m unittest test_review)
    (cd publish && python3 -m unittest test_indexnow)
