import json
import os
import re
import tempfile
import unittest

import compile as c

REC = {
    "project": "Next.js", "repo": "vercel/next.js", "tag": "v15.1.0", "previous_tag": "v15.0.3",
    "query": "Next.js 15 breaking changes", "opportunity": 42.0,
    "release_url": "https://github.com/vercel/next.js/releases/tag/v15.1.0",
    "published_at": "2026-10-01T00:00:00Z",
    "body": "## Breaking\n- Removed `legacyRouter` <script>alert(1)</script>\n- Renamed **x** to y\n```js\nconst a = '</script>';\n```",
    "breaking_lines": ["Removed `legacyRouter` <script>alert(1)</script>", "Renamed **x** to y"],
}


class CompileTest(unittest.TestCase):
    def build(self, records):
        d = tempfile.mkdtemp()
        return d, c.build(records, d, "https://example.com/", "Upgrade Notes", hidden=False)

    def test_page_content_and_markup(self):
        d, (entries, skipped) = self.build([REC])
        self.assertEqual(len(entries), 1)
        html = open(os.path.join(d, "next-js-v15-1-0-upgrade", "index.html")).read()
        self.assertNotIn("<script>alert(1)", html)          # release text is escaped
        self.assertIn("<code>legacyRouter</code>", html)
        self.assertIn("from v15.0.3 to v15.1.0", html)
        self.assertNotIn("DiscussionForumPosting", html)
        ld = json.loads(re.search(r'application/ld\+json">\s*(.*?)\s*</script>', html, re.S).group(1)
                        .replace("<\\/", "</"))
        self.assertEqual(ld["@type"], "TechArticle")
        self.assertEqual(ld["isBasedOn"], REC["release_url"])
        self.assertEqual(html.count('type="checkbox"'), 2)

    def test_thin_records_skipped(self):
        thin = dict(REC, tag="v15.1.1", body="Bug fixes.", breaking_lines=[])
        d, (entries, skipped) = self.build([REC, thin])
        self.assertEqual(len(entries), 1)
        self.assertEqual(skipped, ["Next.js v15.1.1"])

    def test_sitemap_and_robots(self):
        d, _ = self.build([REC])
        sm = open(os.path.join(d, "sitemap.xml")).read()
        self.assertIn("https://example.com/next-js-v15-1-0-upgrade/", sm)
        self.assertIn("Sitemap: https://example.com/sitemap.xml", open(os.path.join(d, "robots.txt")).read())

    def test_hidden_by_default(self):
        d = tempfile.mkdtemp()
        c.build([REC], d, "https://example.com", "Upgrade Notes")
        for f in ("index.html", os.path.join("next-js-v15-1-0-upgrade", "index.html")):
            self.assertIn(c.NOINDEX_META, open(os.path.join(d, f)).read())
        self.assertIn("Disallow: /", open(os.path.join(d, "robots.txt")).read())
        self.assertIn("X-Robots-Tag: noindex", open(os.path.join(d, "_headers")).read())
        # flipping to live removes every block
        c.build([REC], d, "https://example.com", "Upgrade Notes", hidden=False)
        self.assertNotIn(c.NOINDEX_META, open(os.path.join(d, "index.html")).read())
        self.assertFalse(os.path.exists(os.path.join(d, "_headers")))

    def test_archive_keeps_old_pages(self):
        d = tempfile.mkdtemp()
        arch = os.path.join(d, "state", "records.json")
        c.merge_archive([REC], arch)
        newer = dict(REC, tag="v15.2.0", published_at="2026-10-08T00:00:00Z")
        merged = c.merge_archive([newer, dict(REC, body=REC["body"] + "\nmore")], arch)
        self.assertEqual([r["tag"] for r in merged], ["v15.2.0", "v15.1.0"])
        self.assertTrue(merged[1]["body"].endswith("more"))


if __name__ == "__main__":
    unittest.main()
