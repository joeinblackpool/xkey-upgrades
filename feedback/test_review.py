import unittest
from datetime import date

from review import decide, per_niche


class ReviewTests(unittest.TestCase):
    def test_per_niche(self):
        rows = {"https://x.co/a/": {"clicks": 1, "impressions": 10}, "https://x.co/a/b/": {"clicks": 2, "impressions": 5},
                "https://x.co/c/": {"clicks": 0, "impressions": 3}, "https://other/a/": {"clicks": 9, "impressions": 9}}
        s = per_niche(rows, "https://x.co")
        self.assertEqual(s["a"], {"clicks": 3, "impressions": 15, "pages": 2})
        self.assertEqual(s["c"]["impressions"], 3)

    def test_decide(self):
        t = date(2026, 3, 1)
        niches = [{"slug": "win", "status": "testing", "testing_since": "2026-01-20"},
                  {"slug": "young", "status": "testing", "testing_since": "2026-02-20"},
                  {"slug": "lose", "status": "testing", "testing_since": "2026-01-01"},
                  {"slug": "wait", "status": "testing", "testing_since": "2026-01-25"},
                  {"slug": "cand", "status": "candidate"}]
        stats = {"win": {"clicks": 0, "impressions": 400, "pages": 4}, "young": {"clicks": 50, "impressions": 900, "pages": 4},
                 "lose": {"clicks": 1, "impressions": 20, "pages": 4}, "wait": {"clicks": 0, "impressions": 10, "pages": 4}}
        ch = dict(decide(niches, stats, {}, t))
        self.assertEqual(ch, {"win": "winner", "lose": "dropped"})
        self.assertEqual(niches[1]["status"], "testing")  # too young to judge
        self.assertEqual(niches[3]["status"], "testing")  # between 28 and 56 days, keep waiting


if __name__ == "__main__":
    unittest.main()
