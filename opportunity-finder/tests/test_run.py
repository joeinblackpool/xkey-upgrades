"""End-to-end run with the network sources stubbed out."""
import json
import os
import tempfile
import unittest
from unittest import mock

from finder import run, sources

RELEASES = [{"tag": "v15.0.0", "name": "15.0.0", "url": "https://example/rel", "published_at": "2026-10-01T00:00:00Z",
             "prerelease": False, "breaking_lines": ["Removed legacy API", "Renamed config key", "Dropped Node 16"]}]


class RunTest(unittest.TestCase):
    def test_ranks_and_writes_outputs(self):
        with tempfile.TemporaryDirectory() as d, \
             mock.patch.object(sources, "github_releases", return_value=RELEASES), \
             mock.patch.object(sources, "stackoverflow_activity",
                               return_value={"recent": 300, "baseline": 100, "unanswered": 120}), \
             mock.patch.object(sources, "hn_mentions", return_value={"stories": 3, "points": 250}), \
             mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BRAVE_API_KEY", None)
            wl = os.path.join(d, "wl.json")
            json.dump({"projects": [{"name": "Next.js", "repo": "vercel/next.js", "so_tag": "next.js", "value": 5}]},
                      open(wl, "w"))
            self.assertEqual(run.main(["--watchlist", wl, "--out", d]), 0)
            out = [f for f in os.listdir(d) if f.endswith(".json") and f.startswith("opportunities")]
            data = json.load(open(os.path.join(d, out[0])))
            row = data["opportunities"][0]
            self.assertEqual(row["query"], "Next.js 15 breaking changes")
            self.assertEqual(row["gap_method"], "proxy:unanswered-rate")
            self.assertGreater(row["opportunity"], 0)
            self.assertEqual(row["learned_multiplier"], 1.0)

            # a learned 2x multiplier doubles the score
            cal = os.path.join(d, "cal.json")
            json.dump({"projects": {"Next.js": {"multiplier": 2.0}}}, open(cal, "w"))
            for f in os.listdir(d):
                if f.startswith("opportunities"):
                    os.remove(os.path.join(d, f))
            run.main(["--watchlist", wl, "--out", d, "--calibration", cal])
            out = [f for f in os.listdir(d) if f.endswith(".json") and f.startswith("opportunities")]
            row2 = json.load(open(os.path.join(d, out[0])))["opportunities"][0]
            self.assertAlmostEqual(row2["opportunity"], round(row["opportunity"] * 2, 1), places=0)


if __name__ == "__main__":
    unittest.main()
