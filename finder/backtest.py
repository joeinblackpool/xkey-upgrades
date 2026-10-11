"""Would the finder have caught past crazes early? Re-run the curve on old data.

    python3 -m finder.backtest > reports/backtest.txt

For each known craze, reads Wikipedia views up to a date a few weeks BEFORE it went mainstream,
and reports the stage and score the finder would have given on that day.
"""
import sys
from datetime import date

from . import sources
from .score import classify, curve, score

# (article, description to classify with, date before the mainstream peak, when it peaked)
CASES = [
    ("Labubu", "Collectible plush toy", date(2025, 3, 1), "spring-summer 2025"),
    ("Dubai chocolate", "Chocolate bar", date(2024, 11, 15), "Dec 2024 - Jan 2025"),
    ("Prime Hydration", "Sports and energy drink brand", date(2022, 11, 1), "Jan 2023 (UK)"),
    ("Stanley (brand)", "Drinkware brand", date(2023, 10, 1), "Dec 2023 - Jan 2024"),
    ("Pickleball", "Paddle sport", date(2022, 3, 1), "2022-2023"),
    ("Crumbl Cookies", "Cookie bakery chain", date(2022, 2, 1), "2022"),
    # Controls: should NOT score (mature or seasonal).
    ("Air fryer", "Kitchen appliance", date(2025, 6, 1), "control: mature"),
    ("Halloween costume", "Costume worn at Halloween", date(2025, 9, 15), "control: seasonal"),
]


def main():
    baseline_cache = {}
    print(f"{'topic':<20} {'as of':<11} {'stage':<10} {'score':>5}  {'views/wk':>9}  {'x12w':>5}  {'xYoY':>5}  peak")
    for title, desc, as_of, peak in CASES:
        try:
            if as_of not in baseline_cache:
                baseline_cache[as_of] = sources.wiki_total_daily(476, end=as_of)
            daily = sources.wiki_daily_views(title, days=476, end=as_of)
            m = curve(daily, baseline_cache[as_of])
            kind, value = classify(title, desc)
            sc = score(m, value) if "weekly_views" in m else 0
            print(f"{title:<20} {as_of.isoformat():<11} {m['stage']:<10} {sc:>5}  {m.get('weekly_views', 0):>9}  "
                  f"{m.get('x_12w', 0):>5}  {m.get('x_yoy', '-'):>5}  {peak}")
        except Exception as e:
            print(f"{title:<20} error: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
