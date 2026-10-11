import os
import tempfile
import unittest

from build import build, markdown, parse_doc

HUB = """---
title: Cold plunging
short: Cold plunging
description: What cold plunging is and what the evidence says.
updated: 2026-10-11
sources:
  - NHS | https://www.nhs.uk/
---
## What it is
Short **intro** with a [link](https://example.com).

- one
- two
"""
ART = """---
title: Cold plunge tubs compared
description: Types of tub and what they cost.
updated: 2026-10-11
sources:
  - Example | https://example.com/a
---
## Types
| Type | Price |
|---|---|
| Inflatable | £100 |
"""


class BuildTests(unittest.TestCase):
    def test_parse_doc(self):
        m, b = parse_doc(HUB)
        self.assertEqual(m["title"], "Cold plunging")
        self.assertEqual(m["sources"], ["NHS | https://www.nhs.uk/"])
        self.assertTrue(b.startswith("## What it is"))

    def test_markdown(self):
        h, toc = markdown("## A\ntext *em* **b**\n\n1. x\n2. y\n\n| a | b |\n|--|--|\n| 1 | 2 |")
        self.assertIn('<h2 id="a">A</h2>', h)
        self.assertIn("<em>em</em>", h)
        self.assertIn("<ol><li>x</li><li>y</li></ol>", h)
        self.assertIn("<td>1</td>", h)
        self.assertEqual(toc, [("a", "A")])

    def _site(self, live):
        c, o = tempfile.mkdtemp(), tempfile.mkdtemp()
        os.makedirs(os.path.join(c, "cold-plunging"))
        open(os.path.join(c, "cold-plunging", "index.md"), "w").write(HUB)
        open(os.path.join(c, "cold-plunging", "tubs.md"), "w").write(ART)
        out = os.path.join(o, "site")
        return build(c, out, "https://example.com", live), out

    def test_hidden_build(self):
        r, out = self._site(False)
        self.assertEqual(r["errors"], [])
        self.assertEqual((r["niches"], r["articles"]), (1, 1))
        page = open(os.path.join(out, "cold-plunging", "tubs", "index.html")).read()
        self.assertIn('content="noindex, nofollow"', page)
        self.assertIn("Cold plunge tubs compared", page)
        self.assertIn("Disallow: /", open(os.path.join(out, "robots.txt")).read())
        self.assertIn("X-Robots-Tag: noindex", open(os.path.join(out, "_headers")).read())
        self.assertIn("/cold-plunging/tubs/", open(os.path.join(out, "sitemap.xml")).read())

    def test_live_build(self):
        r, out = self._site(True)
        page = open(os.path.join(out, "index.html")).read()
        self.assertNotIn("noindex", page)
        self.assertIn("Sitemap:", open(os.path.join(out, "robots.txt")).read())


if __name__ == "__main__":
    unittest.main()
