import os
import tempfile
import unittest

import indexnow

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://ex.com/</loc></url>
<url><loc>https://ex.com/a/</loc><lastmod>2026-10-01</lastmod></url>
<url><loc>https://ex.com/b/</loc><lastmod>2026-10-02</lastmod></url>
</urlset>"""


class IndexNowTest(unittest.TestCase):
    def test_only_new_or_changed_urls(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "sitemap.xml")
        open(p, "w").write(SITEMAP)
        cur = indexnow.read_sitemap(p)
        self.assertEqual(len(cur), 3)
        prev = {"https://ex.com/": "", "https://ex.com/a/": "2026-10-01", "https://ex.com/b/": "2026-09-01"}
        self.assertEqual(indexnow.changed(cur, prev), ["https://ex.com/b/"])

    def test_key_file(self):
        d = tempfile.mkdtemp()
        indexnow.write_key_file(d, "abcdef1234")
        self.assertEqual(open(os.path.join(d, "abcdef1234.txt")).read(), "abcdef1234")
        with self.assertRaises(ValueError):
            indexnow.write_key_file(d, "../bad")


if __name__ == "__main__":
    unittest.main()
