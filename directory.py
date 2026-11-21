#!/usr/bin/env python3
"""Finds the agents' banner pages made with KMyBanners and writes a page that lists them.

A page repo is found by its topic (the app adds "kmybanners") or by its workflow, which calls the
KMyBanners-tool build workflow. Each candidate counts only when GitHub says it was made from the
template or its workflow calls the tool. For each one the agent's page is read for its title,
description and preview image.

    GH_TOKEN=... python3 directory.py site/

Needs only the standard library. Without a token GitHub's code search is skipped (it needs one).
"""
import datetime
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
TEMPLATE = "elkuku/KMyBanners-template"
TOPIC = "kmybanners"
WORKFLOW = "KMyBanners-tool/.github/workflows/build-page.yml"
# The project's own repos mention the workflow too; they are no agents' pages
OWN = {"elkuku/KMyBanners", "elkuku/KMyBanners-tool", "elkuku/KMyBanners-template",
       "elkuku/KMyBanners-directory", "elkuku/KMyBanners-testdata"}
USER_AGENT = "KMyBanners-directory"


def get(url, token=None, accept="application/vnd.github+json", retry=True):
    """The body of a GET request, or None for 403/404/410/422/429 and network errors.

    A rate limit (429, or 403 with Retry-After) waits once, up to a minute, and tries again.
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    if token and url.startswith(API):
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        wait = e.headers.get("Retry-After")
        if retry and (e.code == 429 or (e.code == 403 and wait)):
            seconds = min(int(wait) if wait and wait.isdigit() else 30, 60)
            print(f"  {e.code}, waiting {seconds} s: {url}", file=sys.stderr)
            time.sleep(seconds)
            return get(url, token, accept, retry=False)
        if e.code in (403, 404, 410, 422, 429):
            print(f"  {e.code} {url}", file=sys.stderr)
            return None
        raise
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"  {e} {url}", file=sys.stderr)
        return None


def api(path, token):
    body = get(API + path, token)
    return json.loads(body) if body else None


def search(kind, query, token):
    """All results of a GitHub search (up to 1000)."""
    items, page = [], 1
    while True:
        q = urllib.parse.urlencode({"q": query, "per_page": 100, "page": page})
        r = api(f"/search/{kind}?{q}", token)
        if not r:
            break
        items += r.get("items", [])
        if len(items) >= r.get("total_count", 0) or not r.get("items") or page >= 10:
            break
        page += 1
    return items


def candidates(token):
    names = {r["full_name"] for r in search("repositories", f"topic:{TOPIC}", token)}
    if token:
        hits = search("code", f'"{WORKFLOW}" path:.github/workflows', token)
        if not hits:
            # GitHub's code search often refuses the Actions token (429); the topic search still works
            print("::warning::The code search found nothing or was refused; only the topic search was used.")
        names |= {h["repository"]["full_name"] for h in hits}
    else:
        print("No GH_TOKEN: skipping the code search", file=sys.stderr)
    return sorted(names - OWN, key=str.lower)


def calls_tool(name, token):
    body = get(f"{API}/repos/{name}/contents/.github/workflows/banner-page.yml", token,
               "application/vnd.github.raw+json")
    return bool(body) and WORKFLOW.encode() in body


def meta(page_html, prop):
    """The content of <meta property="og:…"> (either attribute order)."""
    for pattern in (rf'<meta[^>]+property="{prop}"[^>]+content="([^"]*)"',
                    rf'<meta[^>]+content="([^"]*)"[^>]+property="{prop}"'):
        m = re.search(pattern, page_html)
        if m:
            return html.unescape(m.group(1))
    return None


def https(url):
    return url if url and url.startswith("https://") else None


def page_info(repo, token):
    """The agent's page: url, title, description, image, agent; None when the repo doesn't count."""
    name = repo["full_name"]
    from_template = (repo.get("template_repository") or {}).get("full_name") == TEMPLATE
    if not from_template and not calls_tool(name, token):
        print(f"  {name}: neither from the template nor calling the tool", file=sys.stderr)
        return None
    pages = api(f"/repos/{name}/pages", token) or {}
    url = https(pages.get("html_url")) or f"https://{repo['owner']['login'].lower()}.github.io/{repo['name']}/"
    info = {"repo": name, "repoUrl": repo["html_url"], "url": url, "live": False,
            "created": repo["created_at"], "updated": repo["pushed_at"]}
    body = get(url, accept="text/html")
    if body:
        text = body.decode("utf-8", "replace")
        info.update(live=True, title=meta(text, "og:title"), description=meta(text, "og:description"),
                    image=https(meta(text, "og:image")))
        data = get(url.rstrip("/") + "/banners.json", accept="application/json")
        try:
            info["agent"] = json.loads(data).get("agent") if data else None
        except ValueError:
            pass
    return info


def find(token):
    found = []
    for name in candidates(token):
        print(name, file=sys.stderr)
        repo = api(f"/repos/{name}", token)
        if not repo or repo.get("private") or repo.get("archived") or repo.get("is_template"):
            continue
        info = page_info(repo, token)
        if info:
            found.append(info)
    # Live pages first, the most recently updated on top
    live = sorted((p for p in found if p["live"]), key=lambda p: p["updated"], reverse=True)
    return live + [p for p in found if not p["live"]]


def esc(s):
    return html.escape(s or "", quote=True)


def card(p):
    agent = p.get("agent") or p["repo"].split("/")[0]
    image = (f'<img src="{esc(p["image"])}" alt="" loading="lazy">' if p.get("image")
             else '<div class="noimg" aria-hidden="true"></div>')
    desc = esc(p.get("description")) if p["live"] else "No page yet: the first build hasn't finished."
    link = (f'<a class="page" href="{esc(p["url"])}">{esc(p.get("title") or agent)}</a>' if p["live"]
            else f'<span class="page">{esc(agent)}</span>')
    return f"""<li class="card{'' if p['live'] else ' dim'}">
  {image}
  <div class="text">
    <h2>{link}</h2>
    <p>{desc}</p>
    <p class="meta">Updated {esc(p['updated'][:10])} · <a href="{esc(p['repoUrl'])}">{esc(p['repo'])}</a></p>
  </div>
</li>"""


def render(pages, now):
    live = sum(p["live"] for p in pages)
    cards = "\n".join(card(p) for p in pages) or '<li class="empty">No pages found yet.</li>'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KMyBanners Pages</title>
<meta name="description" content="Ingress agents' banner pages made with KMyBanners, found on GitHub every day.">
<style>
:root {{ --bg: #f6f5fa; --card: #fff; --text: #1c1b22; --muted: #625f6e; --line: #e3e0ec; --accent: #5b3fb0; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg: #16151b; --card: #23222b; --text: #ece9f4; --muted: #a9a5b8; --line: #34323f; --accent: #cbbcff; }}
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 16px/1.5 system-ui, sans-serif; }}
main {{ max-width: 860px; margin: 0 auto; padding: 32px 16px 48px; }}
h1 {{ margin: 0 0 4px; font-size: 1.8rem; }}
.lead {{ margin: 0 0 24px; color: var(--muted); }}
a {{ color: var(--accent); }}
ul {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 12px; }}
.card {{ display: flex; gap: 16px; padding: 12px; background: var(--card); border: 1px solid var(--line); border-radius: 12px; }}
.card img, .noimg {{ width: 160px; height: 84px; object-fit: cover; border-radius: 8px; flex: none; background: var(--line); }}
.card.dim {{ opacity: .7; }}
.text {{ min-width: 0; }}
h2 {{ margin: 0 0 4px; font-size: 1.1rem; }}
h2 a {{ text-decoration: none; }}
.card p {{ margin: 0 0 4px; }}
.meta {{ font-size: .875rem; color: var(--muted); overflow-wrap: anywhere; }}
.empty {{ color: var(--muted); }}
footer {{ margin-top: 32px; font-size: .875rem; color: var(--muted); }}
@media (max-width: 520px) {{ .card {{ flex-direction: column; }} .card img, .noimg {{ width: 100%; height: auto; aspect-ratio: 1200/630; }} }}
</style>
</head>
<body>
<main>
  <h1>KMyBanners Pages</h1>
  <p class="lead">{live} agent{'' if live == 1 else 's'} show{'s' if live == 1 else ''} their Ingress mission banners on a page made with
    <a href="https://elkuku.github.io/KMyBanners/">KMyBanners</a>.</p>
  <ul>
{cards}
  </ul>
  <footer>
    <p>Found on GitHub {esc(now)} (UTC), every day: repositories with the topic <code>{TOPIC}</code> or a workflow
      that calls the KMyBanners build, made from the template. Also as <a href="pages.json">pages.json</a>.</p>
    <p>Want yours here? Make your page with the <a href="https://elkuku.github.io/KMyBanners/">KMyBanners app</a>.
      Source: <a href="https://github.com/elkuku/KMyBanners-directory">elkuku/KMyBanners-directory</a>.</p>
  </footer>
</main>
</body>
</html>
"""


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "site"
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    pages = find(token)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
        f.write(render(pages, now))
    with open(os.path.join(out, "pages.json"), "w", encoding="utf-8") as f:
        json.dump({"generated": now, "pages": pages}, f, indent=2, ensure_ascii=False)
    print(f"{len(pages)} pages, {sum(p['live'] for p in pages)} live", file=sys.stderr)


if __name__ == "__main__":
    main()
