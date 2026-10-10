"""Signal collectors. Each returns plain dicts so scoring stays testable offline."""
import os
import re
import time
from datetime import datetime, timezone

from .http import get_json, github_headers

BREAKING_RE = re.compile(
    r"breaking|removed|deprecat|no longer|migrat|renamed|drop(ped)? support|minimum .*version",
    re.I,
)


def _ts(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def github_releases(repo, since_days):
    """Releases published in the window, with the lines that look like breaking changes."""
    cutoff = time.time() - since_days * 86400
    data = get_json(f"https://api.github.com/repos/{repo}/releases",
                    {"per_page": 30}, github_headers())
    out = []
    for r in data:
        if r.get("draft") or not r.get("published_at"):
            continue
        if _ts(r["published_at"]) < cutoff:
            continue
        body = r.get("body") or ""
        breaking = [l.strip("-* ").strip() for l in body.splitlines() if BREAKING_RE.search(l)]
        out.append({
            "tag": r["tag_name"],
            "name": r.get("name") or r["tag_name"],
            "url": r["html_url"],
            "published_at": r["published_at"],
            "prerelease": r.get("prerelease", False),
            "breaking_lines": [l for l in breaking if l][:20],
        })
    return out


def _se(path, params):
    p = {"site": "stackoverflow", "filter": "total", **params}
    key = os.environ.get("STACKEXCHANGE_KEY")
    if key:
        p["key"] = key
    return get_json(f"https://api.stackexchange.com/2.3/{path}", p)["total"]


def stackoverflow_activity(tag, days):
    """Question counts for the recent window vs the window before it, plus how many went unanswered."""
    now = int(time.time())
    w = days * 86400
    recent = _se("questions", {"tagged": tag, "fromdate": now - w, "todate": now})
    baseline = _se("questions", {"tagged": tag, "fromdate": now - 2 * w, "todate": now - w})
    unanswered = _se("search/advanced", {"tagged": tag, "answers": 0,
                                         "fromdate": now - w, "todate": now})
    return {"recent": recent, "baseline": baseline, "unanswered": unanswered}


def hn_mentions(query, days):
    since = int(time.time()) - days * 86400
    data = get_json("https://hn.algolia.com/api/v1/search_by_date", {
        "query": query, "tags": "story",
        "numericFilters": f"created_at_i>{since}", "hitsPerPage": 50,
    })
    hits = data.get("hits", [])
    return {"stories": len(hits), "points": sum(h.get("points") or 0 for h in hits)}


def serp_urls(query, count=10):
    """Top web results via Brave Search API. Returns None when no key is configured."""
    key = os.environ.get("BRAVE_API_KEY")
    if not key:
        return None
    data = get_json("https://api.search.brave.com/res/v1/web/search",
                    {"q": query, "count": count},
                    {"X-Subscription-Token": key})
    return [{"url": r["url"], "title": r.get("title", "")}
            for r in data.get("web", {}).get("results", [])]
