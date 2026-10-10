"""Opportunity = Value x Demand spike x Index gap (the README formula), each scaled 0-1.

Pure functions: no network, so they can be unit-tested and tuned.
"""
import math
from urllib.parse import urlparse

# Results from these hosts mean searchers are being served forum threads or issue
# trackers instead of a dedicated answer page: the "index inadequacy" signal.
FORUM_HOSTS = (
    "reddit.com", "stackoverflow.com", "stackexchange.com", "quora.com",
    "github.com",  # issues/discussions
    "discord.com", "news.ycombinator.com", "dev.to", "medium.com",
    "community.", "forum.", "discuss.",
)


def value_score(value):
    """Commercial weight 1-5 -> 0.2-1.0."""
    return max(1, min(5, value)) / 5


def demand_score(recent, baseline, hn_points, breaking_count):
    """Spike in Stack Overflow questions, plus HN attention, plus whether the release breaks things."""
    spike = (recent + 1) / (baseline + 1)
    spike_part = max(0.0, min(1.0, math.log2(spike) / 2))  # 4x spike = full marks
    volume_part = min(1.0, math.log10(recent + 1) / 3)       # 1000 q/window = full marks
    hn_part = min(1.0, hn_points / 500)
    breaking_part = min(1.0, breaking_count / 3)
    return round(0.35 * spike_part + 0.25 * volume_part + 0.15 * hn_part + 0.25 * breaking_part, 3)


def is_forum(url):
    host = urlparse(url).netloc.lower()
    return any(h in host for h in FORUM_HOSTS)


def gap_from_serp(results, version_hint=""):
    """Share of the top results that are forums/issues, bumped if none mention the version."""
    if not results:
        return 0.0, {}
    top = results[:10]
    forum_share = sum(is_forum(r["url"]) for r in top) / len(top)
    version_covered = bool(version_hint) and any(
        version_hint.lower() in (r.get("title", "") + r["url"]).lower()
        for r in top if not is_forum(r["url"]))
    gap = forum_share if version_covered else min(1.0, forum_share + 0.2)
    return round(gap, 3), {"forum_share": round(forum_share, 2),
                           "dedicated_page_for_version": version_covered}


def gap_from_proxy(recent, unanswered):
    """No search API: use the unanswered-question rate as a weaker stand-in for the gap."""
    if recent == 0:
        return 0.0
    return round(min(1.0, unanswered / recent * 1.5), 3)


def opportunity(value, demand, gap):
    return round(100 * value * demand * gap, 1)
