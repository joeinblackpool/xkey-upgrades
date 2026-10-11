"""Daily run: gather candidates -> read each one's growth curve -> rank early-stage niches.

    python3 -m finder.run --state ../state --reports ../reports [--max-check 600] [--top 40]

Keeps a pool of every topic seen (state/candidates.json) and re-checks each about weekly,
so something first noticed as a tiny blip gets picked up when its curve starts to bend.
Writes state/niches.json (the ranked list, keeping each niche's status) and a dated CSV report.
"""
import argparse
import csv
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

from . import sources
from .score import classify, curve, score

HERE = os.path.dirname(__file__)
RECHECK_DAYS = 7
FORGET_DAYS = 180


def slug(title):
    import re
    s = re.sub(r"\s*\([^)]*\)", "", title).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:60]


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False, sort_keys=True)
        f.write("\n")


def add(pool, title, source, today, extra=None):
    if not title:
        return
    title = title.replace("_", " ")
    e = pool.setdefault(title, {"first_seen": today, "sources": []})
    if source not in e["sources"]:
        e["sources"].append(source)
    e["last_seen"] = today
    if extra:
        e.setdefault("trend_terms", [])
        for t in extra:
            if t not in e["trend_terms"]:
                e["trend_terms"] = (e["trend_terms"] + [t])[-5:]


def gather(pool, today, seeds, log):
    for geo in ("GB", "US"):
        try:
            for t in sources.google_trends(geo):
                add(pool, sources.wiki_resolve(t["term"]), f"trends-{geo}", today, [t["term"]])
        except RuntimeError as e:
            log(f"trends {geo}: {e}")
    try:
        for t in sources.wiki_top():
            add(pool, t, "wiki-top", today)
    except RuntimeError as e:
        log(f"wiki top: {e}")
    cats = seeds.get("categories", [])
    if cats:
        n = len(cats) if os.environ.get("BOOTSTRAP") == "1" else seeds.get("per_day", 8)
        start = (date.today().toordinal() * n) % len(cats)
        for cat in (cats + cats)[start:start + n]:
            try:
                for t in sources.wiki_links(cat):
                    add(pool, t, f"seed:{cat}", today)
            except RuntimeError as e:
                log(f"seed {cat}: {e}")


def due(pool, today, max_check):
    t = date.fromisoformat(today)
    never = [k for k, v in pool.items() if "checked" not in v]
    stale = sorted((k for k, v in pool.items() if "checked" in v and v.get("kind") in ("commercial", "other")
                    and (t - date.fromisoformat(v["checked"])).days >= RECHECK_DAYS),
                   key=lambda k: pool[k]["checked"])
    return (never + stale)[:max_check]


def check(pool, titles, today, log):
    new = [t for t in titles if "kind" not in pool[t]]
    try:
        info = sources.wiki_info(new)
    except RuntimeError as ex:
        log(f"info: {ex}")
        info = {}
    try:
        baseline = sources.wiki_total_daily(476)
    except RuntimeError as ex:
        log(f"baseline: {ex}")
        baseline = None
    for i, title in enumerate(titles):
        e = pool[title]
        try:
            if "kind" not in e:
                s = info.get(title)
                if not s:
                    continue
                if s["missing"]:
                    e.update(kind="junk", value=0.0, checked=today, score=0.0)
                    continue
                e["description"], e["length"] = s["description"], s["length"]
                e["kind"], e["value"] = classify(title, s["description"], s["type"], s["length"])
            e["checked"] = today
            if e["value"] <= 0:
                e["score"] = 0.0
                continue
            e["curve"] = curve(sources.wiki_daily_views(title, days=476), baseline)
            e["score"] = score(e["curve"], e["value"])
        except Exception as ex:  # one bad topic must not stop the run
            log(f"{title}: {ex}")
        if i and i % 100 == 0:
            log(f"checked {i}/{len(titles)}")


def enrich(pool, ranked, log, brave_top=25, hn_top=40):
    for i, title in enumerate(ranked):
        e = pool[title]
        try:
            if i < hn_top:
                e["hn_monthly"] = sources.hn_monthly_mentions(title.split(" (")[0])
            if i < brave_top:
                gaps = [g for g in (sources.brave_gap(title.split(" (")[0], c) for c in ("GB", "US")) if g is not None]
                e["serp_gap"] = round(sum(gaps) / len(gaps), 2) if gaps else None
            e["score"] = score(e["curve"], e["value"], e.get("serp_gap"), e.get("hn_monthly"))
        except Exception as ex:
            log(f"enrich {title}: {ex}")


def forget(pool, today):
    t = date.fromisoformat(today)
    for k in [k for k, v in pool.items()
              if not v.get("score") and (t - date.fromisoformat(v.get("last_seen", v["first_seen"]))).days > FORGET_DAYS]:
        del pool[k]


def rank(pool, top):
    scored = [k for k, v in pool.items() if v.get("score", 0) > 0]
    return sorted(scored, key=lambda k: -pool[k]["score"])[:top]


def merge_niches(old, pool, ranked, today):
    """Keep status/history for niches already being tested; refresh metrics for all."""
    by_slug = {n["slug"]: n for n in old.get("niches", [])}
    for title in ranked:
        e, s = pool[title], slug(title)
        n = by_slug.setdefault(s, {"slug": s, "title": title, "status": "candidate", "first_ranked": today})
        n.update({"score": e["score"], "stage": e["curve"]["stage"], "weekly_views": e["curve"]["weekly_views"],
                  "growth_wk": e["curve"]["growth_wk"], "x_12w": e["curve"]["x_12w"],
                  "description": e.get("description", ""), "last_ranked": today,
                  "wikipedia": "https://en.wikipedia.org/wiki/" + title.replace(" ", "_"),
                  "trend_terms": e.get("trend_terms", []), "serp_gap": e.get("serp_gap")})
    # Niches being tested stay listed even if they drop out of today's top.
    for n in by_slug.values():
        if n["slug"] not in {slug(t) for t in ranked} and n["status"] == "candidate":
            n["status"] = "candidate-stale" if n.get("last_ranked", today) < today else n["status"]
    keep = [n for n in by_slug.values() if n["status"] != "candidate-stale"]
    keep.sort(key=lambda n: (n["status"] not in ("winner", "testing"), -n.get("score", 0)))
    return {"updated": today, "niches": keep}


def write_report(path, niches):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cols = ["title", "status", "score", "stage", "weekly_views", "growth_wk", "x_12w", "serp_gap", "description", "wikipedia"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for n in niches:
            w.writerow(n)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=os.path.join(HERE, "..", "state"))
    ap.add_argument("--reports", default=os.path.join(HERE, "..", "reports"))
    ap.add_argument("--max-check", type=int, default=int(os.environ.get("MAX_CHECK", 1500)))
    ap.add_argument("--top", type=int, default=40)
    a = ap.parse_args(argv)
    log = lambda m: print(m, file=sys.stderr, flush=True)  # noqa: E731
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    pool = load(os.path.join(a.state, "candidates.json"), {})
    seeds = load(os.path.join(HERE, "seeds.json"), {})
    gather(pool, today, seeds, log)
    todo = due(pool, today, a.max_check)
    log(f"pool {len(pool)}, checking {len(todo)}")
    check(pool, todo, today, log)
    ranked = rank(pool, a.top)
    enrich(pool, ranked, log)
    ranked = rank(pool, a.top)
    forget(pool, today)
    save(os.path.join(a.state, "candidates.json"), pool)

    niches = merge_niches(load(os.path.join(a.state, "niches.json"), {}), pool, ranked, today)
    save(os.path.join(a.state, "niches.json"), niches)
    write_report(os.path.join(a.reports, f"niches-{today}.csv"), niches["niches"])
    for n in niches["niches"][:15]:
        log(f"{n['score']:5.1f}  {n['stage']:<8} {n['weekly_views']:>7}/wk  x{n['x_12w']:<5} {n['title']}  [{n['status']}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
