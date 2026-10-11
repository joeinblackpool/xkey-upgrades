"""Where is a topic on its S-curve, and is it worth a niche?

The sweet spot is the bottom bend of the S: interest has grown steadily for months,
growth is holding up or speeding up, and the topic is still small enough that few good
pages exist. One-day news spikes, seasonal bumps, people, films and sports are not niches.
"""
import math
import re
from statistics import median

# Weekly human Wikipedia views (roughly 1/10 to 1/50 of monthly Google searches).
TINY = 700          # below ~100/day: too noisy to read a trend
EARLY_MAX = 70_000  # below ~10k/day: still early
MAINSTREAM = 350_000

MIN_GROWTH = 0.015  # 1.5% a week = ~2.2x a year


def weekly(daily):
    n = len(daily) // 7
    d = daily[len(daily) - n * 7:]
    return [sum(d[i * 7:(i + 1) * 7]) for i in range(n)]


def _fit(ys):
    """Least-squares line through log(views): (weekly growth rate, r squared)."""
    ls = [math.log(y + 1) for y in ys]
    n = len(ls)
    xm, ym = (n - 1) / 2, sum(ls) / n
    sxx = sum((x - xm) ** 2 for x in range(n))
    sxy = sum((x - xm) * (y - ym) for x, y in zip(range(n), ls))
    syy = sum((y - ym) ** 2 for y in ls)
    slope = sxy / sxx if sxx else 0.0
    r2 = (sxy * sxy) / (sxx * syy) if sxx and syy else 0.0
    return math.exp(slope) - 1, r2


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def curve(daily):
    """Curve metrics from up to two years of daily views (oldest first)."""
    w = weekly(daily)
    if len(w) < 30 or sum(w[-16:]) == 0:
        return {"stage": "no-data"}
    last16 = w[-16:]
    growth, r2 = _fit(last16)
    g_late, _ = _fit(w[-8:])
    g_early, _ = _fit(w[-16:-8])
    roll = [_mean(w[i - 3:i + 1]) for i in range(len(w) - 12, len(w))]
    up_share = sum(1 for a, b in zip(roll, roll[1:]) if b > a) / (len(roll) - 1)
    med = median(last16) or 1
    spike = max(last16) / med
    recent = _mean(w[-4:])
    m = {
        "weekly_views": round(recent),
        "growth_wk": round(growth, 4),
        "fit_r2": round(r2, 2),
        "up_share": round(up_share, 2),
        "accel": round(g_late - g_early, 4),
        "spike": round(spike, 2),
        "x_12w": round(recent / (_mean(w[-16:-12]) or 1), 2),
    }
    # Same 16 weeks last year: if it rose just as much then, it is seasonal, not a new trend.
    seasonal = None
    if len(w) >= 68:
        ly_growth, _ = _fit(w[-68:-52])
        seasonal = ly_growth >= 0.7 * growth and growth > 0
        m["last_year_growth_wk"] = round(ly_growth, 4)
    peak_i = last16.index(max(last16))
    fading = peak_i < 14 and w[-1] < 0.6 * max(last16)

    if spike > 3.5 or fading:
        stage = "spike"
    elif recent < TINY:
        stage = "tiny"
    elif growth < -0.01:
        stage = "declining"
    elif growth < MIN_GROWTH:
        stage = "flat"
    elif seasonal:
        stage = "seasonal"
    elif recent >= MAINSTREAM:
        stage = "mainstream"
    elif r2 >= 0.6 and up_share >= 0.6 and recent < EARLY_MAX:
        stage = "early"
    elif r2 >= 0.5 and up_share >= 0.5:
        stage = "takeoff"
    else:
        stage = "noisy"
    m["stage"] = stage
    return m


PERSON = re.compile(r"\b(born|died|actor|actress|singer|rapper|songwriter|footballer|cricketer|"
                    r"basketball|baseball|player|politician|musician|comedian|presenter|youtuber|"
                    r"streamer|wrestler|boxer|model|journalist|businessman|businesswoman|athlete|"
                    r"golfer|tennis|coach|manager|criminal|influencer|dj|drummer|guitarist|band)\b", re.I)
MEDIA_EVENT = re.compile(r"\b(film|movie|television|tv series|episode|season \d|album|song|novel|"
                         r"video game|soundtrack|election|referendum|storm|hurricane|earthquake|attack|"
                         r"shooting|murder|death of|disappearance|war|battle|match|final|tournament|"
                         r"championship|cup|grand prix|olympic|festival|award|ceremony|football club|"
                         r"\bfc\b|team|league|wikipedia|list of)\b", re.I)
PLACE_ORG = re.compile(r"\b(city|town|village|county|country|state|province|capital|river|mountain|"
                       r"political party|university|school|newspaper|government|agency|ministry)\b", re.I)
COMMERCIAL = re.compile(r"\b(product|brand|device|app|application|software|platform|service|tool|"
                        r"appliance|vehicle|car|e-?bike|scooter|drone|camera|phone|smartphone|laptop|"
                        r"headphones|wearable|gadget|robot|printer|console|medication|drug|treatment|"
                        r"therapy|supplement|diet|skincare|cosmetic|fragrance|food|drink|beverage|snack|"
                        r"recipe|cuisine|exercise|workout|fitness|sport|hobby|craft|technique|method|"
                        r"material|fabric|plant|breed|pet|garden|home|heating|insulation|solar|battery|"
                        r"energy|insurance|mortgage|loan|investment|tax|benefit|course|qualification|"
                        r"certification|job|career|holiday|travel|destination|fashion|style|trend|"
                        r"subscription|marketplace|retailer|toy|furniture|tea|coffee|wine|beer)\b", re.I)


def classify(term, description, page_type=""):
    """('person'|'media-event'|'place-org'|'commercial'|'other', value multiplier)."""
    text = f"{term} {description}"
    if page_type == "disambiguation" or term.startswith(("Main Page", "Special:", "Wikipedia:", "Portal:")):
        return "junk", 0.0
    if PERSON.search(description):
        return "person", 0.0
    if MEDIA_EVENT.search(text):
        return "media-event", 0.0
    if COMMERCIAL.search(text):
        return "commercial", 1.4
    if PLACE_ORG.search(description):
        return "place-org", 0.4
    return "other", 0.8


def score(m, value, gap=None, hn=None, calibration=1.0):
    """0-100. Only early and takeoff topics score above zero."""
    if m.get("stage") not in ("early", "takeoff") or value <= 0:
        return 0.0
    growth = min(m["growth_wk"], 0.12) / 0.12            # 12%/week or more = full marks
    steadiness = m["fit_r2"] * m["up_share"]
    accel = 1 + max(-0.3, min(0.5, m["accel"] * 15))
    stage = 1.0 if m["stage"] == "early" else 0.55
    # Smaller is better until it is too small to matter: peak around 3k-20k views a week.
    v = m["weekly_views"]
    size = 1.0 if 3_000 <= v <= 20_000 else (0.7 if v < 3_000 else max(0.5, 1 - (v - 20_000) / 150_000))
    gap_m = 1.0 if gap is None else 0.8 + 0.6 * gap
    hn_m = 1.0
    if hn and len(hn) >= 4 and sum(hn[:2]) > 0:
        hn_m = 1.15 if sum(hn[-2:]) > 1.5 * sum(hn[:2]) else 1.0
    raw = growth * steadiness * accel * stage * size * value * gap_m * hn_m * calibration
    return round(min(100.0, raw * 100 / 1.4), 1)
