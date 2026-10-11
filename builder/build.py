"""Build the Trending Niches site from content/ into site/.

    python3 builder/build.py            (reads site.json: base_url, live)

content/<niche>/index.md   the niche's hub page (required for the niche to appear)
content/<niche>/<page>.md  articles in that niche
content/about.md           optional About page

Each .md file starts with front matter:
    ---
    title: Cold plunge tubs: what to know before you buy
    description: One or two sentences for search results (under ~155 characters).
    updated: 2026-10-11
    sources:
      - NHS: cold water swimming | https://www.nhs.uk/...
    ---
then Markdown: ## and ### headings, paragraphs, - and 1. lists, **bold**, *italic*,
[links](https://...), > quotes and | tables |. Drafts (draft: true) are skipped.

While site.json has "live": false every page carries noindex and robots.txt blocks crawlers.
"""
import argparse
import html
import json
import os
import re
import shutil
import sys

BRAND = "Trending Niches"
TAGLINE = "Clear, sourced guides to the topics people are just starting to search for."


# ---------- front matter + markdown ----------

def parse_doc(text):
    meta, body = {}, text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            head, body = text[3:end], text[end + 4:]
            key = None
            for line in head.splitlines():
                if not line.strip():
                    continue
                m = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
                if m:
                    key, val = m.group(1), m.group(2).strip()
                    meta[key] = [] if val == "" else val.strip('"')
                elif line.strip().startswith("- ") and key:
                    if not isinstance(meta.get(key), list):
                        meta[key] = []
                    meta[key].append(line.strip()[2:].strip())
    return meta, body.strip("\n")


def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?!\w)", r"<em>\1</em>", t)

    def link(m):
        text, url = m.group(1), m.group(2)
        ext = url.startswith("http")
        attrs = ' rel="noopener" target="_blank"' if ext else ""
        return f'<a href="{html.escape(url)}"{attrs}>{text}</a>'
    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, t)


def slugify(t):
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:60]


def markdown(md):
    out, para, lst, table = [], [], None, []
    toc = []

    def flush():
        nonlocal para, lst, table
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para = []
        if lst:
            tag, items = lst
            out.append(f"<{tag}>" + "".join(f"<li>{inline(i)}</li>" for i in items) + f"</{tag}>")
            lst = None
        if table:
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in table
                    if not re.match(r"^\s*\|?\s*:?-{2,}", r)]
            if rows:
                h = "".join(f"<th>{inline(c)}</th>" for c in rows[0])
                b = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
                out.append(f'<div class="table"><table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>')
            table = []

    for line in md.splitlines():
        s = line.rstrip()
        h = re.match(r"^(#{2,4})\s+(.*)", s)
        ul = re.match(r"^\s*[-*]\s+(.*)", s)
        ol = re.match(r"^\s*\d+[.)]\s+(.*)", s)
        if not s.strip():
            flush()
        elif h:
            flush()
            lvl, text = len(h.group(1)), h.group(2).strip()
            anchor = slugify(re.sub(r"[*`\[\]]", "", text))
            if lvl == 2:
                toc.append((anchor, re.sub(r"[*`]", "", text)))
            out.append(f'<h{lvl} id="{anchor}">{inline(text)}</h{lvl}>')
        elif s.lstrip().startswith("|"):
            if para or lst:
                flush()
            table.append(s)
        elif s.startswith(">"):
            flush()
            out.append(f"<blockquote><p>{inline(s.lstrip('> '))}</p></blockquote>")
        elif ul or ol:
            if para or table:
                flush()
            tag = "ul" if ul else "ol"
            if lst and lst[0] != tag:
                flush()
            lst = lst or (tag, [])
            lst[1].append((ul or ol).group(1))
        elif s.startswith("# "):
            continue  # the page title comes from front matter
        else:
            if lst or table:
                flush()
            para.append(s.strip())
    flush()
    return "\n".join(out), toc


# ---------- pages ----------

CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#5f5e58;--line:#e4e1d8;--accent:#0b6e4f;--card:#fff;--code:#f1efe8}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--fg:#ecebe6;--muted:#a3a19a;--line:#2e2d2a;--accent:#4cc79a;--card:#1c1c1a;--code:#242421}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--accent)}a:hover{text-decoration-thickness:2px}
.wrap{max-width:46rem;margin:0 auto;padding:0 16px}
header.site{border-bottom:1px solid var(--line)}
header.site .wrap{display:flex;align-items:center;justify-content:space-between;gap:12px;padding-top:14px;padding-bottom:14px}
.brand{font-weight:700;color:var(--fg);text-decoration:none;letter-spacing:-.01em}
.brand span{color:var(--accent)}
nav.top a{color:var(--muted);text-decoration:none;margin-left:16px;font-size:15px}
main{padding:28px 0 56px}
h1{font-size:2rem;line-height:1.2;letter-spacing:-.02em;margin:.2em 0 .4em}
h2{font-size:1.35rem;line-height:1.3;margin:1.8em 0 .5em}
h3{font-size:1.1rem;margin:1.4em 0 .4em}
.lede{font-size:1.1rem;color:var(--muted);margin-top:0}
.meta{color:var(--muted);font-size:14px}
.crumbs{font-size:14px;color:var(--muted)}.crumbs a{color:var(--muted)}
.cards{display:grid;gap:14px;padding:0;list-style:none}
.cards li{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px}
.cards a{font-weight:600;text-decoration:none}.cards p{margin:.3em 0 0;color:var(--muted);font-size:15px}
.toc{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 18px;font-size:15px}
.toc ol{margin:.3em 0 0;padding-left:1.2em}
blockquote{margin:1em 0;padding:.2em 1em;border-left:3px solid var(--accent);color:var(--muted)}
code{background:var(--code);padding:.1em .3em;border-radius:4px;font-size:.92em}
.table{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:15px}
th,td{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
.sources{font-size:15px;border-top:1px solid var(--line);margin-top:2.5em;padding-top:1em}
.sources li{margin:.3em 0;overflow-wrap:anywhere}
.note{font-size:14px;color:var(--muted);background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 14px}
footer{border-top:1px solid var(--line);color:var(--muted);font-size:14px;padding:20px 0 40px}
footer a{color:var(--muted)}
"""


def page(cfg, path, title, description, body, crumbs=None, jsonld=None, og_type="website"):
    url = cfg["base"] + path
    robots = "" if cfg["live"] else '<meta name="robots" content="noindex, nofollow">\n'
    crumbs_html = ""
    ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": BRAND, "url": cfg["base"] + "/"}]
    if crumbs:
        parts = [f'<a href="{p}">{html.escape(n)}</a>' if p else html.escape(n) for n, p in crumbs]
        crumbs_html = '<p class="crumbs">' + " › ".join(parts) + "</p>"
        ld.append({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, **({"item": cfg["base"] + p} if p else {})}
            for i, (n, p) in enumerate(crumbs)]})
    if jsonld:
        ld.append(jsonld)
    full_title = title if path == "/" else f"{title} | {BRAND}"
    if len(full_title) > 65:
        full_title = title
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(full_title)}</title>
<meta name="description" content="{html.escape(description)}">
{robots}<link rel="canonical" href="{url}">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:url" content="{url}">
<meta property="og:site_name" content="{BRAND}">
<meta name="twitter:card" content="summary">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<style>{CSS}</style>
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
</head>
<body>
<header class="site"><div class="wrap"><a class="brand" href="/">Trending <span>Niches</span></a>
<nav class="top"><a href="/#niches">Niches</a><a href="/about/">About</a></nav></div></header>
<main><div class="wrap">
{crumbs_html}
{body}
</div></main>
<footer><div class="wrap">{BRAND}: {TAGLINE}<br>Guides are researched from the sources listed on each page and reviewed for accuracy. They are general information, not professional advice. <a href="/about/">About</a></div></footer>
</body>
</html>
"""


def sources_html(srcs):
    if not srcs:
        return ""
    items = []
    for s in srcs:
        if "|" in s:
            name, url = [x.strip() for x in s.rsplit("|", 1)]
            items.append(f'<li><a href="{html.escape(url)}" rel="noopener" target="_blank">{html.escape(name)}</a></li>')
        else:
            items.append(f"<li>{inline(s)}</li>")
    return '<section class="sources"><h2 id="sources">Sources</h2><ol>' + "".join(items) + "</ol></section>"


def toc_html(toc):
    if len(toc) < 3:
        return ""
    return '<nav class="toc" aria-label="Contents"><strong>On this page</strong><ol>' + "".join(
        f'<li><a href="#{a}">{html.escape(t)}</a></li>' for a, t in toc) + "</ol></nav>"


def load_content(content_dir):
    niches = []
    for name in sorted(os.listdir(content_dir)):
        d = os.path.join(content_dir, name)
        if not os.path.isdir(d) or name.startswith((".", "_")):
            continue
        idx = os.path.join(d, "index.md")
        if not os.path.exists(idx):
            continue
        hub_meta, hub_body = parse_doc(open(idx, encoding="utf-8").read())
        if str(hub_meta.get("draft", "")).lower() == "true":
            continue
        arts = []
        for f in sorted(os.listdir(d)):
            if f.endswith(".md") and f != "index.md":
                meta, body = parse_doc(open(os.path.join(d, f), encoding="utf-8").read())
                if str(meta.get("draft", "")).lower() == "true":
                    continue
                arts.append({"slug": f[:-3], "meta": meta, "body": body})
        niches.append({"slug": name, "meta": hub_meta, "body": hub_body, "articles": arts})
    return niches


def check_meta(where, meta, errors):
    for k in ("title", "description", "updated"):
        if not meta.get(k):
            errors.append(f"{where}: missing {k}")
    if meta.get("updated") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(meta["updated"])):
        errors.append(f"{where}: updated must be YYYY-MM-DD")


def build(content_dir, out, base, live):
    cfg = {"base": base.rstrip("/"), "live": live}
    niches = load_content(content_dir)
    errors = []
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    urls = []

    def write(path, text, lastmod=None):
        fp = os.path.join(out, path.strip("/"), "index.html") if path.endswith("/") else os.path.join(out, path.lstrip("/"))
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(text)
        if path.endswith("/"):
            urls.append((cfg["base"] + path, lastmod))

    titles = {}
    for n in niches:
        hub_path = f"/{n['slug']}/"
        hm = n["meta"]
        check_meta(f"{n['slug']}/index.md", hm, errors)
        titles.setdefault(hm.get("title"), []).append(hub_path)
        body_html, toc = markdown(n["body"])
        lst = "".join(f'<li><a href="/{n["slug"]}/{a["slug"]}/">{html.escape(a["meta"].get("title", a["slug"]))}</a>'
                      f'<p>{html.escape(a["meta"].get("description", ""))}</p></li>' for a in n["articles"])
        guides = f'<h2 id="guides">Guides</h2><ul class="cards">{lst}</ul>' if lst else ""
        hub_body = (f'<h1>{html.escape(hm.get("title", n["slug"]))}</h1>'
                    f'<p class="lede">{html.escape(hm.get("description", ""))}</p>'
                    f'<p class="meta">Updated {html.escape(str(hm.get("updated", "")))}</p>'
                    f'{toc_html(toc)}{body_html}{guides}{sources_html(hm.get("sources"))}')
        write(hub_path, page(cfg, hub_path, hm.get("title", n["slug"]), hm.get("description", ""), hub_body,
                             crumbs=[("Home", "/"), (hm.get("short", hm.get("title", n["slug"])), None)],
                             jsonld={"@context": "https://schema.org", "@type": "CollectionPage",
                                     "name": hm.get("title"), "url": cfg["base"] + hub_path,
                                     "dateModified": str(hm.get("updated", ""))}),
              hm.get("updated"))
        for a in n["articles"]:
            m = a["meta"]
            p = f"/{n['slug']}/{a['slug']}/"
            check_meta(f"{n['slug']}/{a['slug']}.md", m, errors)
            if not m.get("sources"):
                errors.append(f"{n['slug']}/{a['slug']}.md: no sources listed")
            titles.setdefault(m.get("title"), []).append(p)
            ab, atoc = markdown(a["body"])
            siblings = [x for x in n["articles"] if x["slug"] != a["slug"]][:6]
            more = ""
            if siblings:
                more = (f'<h2 id="more">More on {html.escape(hm.get("short", hm.get("title", "")))}</h2><ul>' +
                        "".join(f'<li><a href="/{n["slug"]}/{s["slug"]}/">{html.escape(s["meta"].get("title", ""))}</a></li>'
                                for s in siblings) + "</ul>")
            body = (f'<article><h1>{html.escape(m.get("title", a["slug"]))}</h1>'
                    f'<p class="lede">{html.escape(m.get("description", ""))}</p>'
                    f'<p class="meta">Updated {html.escape(str(m.get("updated", "")))}</p>'
                    f'{toc_html(atoc)}{ab}{sources_html(m.get("sources"))}</article>{more}')
            write(p, page(cfg, p, m.get("title", a["slug"]), m.get("description", ""), body,
                          crumbs=[("Home", "/"), (hm.get("short", hm.get("title", n["slug"])), hub_path), (m.get("title", ""), None)],
                          jsonld={"@context": "https://schema.org", "@type": "Article", "headline": m.get("title"),
                                  "description": m.get("description"), "dateModified": str(m.get("updated", "")),
                                  "mainEntityOfPage": cfg["base"] + p,
                                  "publisher": {"@type": "Organization", "name": BRAND, "url": cfg["base"] + "/"}},
                          og_type="article"),
                  m.get("updated"))

    dupes = {t: ps for t, ps in titles.items() if t and len(ps) > 1}
    for t, ps in dupes.items():
        errors.append(f"duplicate title '{t}': {', '.join(ps)}")

    # Home
    cards = "".join(f'<li><a href="/{n["slug"]}/">{html.escape(n["meta"].get("title", n["slug"]))}</a>'
                    f'<p>{html.escape(n["meta"].get("description", ""))}</p></li>' for n in niches)
    home = (f"<h1>{BRAND}</h1><p class=\"lede\">{TAGLINE}</p>"
            "<p>Every guide here covers a topic whose search interest has been climbing steadily for months but "
            "that still has few clear, trustworthy explanations online. Each one is researched from named sources, "
            "which are listed at the bottom of the page.</p>"
            f'<h2 id="niches">Niches</h2>' + (f'<ul class="cards">{cards}</ul>' if cards else
                                             '<p class="note">The first guides are being researched. Check back soon.</p>'))
    write("/", page(cfg, "/", f"{BRAND}: guides to rising topics", TAGLINE, home))

    # About
    about_path = os.path.join(content_dir, "about.md")
    if os.path.exists(about_path):
        am, ab = parse_doc(open(about_path, encoding="utf-8").read())
        about_html, _ = markdown(ab)
        about_title, about_desc = am.get("title", "About"), am.get("description", f"About {BRAND}.")
    else:
        about_title, about_desc = f"About {BRAND}", f"How {BRAND} chooses topics and researches its guides."
        about_html = ""
    write("/about/", page(cfg, "/about/", about_title, about_desc,
                          f"<h1>{html.escape(about_title)}</h1>{about_html}", crumbs=[("Home", "/"), ("About", None)]))

    # 404, favicon, robots, headers, sitemap
    write("/404.html", page(cfg, "/404.html", "Page not found", "This page does not exist.",
                            '<h1>Page not found</h1><p>That page does not exist. <a href="/">Go to the home page</a>.</p>'))
    write("/favicon.svg", '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" '
                          'fill="#0b6e4f"/><path d="M6 24 C13 23 16 9 26 8" stroke="#fff" stroke-width="3.2" fill="none" '
                          'stroke-linecap="round"/></svg>')
    if live:
        write("/robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {cfg['base']}/sitemap.xml\n")
        hdr = "/*\n  Strict-Transport-Security: max-age=31536000\n  X-Content-Type-Options: nosniff\n"
    else:
        write("/robots.txt", "User-agent: *\nDisallow: /\n")
        hdr = "/*\n  X-Robots-Tag: noindex, nofollow\n  X-Content-Type-Options: nosniff\n"
    write("/_headers", hdr + "/favicon.svg\n  Cache-Control: public, max-age=604800\n")
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, lm in urls:
        sm.append(f"<url><loc>{u}</loc>" + (f"<lastmod>{lm}</lastmod>" if lm else "") + "</url>")
    sm.append("</urlset>")
    write("/sitemap.xml", "\n".join(sm) + "\n")
    write("/llms.txt", f"# {BRAND}\n\n> {TAGLINE}\n\n" + "".join(
        f"- [{n['meta'].get('title')}]({cfg['base']}/{n['slug']}/): {n['meta'].get('description', '')}\n" for n in niches))
    return {"niches": len(niches), "articles": sum(len(n["articles"]) for n in niches), "urls": len(urls), "errors": errors}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--content", default="content")
    ap.add_argument("--out", default="site")
    ap.add_argument("--base-url")
    ap.add_argument("--live", action="store_true", help="overrides site.json")
    ap.add_argument("--config", default="site.json")
    a = ap.parse_args(argv)
    cfg = json.load(open(a.config)) if os.path.exists(a.config) else {}
    base = a.base_url or cfg.get("base_url")
    if not base:
        ap.error("--base-url or site.json base_url required")
    live = a.live or bool(cfg.get("live"))
    r = build(a.content, a.out, base, live)
    print(f"built {r['niches']} niches, {r['articles']} articles, {r['urls']} URLs ({'LIVE' if a.live else 'hidden: noindex'})")
    for e in r["errors"]:
        print("ERROR", e, file=sys.stderr)
    return 1 if r["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
