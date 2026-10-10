import unittest
from datetime import datetime, timezone

import calibrate as cal

TODAY = datetime(2026, 12, 1, tzinfo=timezone.utc)
BASE = "https://ex.com"


def rec(project, tag, published="2026-10-01T00:00:00Z"):
    return {"project": project, "tag": tag, "published_at": published}


class CalibrateTest(unittest.TestCase):
    def test_winner_up_loser_down(self):
        recs = [rec("Stripe Node", f"v{i}") for i in range(10)] + [rec("Vite", f"v{i}") for i in range(10)]
        clicks = {cal.page_url(BASE, r): {"clicks": 100 if r["project"] == "Stripe Node" else 10, "impressions": 0}
                  for r in recs}
        out = cal.calibrate(recs, clicks, {}, BASE, TODAY)["projects"]
        self.assertGreater(out["Stripe Node"]["multiplier"], 1.0)
        self.assertLess(out["Vite"]["multiplier"], 1.0)

    def test_revenue_counts(self):
        recs = [rec("A", "v1"), rec("B", "v1")]
        rev = {cal.page_url(BASE, recs[0]): 5.0}
        out = cal.calibrate(recs, {}, rev, BASE, TODAY)["projects"]
        self.assertGreater(out["A"]["multiplier"], out["B"]["multiplier"])
        self.assertEqual(out["A"]["revenue"], 5.0)

    def test_young_pages_ignored_and_no_data_is_neutral(self):
        recs = [rec("A", "v1", "2026-11-25T00:00:00Z"), rec("B", "v1")]
        out = cal.calibrate(recs, {}, {}, BASE, TODAY)["projects"]
        self.assertNotIn("A", out)
        self.assertEqual(out["B"]["multiplier"], 1.0)

    def test_one_lucky_page_is_shrunk(self):
        recs = [rec("Lucky", "v1")] + [rec("Steady", f"v{i}") for i in range(20)]
        clicks = {cal.page_url(BASE, recs[0]): {"clicks": 1000, "impressions": 0}}
        clicks.update({cal.page_url(BASE, r): {"clicks": 10, "impressions": 0} for r in recs[1:]})
        m = cal.calibrate(recs, clicks, {}, BASE, TODAY)["projects"]["Lucky"]["multiplier"]
        self.assertLessEqual(m, 3.0)


if __name__ == "__main__":
    unittest.main()
