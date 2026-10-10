"""Close the loop: learn which projects' pages actually earn, and feed that back into the finder.

    python3 calibrate.py --archive ../state/records.json --base-url https://example.com \
        --out ../../opportunity-finder/calibration.json [--revenue revenue.csv] [--gsc-site sc-domain:example.com]

Performance per page = Search Console clicks + REVENUE_WEIGHT x revenue (from an optional
CSV with columns page_url,revenue exported from your affiliate/ad network).
Each project gets a multiplier vs the site average, shrunk towards 1.0 until it has
enough mature pages, so a couple of lucky pages don't swing the finder.

Search Console access: set GSC_CREDENTIALS to a service-account JSON that has been added
as a user on the Search Console property. Needs `pip install google-auth`.
"""
import argparse
import csv
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "compiler"))
from compile import slugify  # noqa: E402

REVENUE_WEIGHT = 20     # 1 unit of revenue counts as 20 clicks
MIN_AGE_DAYS = 21       # pages younger than this haven't had a fair chance to rank
PRIOR_PAGES = 5         # shrinkage strength
CLAMP = (0.25, 3.0)


def page_url(base_url, rec):
    return f"{base_url.rstrip('/')}/{slugify(rec['project'], rec['tag'], 'upgrade')}/"


def calibrate(records, clicks_by_url, revenue_by_url, base_url, today=None):
    today = today or datetime.now(timezone.utc)
    per_project = {}
    for rec in records:
        published = datetime.fromisoformat(rec["published_at"].replace("Z", "+00:00"))
        if (today - published).days < MIN_AGE_DAYS:
            continue
        url = page_url(base_url, rec)
        clicks = clicks_by_url.get(url, {}).get("clicks", 0)
        impressions = clicks_by_url.get(url, {}).get("impressions", 0)
        revenue = revenue_by_url.get(url, 0.0)
        p = per_project.setdefault(rec["project"], {"pages": 0, "clicks": 0, "impressions": 0,
                                                    "revenue": 0.0, "score": 0.0})
        p["pages"] += 1
        p["clicks"] += clicks
        p["impressions"] += impressions
        p["revenue"] += revenue
        p["score"] += clicks + REVENUE_WEIGHT * revenue

    total_pages = sum(p["pages"] for p in per_project.values())
    site_avg = sum(p["score"] for p in per_project.values()) / total_pages if total_pages else 0
    for p in per_project.values():
        if site_avg == 0:
            m = 1.0
        else:
            m = (p["score"] + PRIOR_PAGES * site_avg) / ((p["pages"] + PRIOR_PAGES) * site_avg)
        p["multiplier"] = round(max(CLAMP[0], min(CLAMP[1], m)), 3)
        p["revenue"] = round(p["revenue"], 2)
        del p["score"]
    return {"generated": today.strftime("%Y-%m-%d"), "site_avg_score_per_page": round(site_avg, 2),
            "projects": per_project}


def read_revenue(path):
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[row["page_url"].strip()] = out.get(row["page_url"].strip(), 0.0) + float(row["revenue"] or 0)
    return out


def fetch_gsc(site, days=90):
    """Clicks and impressions per page from the Search Console API."""
    from google.oauth2 import service_account          # pip install google-auth
    from google.auth.transport.requests import AuthorizedSession
    creds = service_account.Credentials.from_service_account_info(
        json.loads(os.environ["GSC_CREDENTIALS"]),
        scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    s = AuthorizedSession(creds)
    end = date.today() - timedelta(days=3)  # GSC data lags a few days
    from urllib.parse import quote
    url = f"https://searchconsole.googleapis.com/webmasters/v3/sites/{quote(site, safe='')}/searchAnalytics/query"
    out, start_row = {}, 0
    while True:
        r = s.post(url, json={"startDate": str(end - timedelta(days=days)), "endDate": str(end),
                              "dimensions": ["page"], "rowLimit": 25000, "startRow": start_row})
        r.raise_for_status()
        rows = r.json().get("rows", [])
        for row in rows:
            out[row["keys"][0]] = {"clicks": row["clicks"], "impressions": row["impressions"]}
        if len(rows) < 25000:
            return out
        start_row += 25000


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--gsc-site", help="Search Console property, e.g. sc-domain:example.com")
    ap.add_argument("--revenue", help="CSV with page_url,revenue")
    a = ap.parse_args(argv)
    if not (a.gsc_site and os.environ.get("GSC_CREDENTIALS")) and not a.revenue:
        print("no Search Console credentials or revenue file; skipping calibration", file=sys.stderr)
        return 0
    records = json.load(open(a.archive, encoding="utf-8"))
    clicks = fetch_gsc(a.gsc_site) if a.gsc_site and os.environ.get("GSC_CREDENTIALS") else {}
    revenue = read_revenue(a.revenue) if a.revenue else {}
    result = calibrate(records, clicks, revenue, a.base_url)
    json.dump(result, open(a.out, "w"), indent=2)
    for name, p in sorted(result["projects"].items(), key=lambda kv: -kv[1]["multiplier"]):
        print(f"{p['multiplier']:5.2f}x  {name:<16} pages={p['pages']} clicks={p['clicks']} revenue={p['revenue']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
