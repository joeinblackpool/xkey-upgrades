# Opportunity finder

Scans a watchlist of developer tools for new releases and scores each one as a content gap:

**Opportunity = Value × Demand spike × Index gap** (each 0–1, shown as 0–100)

- **Value**: commercial weight you set per project in `watchlist.json` (1–5).
- **Demand**: Stack Overflow question spike vs the previous window, question volume, Hacker News points, and how many breaking-change lines the release notes contain.
- **Gap**: share of the top 10 search results that are forums, issue trackers or Q&A, plus a bump if no dedicated page mentions the version. Needs `BRAVE_API_KEY`; without it, the unanswered-question rate is used as a weaker stand-in.

## Run

    python3 -m finder.run --days 14 --top 20

Writes `output/opportunities-<timestamp>.json` and `.csv` with the evidence for every score.
Python 3.9+, no extra packages. Optional env vars: `GITHUB_TOKEN` (higher rate limit), `STACKEXCHANGE_KEY`, `BRAVE_API_KEY`.

Needs outbound access to api.github.com, api.stackexchange.com, hn.algolia.com and api.search.brave.com.

## Test

    python3 -m unittest discover -s tests -t .
