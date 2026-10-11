import math
import unittest

from finder.score import classify, curve, score
from finder.sources import parse_trends_rss
from finder.run import merge_niches, slug


def daily_from_weekly(weeks):
    out = []
    for w in weeks:
        out += [w / 7] * 7
    return out


def growing(start, rate, n=68):
    return [start * (1 + rate) ** i for i in range(n)]


class CurveTests(unittest.TestCase):
    def test_steady_growth_small_is_early(self):
        m = curve(daily_from_weekly([800] * 52 + growing(800, 0.08, 16)))
        self.assertEqual(m["stage"], "early", m)
        self.assertGreater(m["growth_wk"], 0.06)

    def test_news_spike_rejected(self):
        w = [3000] * 60 + [3000, 3000, 40000, 9000, 4000, 3500, 3200, 3100]
        self.assertEqual(curve(daily_from_weekly(w))["stage"], "spike")

    def test_flat(self):
        self.assertEqual(curve(daily_from_weekly([5000] * 68))["stage"], "flat")

    def test_mainstream(self):
        m = curve(daily_from_weekly([200000] * 52 + growing(200000, 0.05, 16)))
        self.assertEqual(m["stage"], "mainstream")

    def test_seasonal(self):
        season = growing(2000, 0.06, 16)
        w = [2000] * 0 + season + [2000] * 36 + season
        self.assertEqual(curve(daily_from_weekly(w))["stage"], "seasonal")

    def test_too_short(self):
        self.assertEqual(curve([10] * 50)["stage"], "no-data")


class ClassifyAndScore(unittest.TestCase):
    def test_people_and_media_score_zero(self):
        self.assertEqual(classify("Jane Doe", "English footballer (born 1999)")[0], "person")
        self.assertEqual(classify("Some Show", "2026 American television series")[0], "media-event")
        self.assertEqual(classify("Thing", "", "disambiguation")[0], "junk")

    def test_commercial(self):
        kind, v = classify("Cold plunge", "Therapy involving immersion in cold water")
        self.assertEqual(kind, "commercial")
        self.assertGreater(v, 1)

    def test_score_prefers_early(self):
        early = curve(daily_from_weekly([800] * 52 + growing(800, 0.08, 16)))
        flat = curve(daily_from_weekly([5000] * 68))
        self.assertGreater(score(early, 1.4), 0)
        self.assertEqual(score(flat, 1.4), 0)
        self.assertEqual(score(early, 0.0), 0)


class RunTests(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(slug("Cold plunge (therapy)"), "cold-plunge")

    def test_parse_trends(self):
        xml = """<?xml version="1.0"?><rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0">
        <channel><item><title>air fryer</title><ht:approx_traffic>2000+</ht:approx_traffic>
        <ht:news_item><ht:news_item_title>Best air fryers</ht:news_item_title></ht:news_item></item></channel></rss>"""
        r = parse_trends_rss(xml)
        self.assertEqual(r[0]["term"], "air fryer")
        self.assertEqual(r[0]["traffic"], "2000+")
        self.assertEqual(r[0]["news"], ["Best air fryers"])

    def test_merge_keeps_status(self):
        c = {"stage": "early", "weekly_views": 5000, "growth_wk": 0.05, "x_12w": 1.8}
        pool = {"Cold plunge": {"score": 50, "curve": c}, "Sauna hat": {"score": 40, "curve": c}}
        old = {"niches": [{"slug": "cold-plunge", "title": "Cold plunge", "status": "testing", "first_ranked": "2026-01-01"},
                          {"slug": "gone", "title": "Gone", "status": "candidate", "last_ranked": "2026-01-01"}]}
        out = merge_niches(old, pool, ["Sauna hat"], "2026-02-01")
        by = {n["slug"]: n for n in out["niches"]}
        self.assertEqual(by["cold-plunge"]["status"], "testing")   # kept while testing
        self.assertNotIn("gone", by)                                # stale candidate dropped
        self.assertEqual(out["niches"][0]["slug"], "cold-plunge")   # testing listed first


if __name__ == "__main__":
    unittest.main()


class ExtraTests(unittest.TestCase):
    def test_new_article_growing_is_early(self):
        w = [0] * 48 + growing(1000, 0.07, 20)
        m = curve(daily_from_weekly(w))
        self.assertTrue(m.get("new_article"))
        self.assertEqual(m["stage"], "early", m)

    def test_sitewide_swing_removed(self):
        # Topic rises exactly with all of Wikipedia (e.g. school term): not a trend.
        base = [1e6 * (1.03 ** (i // 7)) if i >= 52 * 7 else 1e6 for i in range(68 * 7)]
        topic = [b / 200 for b in base]
        self.assertNotIn(curve(topic, base)["stage"], ("early", "takeoff"))
        self.assertIn(curve(topic)["stage"], ("early", "takeoff", "seasonal", "mainstream"))

    def test_broad_and_academic(self):
        self.assertLess(classify("Dog", "Domesticated species of canid", "standard", 200_000)[1], 0.2)
        self.assertEqual(classify("Ancient China", "Overview of and topical guide to ancient China")[0], "academic")
        self.assertEqual(classify("Harvard University", "Private university in Cambridge")[0], "place-org")
