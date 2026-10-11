"""Tiny HTTP helper (stdlib only). Wikimedia asks for a descriptive User-Agent with a contact URL."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "xkey-niche-finder/1.0 (https://upgrades.xkey.co.uk/about/; github.com/joeinblackpool/xkey-upgrades)"


def get_text(url, params=None, headers=None, retries=3, accept="*/*"):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    hdrs = {"User-Agent": UA, "Accept": accept}
    hdrs.update(headers or {})
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=25) as resp:
                return resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 401, 403, 404):
                break
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
        time.sleep(2 ** attempt)
    raise RuntimeError(f"GET {url} failed: {last}")


def get_json(url, params=None, headers=None, retries=3):
    return json.loads(get_text(url, params, headers, retries, accept="application/json"))
