# Gap filler

Turns the opportunity finder's ranked list into a live site of upgrade guides, then learns from what ranks and earns.

| Part | What it does |
|---|---|
| `ingest/` (Go) | Your original worker, fixed. Fetches GitHub releases for the top opportunities and writes `records.json`. |
| `compiler/compile.py` | Your compiler, rewritten. One page per release: breaking changes as a tickable checklist, full release notes, honest `TechArticle` markup citing the source. Writes index, sitemap.xml, robots.txt. Skips thin releases. With `--archive`, keeps every page from earlier runs. |
| `publish/indexnow.py` | Submits only new or changed URLs to IndexNow (Bing and others). Google finds pages through the sitemap in Search Console. |
| `feedback/calibrate.py` | Pulls clicks per page from Search Console (plus optional revenue CSV), works out which projects outperform, and writes `opportunity-finder/calibration.json`. The finder multiplies its scores by these. |
| `../.github/workflows/pipeline.yml` | Runs all of the above daily and commits the site; Cloudflare deploys it. |
| `run.sh` | Local run: finder → ingest → build. |

## Testing mode (default)

The site is **hidden** until you launch it: every page carries `noindex`, robots.txt blocks all crawlers, Cloudflare sends an `X-Robots-Tag: noindex` header, and nothing is sent to IndexNow. Nothing links to it from xkey.co.uk.

To launch, set the repo variable `SITE_LIVE` to `true` (or run locally with `SITE_LIVE=true`). The next run removes all the blocks and starts IndexNow. To keep even humans out while testing, put Cloudflare Access (Zero Trust → Access → Applications) in front of the subdomain.

## Run locally

    BASE_URL=https://yoursite.pages.dev bash run.sh 50

Needs Python 3.9+, Go 1.21+ and network access to GitHub, Stack Exchange and HN Algolia. Output is in `site/`.

## Deploy

See the repo root README. The daily workflow builds `site/` and commits it, and Cloudflare Workers Builds deploys each push to upgrades.xkey.co.uk.

## Tests

    (cd ingest && go test ./...)
    (cd compiler && python3 -m unittest test_compile)
    (cd publish && python3 -m unittest test_indexnow)
    (cd feedback && python3 -m unittest test_calibrate)
