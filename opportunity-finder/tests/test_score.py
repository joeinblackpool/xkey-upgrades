import unittest

from finder import score


class ScoreTest(unittest.TestCase):
    def test_spike_raises_demand(self):
        flat = score.demand_score(100, 100, 0, 0)
        spike = score.demand_score(400, 100, 0, 0)
        self.assertGreater(spike, flat)

    def test_breaking_changes_raise_demand(self):
        self.assertGreater(score.demand_score(50, 50, 0, 3), score.demand_score(50, 50, 0, 0))

    def test_forum_heavy_serp_is_a_gap(self):
        forums = [{"url": "https://www.reddit.com/r/nextjs/x"}] * 7 + \
                 [{"url": "https://nextjs.org/docs", "title": "Docs"}] * 3
        gap, detail = score.gap_from_serp(forums, "15")
        self.assertEqual(detail["forum_share"], 0.7)
        self.assertAlmostEqual(gap, 0.9)  # no dedicated v15 page -> +0.2

    def test_dedicated_page_closes_gap(self):
        results = [{"url": "https://nextjs.org/docs/15-upgrade", "title": "Upgrading to 15"}] * 10
        gap, detail = score.gap_from_serp(results, "15")
        self.assertEqual(gap, 0.0)
        self.assertTrue(detail["dedicated_page_for_version"])

    def test_opportunity_is_product(self):
        self.assertEqual(score.opportunity(1.0, 0.5, 0.5), 25.0)
        self.assertEqual(score.opportunity(1.0, 1.0, 0.0), 0.0)

    def test_proxy_gap(self):
        self.assertEqual(score.gap_from_proxy(0, 0), 0.3)
        self.assertEqual(score.gap_from_proxy(100, 40), 0.5)
        self.assertEqual(score.gap_from_proxy(10, 10), 0.8)


if __name__ == "__main__":
    unittest.main()
