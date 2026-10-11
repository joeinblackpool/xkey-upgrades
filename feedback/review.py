"""Test-then-scale: decide which tested niches are winners, from Search Console.

    python3 feedback/review.py --niches state/niches.json --base-url https://upgrades.xkey.co.uk \
        --gsc-site sc-domain:xkey.co.uk [--revenue feedback/revenue.csv]

A niche moves  candidate -> testing  when its first pages are published (the writer sets this).
After TEST_DAYS live, a testing niche becomes a winner if its pages together reach
WIN_IMPRESSIONS impressions or WIN_CLICKS clicks in the last 28 days (or any revenue);
if it still hasn't after DROP_DAYS, it is dropped and no more pages are written for it.

Only meaningful once the site is live (SITE_LIVE=true): hidden pages get no impressions.
Search Console access: GSC_CREDENTIALS = service-account JSON added as a user on the property.
"""
import argparse
import csv
import json
import os
import sys
from datetime import date, timedelta

TEST_DAYS = 28
DROP_DAYS = 56
WIN_IMPRESSIONS = 300
WIN_CLICKS = 10


def per_niche(rows, base_url):
    """Sum page-level GSC rows into /<niche>/ folders."""
    base = base_url.rstrip("/") + "/"
    out = {}
    for url, r in rows.items():
        if not url.startswith(base):
            continue
        slug = url[len(base):].split("/")[0]
        if slug:
            o = out.setdefault(slug, {"clicks": 0, "impressions": 0, "pages": 0})
            o["clicks"] += r["clicks"]
            o["impressions"] += r["impressions"]
            o["pages"] += 1
    return out


def decide(niches, stats, revenue, today):
    changes = []
    for n in niches:
        if n.get("status") != "testing" or not n.get("testing_since"):
            continue
        age = (today - date.fromisoformat(n["testing_since"])).days
        s = stats.get(n["slug"], {"clicks": 0, "impressions": 0, "pages": 0})
        rev = round(revenue.get(n["slug"], 0.0), 2)
        n["results_28d"] = {**s, "revenue": rev, "checked": today.isoformat(), "days_live": age}
        if age < TEST_DAYS:
            continue
        if s["impressions"] >= WIN_IMPRESSIONS or s["clicks"] >= WIN_CLICKS or rev > 0:
            n["status"], n["winner_since"] = "winner", today.isoformat()
            changes.append((n["slug"], "winner"))
        elif age >= DROP_DAYS:
            n["status"], n["dropped_since"] = "dropped", today.isoformat()
            changes.append((n["slug"], "dropped"))
    return changes


def fetch_gsc(site, days=28):
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    from urllib.parse import quote
    creds = service_account.Credentials.from_service_account_info(
        json.loads(os.environ["GSC_CREDENTIALS"]), scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    s = AuthorizedSession(creds)
    end = date.today() - timedelta(days=3)
    url = f"https://searchconsole.googleapis.com/webmasters/v3/sites/{quote(site, safe='')}/searchAnalytics/query"
    out, start = {}, 0
    while True:
        r = s.post(url, json={"startDate": str(end - timedelta(days=days)), "endDate": str(end),
                              "dimensions": ["page"], "rowLimit": 25000, "startRow": start})
        r.raise_for_status()
        rows = r.json().get("rows", [])
        for row in rows:
            out[row["keys"][0]] = {"clicks": row["clicks"], "impressions": row["impressions"]}
        if len(rows) < 25000:
            return out
        start += 25000


def read_revenue(path, base_url):
    """CSV page_url,revenue (from an affiliate/ad network export), summed per niche."""
    base = base_url.rstrip("/") + "/"
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            u = row["page_url"].strip()
            if u.startswith(base):
                slug = u[len(base):].split("/")[0]
                out[slug] = out.get(slug, 0.0) + float(row.get("revenue") or 0)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--niches", required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--gsc-site")
    ap.add_argument("--revenue")
    a = ap.parse_args(argv)
    if not (a.gsc_site and os.environ.get("GSC_CREDENTIALS")):
        print("no Search Console access set up; skipping review", file=sys.stderr)
        return 0
    data = json.load(open(a.niches, encoding="utf-8"))
    stats = per_niche(fetch_gsc(a.gsc_site), a.base_url)
    revenue = read_revenue(a.revenue, a.base_url) if a.revenue and os.path.exists(a.revenue) else {}
    for slug, status in decide(data["niches"], stats, revenue, date.today()):
        print(f"{slug}: {status}")
    with open(a.niches, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
