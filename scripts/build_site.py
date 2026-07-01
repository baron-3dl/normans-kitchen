#!/usr/bin/env python3
"""
Generate the static site from data/recipes.json.

Emits into site/:
  index.html            home: search + category filter + full card grid
  recipe/<slug>.html    one page per recipe (print-friendly, Recipe JSON-LD)
  about.html            About Poppa (placeholder to fill in)
  404.html, sitemap.xml, robots.txt, .nojekyll, favicon.svg

Hand-authored assets (assets/style.css, assets/search.js) are left untouched.
Re-runnable: safe to delete site/recipe and regenerate.
"""
from __future__ import annotations
import json, html, shutil
from urllib.parse import quote, urlsplit
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "recipes.json"
SITE = ROOT / "site"

SITE_TITLE = "Poppa's Recipes"
TAGLINE = "recipes worth keeping"
BASE_URL = "https://baron-3dl.github.io/normans-kitchen"
PATH_PREFIX = (urlsplit(BASE_URL).path.rstrip("/") or "") + "/"   # "/normans-kitchen/"

CATEGORIES = [
    "Chicken & Poultry", "Beef", "Pork", "Meats", "Fish & Seafood", "Pasta",
    "Rice", "Potatoes", "Vegetables", "Salads & Dressings", "Soups & Chowders",
    "Desserts, Pies & Cakes", "Cookies & Bars", "Sauces & Seasonings",
    "Kids' Corner", "Miscellaneous",
]

E = html.escape


def favicon_svg() -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<rect width="64" height="64" rx="10" fill="#f8f1e0"/>'
        '<path d="M14 30h36v14a8 8 0 0 1-8 8H22a8 8 0 0 1-8-8V30z" fill="#b3271b"/>'
        '<rect x="11" y="24" width="42" height="8" rx="4" fill="#2c2620"/>'
        '<rect x="29" y="17" width="6" height="8" rx="3" fill="#2c2620"/>'
        '</svg>'
    )


def head(title, desc, base, canonical, image="", extra_head=""):
    og_img = f'<meta property="og:image" content="{E(image)}">\n' if image else ""
    tw_card = "summary_large_image" if image else "summary"
    tw_img = f'<meta name="twitter:image" content="{E(image)}">\n' if image else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<link rel="canonical" href="{E(canonical)}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{E(canonical)}">
<meta property="og:site_name" content="{E(SITE_TITLE)}">
{og_img}<meta name="twitter:card" content="{tw_card}">
<meta name="twitter:title" content="{E(title)}">
<meta name="twitter:description" content="{E(desc)}">
{tw_img}<link rel="icon" href="{base}favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700;800&family=Lora:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{base}assets/style.css">
{extra_head}</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
"""


def header(base, current, compact=False):
    # exactly one <h1> per page: the wordmark is the h1 on the home page; on
    # recipe/about pages the page's own title is the h1, so the wordmark is a <p>.
    tag = "h1" if current == "home" else "p"
    nav = f"""<nav class="topnav" aria-label="Primary">
  <a href="{base}index.html"{' aria-current="page"' if current=='home' else ''}>All Recipes</a>
  <a href="{base}about.html"{' aria-current="page"' if current=='about' else ''}>About Poppa</a>
</nav>"""
    if compact:
        return f"""<header class="site-header compact">
<div class="wrap">
  <{tag} class="wordmark small"><a href="{base}index.html">{E(SITE_TITLE)}</a></{tag}>
  {nav}
</div>
</header>
"""
    return f"""<header class="site-header">
<div class="wrap">
  <div class="masthead-rule"><span>&#10022;</span></div>
  <{tag} class="wordmark"><a href="{base}index.html">{E(SITE_TITLE)}</a></{tag}>
  <p class="tagline">{E(TAGLINE)}</p>
  <p class="subtag">A family collection</p>
  {nav}
</div>
</header>
"""


def footer(base):
    return f"""<footer class="site-footer">
<div class="wrap">
  <p>Poppa's recipes, gathered and kept for the family. Made with <span class="heart">&hearts;</span></p>
  <p><a href="{base}index.html">All Recipes</a> &nbsp;·&nbsp; <a href="{base}about.html">About Poppa</a></p>
</div>
</footer>
</body>
</html>"""


def ing_line(i):
    return (f'{i["qty"]} {i["item"]}'.strip() if i.get("qty") else i["item"])


def search_signature(r):
    parts = [r["title"], r["category"]]
    for i in r["ingredients"]:
        parts.append(i.get("item", "") or i.get("heading", ""))
    return " ".join(parts).lower()


def card(r):
    has_photo = bool(r.get("image"))
    photo = ""
    if has_photo:
        photo = (f'<div class="card-photo"><img src="{E(r["image"])}" '
                 f'alt="{E(r["title"])}" loading="lazy"></div>')
    n_ing = sum(1 for i in r["ingredients"] if "item" in i)
    meta = f'{n_ing} ingredient{"s" if n_ing != 1 else ""}'
    sig = E(search_signature(r), quote=True)
    return f"""<article class="card{' has-photo' if has_photo else ''}" data-category="{E(r['category'], quote=True)}" data-search="{sig}">
  <a class="card-link" href="recipe/{E(r['slug'])}.html">
    {photo}
    <div class="card-body">
      <span class="card-kicker">{E(r['category'])}</span>
      <h2 class="card-title">{E(r['title'])}</h2>
      <span class="card-meta">{meta}</span>
    </div>
  </a>
</article>"""


def clean_desc(r):
    items = [i["item"] for i in r["ingredients"] if "item" in i]
    lead = f'Poppa\'s recipe for {r["title"]}'
    if r.get("category"):
        lead += f' ({r["category"]})'
    if items:
        acc, out = 0, []
        for it in items:
            if acc + len(it) > 120:
                break
            out.append(it); acc += len(it) + 2
        if out:
            lead += " — " + ", ".join(out)
            if len(out) < len(items):
                lead += "…"
    return lead + "."


def recipe_jsonld(r):
    ings = [ing_line(i) for i in r["ingredients"] if "item" in i]  # skip heading rows
    data = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": r["title"],
        "recipeCategory": r["category"],
        "recipeIngredient": ings,
        "recipeInstructions": [{"@type": "HowToStep", "text": s} for s in r["steps"]],
        "url": f'{BASE_URL}/recipe/{r["slug"]}.html',
    }
    if r.get("image"):
        data["image"] = f'{BASE_URL}/{r["image"]}'
    if r.get("servings"):
        data["recipeYield"] = r["servings"]
    if r.get("source"):
        data["author"] = {"@type": "Organization", "name": r["source"]}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{payload}</script>\n'


def build_index(recipes):
    counts = Counter(r["category"] for r in recipes)
    chips = "\n".join(
        f'<button class="chip" data-cat="{E(c, quote=True)}" aria-pressed="false">'
        f'{E(c)} <span class="count">{counts[c]}</span></button>'
        for c in CATEGORIES if counts.get(c)
    )
    magnifier = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
                 'stroke="currentColor" stroke-width="2" aria-hidden="true">'
                 '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>')
    cards = "\n".join(card(r) for r in recipes)
    desc = (f"{len(recipes)} of Poppa's recipes — chicken, meats, desserts, cookies, "
            "salads, soups and more, gathered for the family.")
    return (
        head(SITE_TITLE, desc, "", BASE_URL + "/")
        + header("", "home")
        + f"""<main id="main" class="wrap">
  <div class="controls">
    <div class="search-box">
      {magnifier}
      <input id="search" type="search" placeholder="Search {len(recipes)} recipes — try “chicken”, “cabbage”, “chocolate”…" aria-label="Search recipes by name, category, or ingredient" autocomplete="off">
    </div>
    <div class="category-bar" role="group" aria-label="Filter by category">
      {chips}
    </div>
    <p class="result-meta" id="result-meta" role="status" aria-live="polite" aria-atomic="true">{len(recipes)} recipes in the collection</p>
  </div>

  <div class="recipe-grid" id="recipe-grid">
    {cards}
    <p class="no-results" id="no-results" role="status" style="display:none">No recipes match — try another word.</p>
  </div>
</main>
"""
        + footer("")
        + '\n<script src="assets/search.js"></script>\n'
    )


def build_recipe(r):
    base = "../"
    ing_html = []
    for i in r["ingredients"]:
        if "heading" in i:
            ing_html.append(f'<li class="ing-heading">{E(i["heading"])}</li>')
        else:
            qty = E(i.get("qty", ""))
            item = E(i.get("item", ""))
            ing_html.append(f'<li><span class="qty">{qty}</span><span class="item">{item}</span></li>')
    ingredients = "\n".join(ing_html)

    steps = r["steps"]
    if len(steps) <= 1:
        body = "".join(f'<li class="single-block">{E(s)}</li>' for s in steps)
        method = f'<ol>{body}</ol>' if steps else '<p><em>No directions were recorded for this recipe.</em></p>'
    else:
        method = "<ol>\n" + "\n".join(f'<li>{E(s)}</li>' for s in steps) + "\n</ol>"

    notes_block = ""
    parts = [f'<p class="note">{E(n)}</p>' for n in r.get("notes", [])]
    if r.get("source"):
        parts.append(f'<p class="source">Source: {E(r["source"])}</p>')
    if parts:
        notes_block = ('<section class="recipe-notes"><h3>Notes</h3>\n'
                       + "\n".join(parts) + '</section>')

    image_url = f'{BASE_URL}/{r["image"]}' if r.get("image") else ""
    photo = f'<img class="recipe-photo" src="{base}{E(r["image"])}" alt="{E(r["title"])}">' if r.get("image") else ""
    servings = f'<p class="recipe-servings">{E(r["servings"])}</p>' if r.get("servings") else ""

    desc = clean_desc(r)
    canonical = f'{BASE_URL}/recipe/{r["slug"]}.html'

    return (
        head(f'{r["title"]} — {SITE_TITLE}', desc, base, canonical,
             image=image_url, extra_head=recipe_jsonld(r))
        + header(base, "", compact=True)
        + f"""<main id="main" class="wrap">
  <article class="recipe">
    <p class="breadcrumb"><a href="{base}index.html">Poppa's Recipes</a> &nbsp;/&nbsp; <a href="{base}index.html?c={quote(r['category'])}">{E(r['category'])}</a></p>
    <h1 class="recipe-title">{E(r['title'])}</h1>
    <div class="recipe-rule"></div>
    {servings}
    {photo}
    <div class="recipe-cols">
      <aside class="ingredients">
        <h3>Ingredients</h3>
        <ul>
{ingredients}
        </ul>
      </aside>
      <div class="method">
        <h3>Directions</h3>
        {method}
        {notes_block}
      </div>
    </div>
    <p class="print-source">{BASE_URL}/recipe/{r["slug"]}.html</p>
    <div class="recipe-foot">
      <a class="btn" href="{base}index.html">&larr; All recipes</a>
      <button class="btn" onclick="window.print()">Print this recipe</button>
    </div>
  </article>
</main>
"""
        + footer(base)
    )


def build_about():
    desc = "About Poppa — the cook behind the recipes."
    return (
        head(f"About Poppa — {SITE_TITLE}", desc, "", BASE_URL + "/about.html")
        + header("", "about")
        + """<main id="main" class="wrap">
  <article class="about">
    <h1>About Poppa</h1>
    <div class="recipe-rule"></div>
    <div class="about-photo">A photo of Poppa<br>goes here</div>
    <p class="placeholder-note">This page is a placeholder — replace the text below (and drop a photo
    into <code>site/images/poppa.jpg</code>, then point the photo frame at it) with Poppa's real story.</p>
    <p>Every recipe on this site came from Poppa's kitchen — collected over the years, cooked for
    the people he loved, and written down so they'd never be lost. Some are clipped from magazines,
    some passed down, some his own invention. Together they're a portrait of a man who fed his family
    with his hands and his heart.</p>
    <p>Write a few paragraphs here about who Poppa was — where he cooked, the dishes people asked
    for again and again, the holidays, the kitchen he stood in. This is the part of the site that
    turns a list of recipes into a keepsake.</p>
    <p style="text-align:center; font-style:italic; color:var(--red); margin-top:2rem;">
    “Recipes worth keeping.”</p>
  </article>
</main>
"""
        + footer("")
    )


def build_404():
    base = PATH_PREFIX
    return (
        head(f"Not found — {SITE_TITLE}", "Page not found", base, BASE_URL + "/404.html")
        + header(base, "")
        + f"""<main id="main" class="wrap" style="text-align:center; padding:3rem 0;">
  <h1 style="font-family:var(--serif-display); font-size:2rem;">This recipe went out of the oven.</h1>
  <p>We couldn't find that page. <a href="{base}index.html">Back to all recipes &rarr;</a></p>
</main>
"""
        + footer(base)
    )


def build_sitemap(recipes):
    urls = [f"{BASE_URL}/", f"{BASE_URL}/about.html"]
    urls += [f'{BASE_URL}/recipe/{r["slug"]}.html' for r in recipes]
    items = "\n".join(f"  <url><loc>{u}</loc></url>" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{items}\n</urlset>\n'


def main():
    recipes = json.loads(DATA.read_text(encoding="utf-8"))

    dups = [s for s, n in Counter(r["slug"] for r in recipes).items() if n > 1]
    if dups:
        raise SystemExit(f"Duplicate slugs would overwrite recipe pages: {dups}")

    rec_dir = SITE / "recipe"
    if rec_dir.exists():
        shutil.rmtree(rec_dir)
    rec_dir.mkdir(parents=True)

    (SITE / "index.html").write_text(build_index(recipes), encoding="utf-8")
    (SITE / "about.html").write_text(build_about(), encoding="utf-8")
    (SITE / "404.html").write_text(build_404(), encoding="utf-8")
    (SITE / "favicon.svg").write_text(favicon_svg(), encoding="utf-8")
    (SITE / "sitemap.xml").write_text(build_sitemap(recipes), encoding="utf-8")
    (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n", encoding="utf-8")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")

    for r in recipes:
        (rec_dir / f'{r["slug"]}.html').write_text(build_recipe(r), encoding="utf-8")

    print(f"Built site: index + about + 404 + {len(recipes)} recipe pages")
    print(f"  photos: {sum(1 for r in recipes if r.get('image'))} | "
          f"JSON-LD on every recipe page")


if __name__ == "__main__":
    main()
