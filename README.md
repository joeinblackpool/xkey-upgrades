# Upgrade Notes (upgrades.xkey.co.uk)

Finds developer-tool releases where searchers are poorly served (forums, thin pages) and publishes a useful upgrade guide for each one.

- `opportunity-finder/`: scores new releases as value × demand spike × gap and writes a ranked list.
- `gap-filler/`: fetches the releases (Go), builds the static site into `gap-filler/site/`, IndexNow, and the Search Console feedback loop.
- `.github/workflows/pipeline.yml`: runs everything daily at 05:17 UTC and commits the new site and a ranked report to `reports/`.
- `wrangler.jsonc`: an assets-only Cloudflare Worker, `xkey-upgrades`, on upgrades.xkey.co.uk. Every push to `main` deploys through Cloudflare Workers Builds, the same setup as the xkey Worker. It's separate from the xkey Worker and doesn't touch it.

## Hidden until launch
Every page is `noindex`, robots.txt blocks crawlers, and nothing is sent to IndexNow. To launch, set the Actions variable `SITE_LIVE` to `true`.

## Tests
    (cd opportunity-finder && python3 -m unittest discover -s tests -t .)
    (cd gap-filler/ingest && go test ./...)
    (cd gap-filler/compiler && python3 -m unittest test_compile)
    (cd gap-filler/publish && python3 -m unittest test_indexnow)
    (cd gap-filler/feedback && python3 -m unittest test_calibrate)
