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

MIN_GROWTH = 0.02   # 2% a week (after removing site-wide swings) = ~2.8x a year


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


def normalise(daily, baseline):
    """Remove site-wide swings (school terms, holidays, outages) by scaling to total Wikipedia traffic."""
    if not baseline or len(baseline) != len(daily):
        return daily
    avg = sum(baseline) / len(baseline)
    return [d * avg / b if b else d for d, b in zip(daily, baseline)]


def curve(daily, baseline=None):
    """Curve metrics from up to ~68 weeks of daily views (oldest first).

    New articles (14-29 weeks of history) are judged on what exists; being new and growing is
    itself an early signal, so they are flagged."""
    daily = normalise(daily, baseline)
    first = next((i for i, d in enumerate(daily) if d > 0), len(daily))
    daily = daily[first:]
    w = weekly(daily)
    if len(w) < 14 or sum(w[-12:]) == 0:
        return {"stage": "no-data"}
    if len(w) < 30:
        w = w[1:]  # first week of a new article is usually partial
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
        "weeks_of_data": len(w),
    }
    if len(w) < 30:
        m["new_article"] = True
    # Same 16 weeks last year: if it rose just as much then, it is seasonal, not a new trend.
    # Anything that comes back every year is out: it must have risen as much at this time last
    # year, OR be no higher than a year ago. Real early niches are well above last year's level.
    seasonal = None
    if len(w) >= 68:
        ly_growth, _ = _fit(w[-68:-52])
        yoy = recent / (_mean(w[-56:-52]) or 1)
        m["last_year_growth_wk"] = round(ly_growth, 4)
        m["x_yoy"] = round(yoy, 2)
        seasonal = growth > 0 and (ly_growth >= 0.5 * growth or yoy < 1.5)
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
                    r"golfer|tennis|coach|manager|criminal|influencer|dj|drummer|guitarist|band|writer|author|"
                    r"poet|novelist|playwright|painter|artist|sculptor|philosopher|scientist|physicist|"
                    r"chemist|economist|historian|inventor|engineer|entrepreneur|killer|murderer|"
                    r"terrorist|dictator|monarch|king|queen|prince|princess|emperor|president|"
                    r"prime minister|general|soldier|officer|activist|director|producer|chef|"
                    r"personality|socialite|billionaire)\b|\(born |\(\d{3,4}\s*[–-]\s*\d{3,4}\)", re.I)
MEDIA_EVENT = re.compile(r"\b(film|movie|television|tv series|episode|season \d|album|song|novel|"
                         r"video game|soundtrack|franchise|comic|manga|anime|horror|fictional|character|"
                         r"election\w*|referendum|storm|hurricane|earthquake|attack|"
                         r"shooting|murder|death of|disappearance|war|battle|match|final|tournament|"
                         r"championship|cup|grand prix|olympic|festival|award|ceremony|football club|"
                         r"\bfc\b|team|league|wikipedia|list of)\b", re.I)
ACADEMIC = re.compile(r"\b(philosoph\w*|history of|ancient|empire|dynasty|century|mathemat\w*|theorem|"
                      r"linguistic\w*|grammar|concept|theory|academic|journal|research literature|"
                      r"overview|topical guide|religio\w*|mytholog\w*|deity|god|goddess|saint|"
                      r"legal case|court case|treaty|law of|econom\w*|ideolog\w*|subculture|"
                      r"politic\w*|social\w*|sociolog\w*|psycholog\w* concept|term|entity|system|"
                      r"movement|doctrine|school of thought|genre|art form|literary)\b", re.I)
# Consumer crazes: what young people buy, wear, drink, collect and share. Highest value.
CONSUMER = re.compile(r"\b(toy|toys|plush|collectible|figure|figurine|blind box|trading card|sticker|"
                      r"drink|beverage|energy drink|soda|snack|candy|confectionery|sweet|chocolate|"
                      r"ice cream|bubble tea|cereal|sauce|flavou?r|fashion|clothing|apparel|sneaker|shoe|"
                      r"footwear|trainers|handbag|bag|accessor\w*|jewel\w*|watch|tumbler|bottle|cup|"
                      r"cosmetic\w*|make-?up|skincare|skin care|beauty|lip|nail|hair|fragrance|perfume|"
                      r"brand|product|gadget|device|headphones|earbuds|phone case|app|social media|"
                      r"meme|slang|internet trend|viral|challenge|fad|craze|aesthetic|subculture style|"
                      r"vape|e-cigarette|nicotine pouch|squishy|fidget|slime|keychain|charm|merch\w*)\b", re.I)
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
                        r"subscription|marketplace|retailer|toy|furniture|tea|coffee|wine|beer|extension|gear|equipment|accessory|kit|machine|paddle|racket)\b", re.I)


def classify(term, description, page_type="", length=0):
    """(kind, value multiplier). Broad core topics (very long articles, e.g. "Dog") are not niches."""
    text = f"{term} {description}"
    broad = 0.25 if length > 120_000 else (0.6 if length > 70_000 else 1.0)
    if page_type == "disambiguation" or term.startswith(("Main Page", "Special:", "Wikipedia:", "Portal:")):
        return "junk", 0.0
    if PERSON.search(description):
        return "person", 0.0
    if CONSUMER.search(description) and not re.search(r"\b(film|television|tv series|album|song|episode|novel)\b",
                                                      description, re.I):
        return "consumer", round(1.8 * broad, 2)
    if MEDIA_EVENT.search(text):
        return "media-event", 0.0
    if ACADEMIC.search(description):
        return "academic", 0.0
    if PLACE_ORG.search(description):
        return "place-org", 0.0
    if CONSUMER.search(term):
        return "consumer", round(1.8 * broad, 2)
    if COMMERCIAL.search(text):
        return "commercial", round(1.2 * broad, 2)
    return "other", round(0.3 * broad, 2)


def score(m, value, gap=None, hn=None, calibration=1.0):
    """0-100. Only early and takeoff topics score above zero."""
    if m.get("stage") not in ("early", "takeoff") or value <= 0:
        return 0.0
    growth = min(m["growth_wk"], 0.12) / 0.12            # 12%/week or more = full marks
    steadiness = m["fit_r2"] * m["up_share"]
    accel = 1 + max(-0.3, min(0.5, m["accel"] * 15))
    stage = 1.0 if m["stage"] == "early" else 0.55
    # "From nowhere": a brand-new article, or several times last year's level.
    nowhere = 1.4 if m.get("new_article") else (1.3 if m.get("x_yoy", 0) >= 5 else 1.0)
    # Smaller is better until it is too small to matter: peak around 3k-20k views a week.
    v = m["weekly_views"]
    size = 1.0 if 3_000 <= v <= 20_000 else (0.7 if v < 3_000 else max(0.5, 1 - (v - 20_000) / 150_000))
    gap_m = 1.0 if gap is None else 0.8 + 0.6 * gap
    hn_m = 1.0
    if hn and len(hn) >= 4 and sum(hn[:2]) > 0:
        hn_m = 1.15 if sum(hn[-2:]) > 1.5 * sum(hn[:2]) else 1.0
    raw = growth * steadiness * accel * stage * nowhere * size * value * gap_m * hn_m * calibration
    return round(min(100.0, raw * 100 / 1.8), 1)
