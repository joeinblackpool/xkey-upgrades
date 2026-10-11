"""Tell Bing, Yandex, Seznam and others (via IndexNow) about new or changed pages.

    python3 indexnow.py --site ../site --base-url https://example.com --state ../state/indexnow.json

Reads site/sitemap.xml, submits only URLs whose <lastmod> is new since the last run,
and writes the IndexNow key file into the site so it deploys with it.
Set INDEXNOW_KEY (8-128 hex chars) so the key stays the same between runs.
Google does not use IndexNow; it picks pages up from the sitemap in Search Console.
"""
import argparse
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

ENDPOINT = "https://api.indexnow.org/indexnow"
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
BATCH = 10000  # protocol limit per request


def read_sitemap(path):
    root = ET.parse(path).getroot()
    out = {}
    for u in root.findall("sm:url", NS):
        loc = u.find("sm:loc", NS).text.strip()
        lm = u.find("sm:lastmod", NS)
        out[loc] = lm.text.strip() if lm is not None else ""
    return out


def changed(current, previous):
    return [u for u, lm in current.items() if previous.get(u) != lm]


def write_key_file(site_dir, key):
    if not re.fullmatch(r"[A-Za-z0-9-]{8,128}", key):
        raise ValueError("INDEXNOW_KEY must be 8-128 letters, digits or dashes")
    with open(os.path.join(site_dir, f"{key}.txt"), "w") as f:
        f.write(key)


def submit(urls, base_url, key):
    host = urlparse(base_url).netloc
    for i in range(0, len(urls), BATCH):
        body = json.dumps({"host": host, "key": key,
                           "keyLocation": f"{base_url.rstrip('/')}/{key}.txt",
                           "urlList": urls[i:i + BATCH]}).encode()
        req = urllib.request.Request(ENDPOINT, data=body, method="POST",
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        with urllib.request.urlopen(req, timeout=30) as r:
            if r.status not in (200, 202):
                raise RuntimeError(f"IndexNow answered {r.status}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--state", default="state/indexnow.json")
    ap.add_argument("--write-key-only", action="store_true",
                    help="only drop the key file into the site (run before deploy)")
    a = ap.parse_args(argv)
    key = os.environ.get("INDEXNOW_KEY")
    if not key:
        print("INDEXNOW_KEY not set; skipping IndexNow", file=sys.stderr)
        return 0
    write_key_file(a.site, key)
    if a.write_key_only:
        return 0

    current = read_sitemap(os.path.join(a.site, "sitemap.xml"))
    previous = json.load(open(a.state)) if os.path.exists(a.state) else {}
    urls = changed(current, previous)
    if urls:
        submit(urls, a.base_url, key)
    os.makedirs(os.path.dirname(a.state) or ".", exist_ok=True)
    json.dump(current, open(a.state, "w"), indent=1, sort_keys=True)
    print(f"IndexNow: submitted {len(urls)} of {len(current)} URLs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
