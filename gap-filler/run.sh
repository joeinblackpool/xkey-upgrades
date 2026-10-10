#!/usr/bin/env bash
# Full pipeline: find gaps -> ingest releases -> build site (keeping every earlier page).
# Usage: BASE_URL=https://yoursite.pages.dev ./run.sh [top_n]
# The site is hidden from search engines unless SITE_LIVE=true.
set -euo pipefail
cd "$(dirname "$0")"
TOP="${1:-50}"
: "${BASE_URL:?set BASE_URL to the public site URL}"
(cd ../opportunity-finder && python3 -m finder.run --days 30 --top "$TOP")
OPS="$(ls -t ../opportunity-finder/output/opportunities-*.json | head -1)"
(cd ingest && go run . -opportunities "../$OPS" -watchlist ../../opportunity-finder/watchlist.json -top "$TOP" -out ../records.json)
LIVE=""; [ "${SITE_LIVE:-false}" = "true" ] && LIVE="--live"
python3 compiler/compile.py records.json --archive state/records.json --out site --base-url "$BASE_URL" $LIVE
