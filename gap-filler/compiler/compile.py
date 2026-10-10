"""Build a static site from ingested release records: one upgrade-guide page per record,
plus an index, sitemap.xml and robots.txt.

    python3 compile.py records.json --out site --base-url https://example.com --site-name "Upgrade Notes"

Records too thin to be useful (no breaking changes and short notes) are skipped, not padded.
"""
import argparse
import html
import json
import os
import re
import sys
from datetime import datetime, timezone

MIN_BODY_CHARS = 300


def slugify(*parts):
    s = "-".join(parts).lower()
    s = re.sub(r"[^a-z0-9.]+", "-", s).replace(".", "-")
    return re.sub(r"-+", "-", s).strip("-")


def is_thin(rec):
    return not rec.get("breaking_lines") and len(rec.get("body") or "") < MIN_BODY_CHARS


def inline_md(text):
    """Escape, then allow `code`, **bold** and [links](https://...)."""
    t = html.escape(text, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s\"]+)\)",
               lambda m: f'<a href="{html.escape(m.group(2))}" rel="nofollow">{m.group(1)}</a>', t)
    return t


def render_notes(md):
    """Small, safe markdown subset for release notes: headings, bullets, code fences, paragraphs."""
    out, in_list, in_code = [], False, False
    for raw in (md or "").splitlines():
        line = raw.rstrip()
        if line.strip().startswith("```"):
            if in_list:
                out.append("</ul>"); in_list = False
            out.append("</code></pre>" if in_code else "<pre><code>")
            in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(line)); continue
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        b = re.match(r"^\s*[-*]\s+(.*)", line)
        if b:
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append(f"<li>{inline_md(b.group(1))}</li>"); continue
        if in_list:
            out.append("</ul>"); in_list = False
        if m:
            lvl = min(6, len(m.group(1)) + 2)  # page already uses h1/h2
            out.append(f"<h{lvl}>{inline_md(m.group(2))}</h{lvl}>")
        elif line.strip():
            out.append(f"<p>{inline_md(line)}</p>")
    if in_list:
        out.append("</ul>")
    if in_code:
        out.append("</code></pre>")
    return "\n".join(out)


def json_ld(obj):
    return json.dumps(obj, indent=2).replace("</", "<\\/")


CSS = """
:root{--bg:#fff;--fg:#18181b;--muted:#52525b;--card:#f4f4f5;--line:#e4e4e7;--accent:#2563eb}
@media (prefers-color-scheme:dark){:root{--bg:#09090b;--fg:#fafafa;--muted:#a1a1aa;--card:#18181b;--line:#27272a;--accent:#60a5fa}}
body{background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,sans-serif;margin:0;padding:0 16px}
main{max-width:760px;margin:2rem auto}a{color:var(--accent)}
.meta{color:var(--muted);font-size:.9rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:1rem 1.25rem;margin:1.25rem 0}
.check li{list-style:none;margin:.4rem 0}.check{padding-left:0}
.check label{display:flex;gap:.6rem;align-items:flex-start;cursor:pointer}
.check input{margin-top:.35rem}.done{text-decoration:line-through;color:var(--muted)}
progress{width:100%}pre{overflow-x:auto;background:var(--card);padding:.75rem;border-radius:6px}
button{font:inherit;padding:.4rem .8rem;border-radius:6px;border:1px solid var(--line);background:var(--bg);color:var(--fg);cursor:pointer}
"""

CHECKLIST_JS = """
(function(){
  var key='checklist:'+location.pathname, boxes=[].slice.call(document.querySelectorAll('.check input'));
  var bar=document.getElementById('progress'), saved={};
  try{saved=JSON.parse(localStorage.getItem(key)||'{}')}catch(e){}
  function update(){
    var done=0; boxes.forEach(function(b,i){ if(b.checked)done++; b.parentNode.classList.toggle('done',b.checked); saved[i]=b.checked; });
    bar.value=done; bar.max=boxes.length;
    document.getElementById('progress-label').textContent=done+' of '+boxes.length+' handled';
    try{localStorage.setItem(key,JSON.stringify(saved))}catch(e){}
  }
  boxes.forEach(function(b,i){ b.checked=!!saved[i]; b.addEventListener('change',update); });
  document.getElementById('copy').addEventListener('click',function(){
    var md=boxes.map(function(b){return '- ['+(b.checked?'x':' ')+'] '+b.parentNode.textContent.trim()}).join('\\n');
    navigator.clipboard.writeText(md).then(function(){document.getElementById('copy').textContent='Copied'});
  });
  update();
})();
"""


def page(rec, site_name, base_url, slug):
    proj, tag, prev = rec["project"], rec["tag"], rec.get("previous_tag") or ""
    title = f"{proj} {tag}: breaking changes and upgrade checklist"
    from_to = f"from {prev} to {tag}" if prev else f"to {tag}"
    published = rec["published_at"]
    url = f"{base_url}/{slug}/"
    breaking = rec.get("breaking_lines") or []
    desc = (f"{len(breaking)} breaking or behaviour-changing items when upgrading {proj} {from_to}, "
            f"taken from the official release notes, as a checklist you can work through.")
    ld = {
        "@context": "https://schema.org", "@type": "TechArticle",
        "headline": title, "description": desc, "url": url,
        "datePublished": published,
        "dateModified": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "author": {"@type": "Organization", "name": site_name},
        "publisher": {"@type": "Organization", "name": site_name},
        "about": {"@type": "SoftwareApplication", "name": proj, "softwareVersion": tag},
        "isBasedOn": rec["release_url"],
    }
    items = "\n".join(
        f'<li><label><input type="checkbox"><span>{inline_md(l)}</span></label></li>' for l in breaking)
    checklist = f"""
<section class="card">
  <h2>Upgrade checklist</h2>
  <p class="meta">Tick items off as you handle them. Progress is saved in this browser.</p>
  <progress id="progress" value="0" max="1"></progress> <span id="progress-label" class="meta"></span>
  <ul class="check">{items}</ul>
  <button id="copy" type="button">Copy as Markdown task list</button>
</section>""" if breaking else ""
    e = html.escape
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}">
<style>{CSS}</style>
<script type="application/ld+json">
{json_ld(ld)}
</script>
</head>
<body>
<main>
<p class="meta"><a href="{e(base_url)}/">{e(site_name)}</a></p>
<h1>{e(title)}</h1>
<p class="meta">Released {e(published[:10])} · Source: <a href="{e(rec['release_url'])}" rel="nofollow">official {e(proj)} release notes</a></p>
<p>Upgrading {e(proj)} {e(from_to)}? This page pulls out the {len(breaking)} items in the release notes that can break existing code or change behaviour, so you can check each one against your project.</p>
{checklist}
<section>
<h2>Full release notes</h2>
{render_notes(rec.get('body'))}
</section>
</main>
{"<script>" + CHECKLIST_JS + "</script>" if breaking else ""}
</body>
</html>
"""


def index_page(entries, site_name, base_url):
    e = html.escape
    rows = "\n".join(
        f'<li><a href="{e(base_url)}/{e(s)}/">{e(r["project"])} {e(r["tag"])}</a> '
        f'<span class="meta">· {len(r.get("breaking_lines") or [])} breaking items · {e(r["published_at"][:10])}</span></li>'
        for s, r in entries)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(site_name)}</title><link rel="canonical" href="{e(base_url)}/"><style>{CSS}</style></head>
<body><main><h1>{e(site_name)}</h1>
<p>Breaking changes and upgrade checklists for popular developer tools, built from their official release notes.</p>
<ul>{rows}</ul></main></body></html>
"""


def sitemap(entries, base_url):
    urls = [f"<url><loc>{html.escape(base_url)}/</loc></url>"] + [
        f"<url><loc>{html.escape(base_url)}/{html.escape(s)}/</loc><lastmod>{r['published_at'][:10]}</lastmod></url>"
        for s, r in entries]
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>\n")


NOT_FOUND = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>Page not found | {site}</title><style>""" + CSS.replace("{", "{{").replace("}", "}}") + """</style></head>
<body><main><h1>Page not found</h1><p><a href="{base}/">Back to {site}</a></p></main></body></html>
"""

NOINDEX_META = '<meta name="robots" content="noindex, nofollow">'


def hide(html_text):
    """Testing mode: tell every crawler to stay out of the page."""
    return html_text.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n' + NOINDEX_META, 1)


def build(records, out, base_url, site_name, hidden=True):
    base_url = base_url.rstrip("/")
    os.makedirs(out, exist_ok=True)
    entries, skipped = [], []
    seen = set()
    for rec in records:
        if is_thin(rec):
            skipped.append(f"{rec['project']} {rec['tag']}")
            continue
        slug = slugify(rec["project"], rec["tag"], "upgrade")
        if slug in seen:
            continue
        seen.add(slug)
        os.makedirs(os.path.join(out, slug), exist_ok=True)
        with open(os.path.join(out, slug, "index.html"), "w", encoding="utf-8") as f:
            html_text = page(rec, site_name, base_url, slug)
            f.write(hide(html_text) if hidden else html_text)
        entries.append((slug, rec))
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
        html_text = index_page(entries, site_name, base_url)
        f.write(hide(html_text) if hidden else html_text)
    with open(os.path.join(out, "404.html"), "w", encoding="utf-8") as f:
        e = html.escape
        f.write(hide(NOT_FOUND.format(site=e(site_name), base=e(base_url))) if hidden
                else NOT_FOUND.format(site=e(site_name), base=e(base_url)))
    with open(os.path.join(out, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sitemap(entries, base_url))
    with open(os.path.join(out, "robots.txt"), "w", encoding="utf-8") as f:
        if hidden:
            f.write("User-agent: *\nDisallow: /\n")
        else:
            f.write(f"User-agent: *\nAllow: /\nSitemap: {base_url}/sitemap.xml\n")
    headers = os.path.join(out, "_headers")  # Cloudflare Pages response headers
    if hidden:
        with open(headers, "w", encoding="utf-8") as f:
            f.write("/*\n  X-Robots-Tag: noindex, nofollow\n")
    elif os.path.exists(headers):
        os.remove(headers)
    return entries, skipped


def merge_archive(new_records, archive_path):
    """Keep every page ever published: merge this run's records into the archive by project+tag."""
    archive = json.load(open(archive_path, encoding="utf-8")) if os.path.exists(archive_path) else []
    by_key = {(r["project"], r["tag"]): r for r in archive}
    for r in new_records:
        by_key[(r["project"], r["tag"])] = r
    merged = sorted(by_key.values(), key=lambda r: r["published_at"], reverse=True)
    os.makedirs(os.path.dirname(archive_path) or ".", exist_ok=True)
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=1)
    return merged


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("records")
    ap.add_argument("--out", default="site")
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--site-name", default="Upgrade Notes")
    ap.add_argument("--live", action="store_true",
                    help="let search engines index the site; without it every page is noindex (testing mode)")
    ap.add_argument("--archive", help="JSON file of all records published so far; merged and rewritten")
    a = ap.parse_args(argv)
    records = json.load(open(a.records, encoding="utf-8")) or []
    if a.archive:
        records = merge_archive(records, a.archive)
    entries, skipped = build(records, a.out, a.base_url, a.site_name, hidden=not a.live)
    print("LIVE: indexable" if a.live else "HIDDEN: noindex everywhere (pass --live to launch)")
    print(f"built {len(entries)} pages into {a.out}/, skipped {len(skipped)} thin records")
    for s in skipped:
        print("  thin:", s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
