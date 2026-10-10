"""Scan the watchlist and write a ranked list of content gaps.

    python3 -m finder.run [--days 14] [--top 20] [--watchlist watchlist.json]

Optional env vars: GITHUB_TOKEN, STACKEXCHANGE_KEY, BRAVE_API_KEY (enables the real gap check).
"""
import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone

from . import score, sources


def major_version(tag):
    m = re.search(r"(\d+)(?:\.(\d+))?", tag)
    return m.group(1) if m else tag


def load_calibration(path):
    """Per-project multipliers learned from real clicks/revenue (gap-filler/feedback/calibrate.py)."""
    if not os.path.exists(path):
        return {}
    return {k: v["multiplier"] for k, v in json.load(open(path))["projects"].items()}


def scan_project(p, days, use_serp, calibration=None):
    rels = [r for r in sources.github_releases(p["repo"], days) if not r["prerelease"]]
    if not rels:
        return []
    so = sources.stackoverflow_activity(p["so_tag"], days)
    hn = sources.hn_mentions(p["name"], days)
    rows = []
    for r in rels:
        ver = major_version(r["tag"])
        query = f"{p['name']} {ver} breaking changes"
        demand = score.demand_score(so["recent"], so["baseline"], hn["points"], len(r["breaking_lines"]))
        serp = sources.serp_urls(query) if use_serp else None
        if serp is not None:
            gap, gap_detail = score.gap_from_serp(serp, f"{ver}")
            gap_method = "serp"
        else:
            gap, gap_detail = score.gap_from_proxy(so["recent"], so["unanswered"]), {}
            gap_method = "proxy:unanswered-rate"
        value = score.value_score(p["value"])
        learned = (calibration or {}).get(p["name"], 1.0)
        rows.append({
            "project": p["name"],
            "release": r["tag"],
            "query": query,
            "opportunity": round(score.opportunity(value, demand, gap) * learned, 1),
            "learned_multiplier": learned,
            "value": value, "demand": demand, "gap": gap, "gap_method": gap_method,
            "so_recent": so["recent"], "so_baseline": so["baseline"], "so_unanswered": so["unanswered"],
            "hn_points": hn["points"],
            "breaking_count": len(r["breaking_lines"]),
            "breaking_sample": r["breaking_lines"][:3],
            "release_url": r["url"],
            "published_at": r["published_at"],
            **{f"gap_{k}": v for k, v in gap_detail.items()},
        })
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--watchlist", default="watchlist.json")
    ap.add_argument("--out", default="output")
    ap.add_argument("--calibration", default="calibration.json")
    a = ap.parse_args(argv)
    calibration = load_calibration(a.calibration)

    projects = json.load(open(a.watchlist))["projects"]
    use_serp = bool(os.environ.get("BRAVE_API_KEY"))
    rows, errors = [], []
    for p in projects:
        try:
            rows += scan_project(p, a.days, use_serp, calibration)
        except Exception as e:  # one bad source shouldn't sink the scan
            errors.append(f"{p['name']}: {e}")
    rows.sort(key=lambda r: r["opportunity"], reverse=True)

    os.makedirs(a.out, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    with open(os.path.join(a.out, f"opportunities-{stamp}.json"), "w") as f:
        json.dump({"generated": stamp, "days": a.days, "errors": errors, "opportunities": rows}, f, indent=2)
    if rows:
        with open(os.path.join(a.out, f"opportunities-{stamp}.csv"), "w", newline="") as f:
            cols = [k for k in rows[0] if k != "breaking_sample"]
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)

    if not use_serp:
        print("note: BRAVE_API_KEY not set, gap uses the unanswered-question proxy")
    for r in rows[: a.top]:
        print(f"{r['opportunity']:6.1f}  {r['query']:<45} v={r['value']} d={r['demand']} g={r['gap']}")
    for e in errors:
        print("error:", e, file=sys.stderr)
    return 0 if rows or not errors else 1


if __name__ == "__main__":
    sys.exit(main())
