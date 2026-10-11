"""Where candidate niches come from, and where their growth curves come from.

Seeds (what to look at):
  - Google Trends daily trending searches, UK and US (public RSS feed).
  - Wikipedia's most-read articles, skipping the very top (already mainstream).
  - Your own category seeds (seeds.json): the topics linked from each seed article,
    so rising sub-niches inside a category get checked too.

Signals (is it early on the S-curve?):
  - Wikipedia page views per day for the last 52 weeks (free, long history, not news-only).
  - Hacker News mentions per month (tech topics only, a second opinion).
  - Brave Search, if BRAVE_API_KEY is set: how many top-10 results are forums or thin pages
    (a "gap" you can fill). Optional.
"""
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, timedelta

from .http import get_json, get_text

WIKI_REST = "https://wikimedia.org/api/rest_v1/metrics/pageviews"
WIKI_API = "https://en.wikipedia.org/w/api.php"
TRENDS_RSS = "https://trends.google.com/trending/rss"
HT = "{https://trends.google.com/trending/rss}"


def _pause():
    time.sleep(0.05)


def parse_trends_rss(xml_text):
    out = []
    root = ET.fromstring(xml_text)
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        traffic = (item.findtext(f"{HT}approx_traffic") or "").strip()
        news = [n.findtext(f"{HT}news_item_title") or "" for n in item.findall(f"{HT}news_item")]
        if title:
            out.append({"term": title, "traffic": traffic, "news": [x for x in news if x][:3]})
    return out


def google_trends(geo):
    """Today's trending searches for a country ('GB' or 'US')."""
    return parse_trends_rss(get_text(TRENDS_RSS, {"geo": geo}))


def wiki_top(day, skip=40, limit=1000):
    """Most-read English Wikipedia articles on a day, minus the top `skip`."""
    d = day.strftime("%Y/%m/%d")
    data = get_json(f"{WIKI_REST}/top/en.wikipedia/all-access/{d}")
    arts = data["items"][0]["articles"]
    return [a["article"] for a in arts if a["rank"] > skip][:limit]


def wiki_links(title, limit=200):
    """Articles linked from a seed article (namespace 0 only)."""
    data = get_json(WIKI_API, {"action": "query", "prop": "links", "titles": title, "plnamespace": 0,
                               "pllimit": min(limit, 500), "format": "json", "redirects": 1})
    pages = data.get("query", {}).get("pages", {})
    out = []
    for p in pages.values():
        out += [l["title"] for l in p.get("links", [])]
    return out[:limit]


def wiki_resolve(term):
    """Best-matching article title for a search term, or None."""
    data = get_json(WIKI_API, {"action": "opensearch", "search": term, "limit": 1, "namespace": 0,
                               "format": "json", "redirects": "resolve"})
    _pause()
    return data[1][0] if len(data) > 1 and data[1] else None


def wiki_summary(title):
    """Short description and page type (standard / disambiguation)."""
    t = urllib.parse.quote(title.replace(" ", "_"), safe="")
    try:
        data = get_json(f"https://en.wikipedia.org/api/rest_v1/page/summary/{t}")
    except RuntimeError:
        return {"description": "", "type": "missing", "extract": ""}
    _pause()
    return {"description": data.get("description", ""), "type": data.get("type", ""),
            "extract": (data.get("extract") or "")[:400]}


def wiki_daily_views(title, days=364, end=None):
    """Daily human page views, oldest first. Missing days count as 0."""
    end = end or (date.today() - timedelta(days=1))
    start = end - timedelta(days=days - 1)
    t = urllib.parse.quote(title.replace(" ", "_"), safe="")
    try:
        data = get_json(f"{WIKI_REST}/per-article/en.wikipedia/all-access/user/{t}/daily/"
                        f"{start:%Y%m%d}00/{end:%Y%m%d}00")
    except RuntimeError:
        return []
    _pause()
    by_day = {i["timestamp"][:8]: i["views"] for i in data.get("items", [])}
    return [by_day.get((start + timedelta(days=i)).strftime("%Y%m%d"), 0) for i in range(days)]


def hn_monthly_mentions(term, months=6):
    """Hacker News stories+comments mentioning the term, per 30-day block, oldest first."""
    now = int(time.time())
    out = []
    for m in range(months, 0, -1):
        lo, hi = now - m * 30 * 86400, now - (m - 1) * 30 * 86400
        data = get_json("https://hn.algolia.com/api/v1/search",
                        {"query": f'"{term}"', "numericFilters": f"created_at_i>{lo},created_at_i<{hi}",
                         "hitsPerPage": 0})
        out.append(data.get("nbHits", 0))
        _pause()
    return out


THIN = re.compile(r"(reddit\.com|quora\.com|stackexchange|stackoverflow|facebook\.com|tiktok\.com|"
                  r"pinterest\.|x\.com|twitter\.com|youtube\.com|forum|community\.|answers\.)", re.I)


def brave_gap(term, country):
    """Share of the top 10 that are forums/social/video: high = searchers poorly served. None if no key."""
    key = os.environ.get("BRAVE_API_KEY")
    if not key:
        return None
    data = get_json("https://api.search.brave.com/res/v1/web/search",
                    {"q": term, "count": 10, "country": country.lower()},
                    headers={"X-Subscription-Token": key})
    results = data.get("web", {}).get("results", [])
    if not results:
        return None
    return round(sum(1 for r in results if THIN.search(r.get("url", ""))) / len(results), 2)
