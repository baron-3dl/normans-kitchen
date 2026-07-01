#!/usr/bin/env python3
"""
Generate the static site from data/recipes.json (+ groups.json, enhanced.json,
images.json — the last two are optional and fill in the Enhanced view).

Two view modes, switched by a header toggle (persisted, no reload):
  Original  — faithful transcriptions exactly as Poppa kept them.
  Enhanced  — the same recipe, normalized into clean numbered steps, with a
              sourced photo, a short intro, and cross-links to related recipes.
Each recipe also has its own Enhanced/Original tabs (start from the global mode,
flip locally). Recipes can belong to multiple categories.

Hand-authored assets (style.css, search.js, recipe.js, mode.js) are untouched.
"""
from __future__ import annotations
import json, html, shutil
from urllib.parse import quote, urlsplit
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = ROOT / "site"

SITE_TITLE = "Poppa's Recipes"
TAGLINE = "recipes worth keeping"
BASE_URL = "https://baron-3dl.github.io/normans-kitchen"
PATH_PREFIX = (urlsplit(BASE_URL).path.rstrip("/") or "") + "/"

CATEGORIES = [
    "Chicken & Poultry", "Beef", "Pork", "Meats", "Fish & Seafood", "Pasta",
    "Rice", "Potatoes", "Vegetables", "Salads & Dressings", "Soups & Chowders",
    "Desserts, Pies & Cakes", "Cookies & Bars", "Sauces & Seasonings",
    "Kids' Corner", "Miscellaneous",
]
CATSET = set(CATEGORIES)
E = html.escape


def load(name, default):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def favicon_svg():
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
    tw = "summary_large_image" if image else "summary"
    tw_img = f'<meta name="twitter:image" content="{E(image)}">\n' if image else ""
    return f"""<!doctype html>
<html lang="en" data-mode="original">
<head>
<meta charset="utf-8">
<script>try{{document.documentElement.setAttribute('data-mode',localStorage.getItem('nk-mode')||'original')}}catch(e){{}}</script>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<link rel="canonical" href="{E(canonical)}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{E(canonical)}">
<meta property="og:site_name" content="{E(SITE_TITLE)}">
{og_img}<meta name="twitter:card" content="{tw}">
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


def mode_toggle():
    return ('<div class="mode-toggle" role="group" aria-label="View mode">'
            '<button type="button" data-mode="original" aria-pressed="true">Original</button>'
            '<button type="button" data-mode="enhanced" aria-pressed="false">Enhanced</button>'
            '</div>')


def header(base, current, compact=False):
    tag = "h1" if current == "home" else "p"
    nav = f"""<nav class="topnav" aria-label="Primary">
  <a href="{base}index.html"{' aria-current="page"' if current=='home' else ''}>All Recipes</a>
  <a href="{base}about.html"{' aria-current="page"' if current=='about' else ''}>About Poppa</a>
</nav>"""
    if compact:
        return f"""<header class="site-header compact">
<div class="wrap">
  {mode_toggle()}
  <{tag} class="wordmark small"><a href="{base}index.html">{E(SITE_TITLE)}</a></{tag}>
  {nav}
</div>
</header>
"""
    return f"""<header class="site-header">
<div class="wrap">
  {mode_toggle()}
  <div class="masthead-rule"><span>&#10022;</span></div>
  <{tag} class="wordmark"><a href="{base}index.html">{E(SITE_TITLE)}</a></{tag}>
  <p class="tagline">{E(TAGLINE)}</p>
  <p class="subtag">A family collection</p>
  {nav}
</div>
</header>
"""


def footer(base, extra_scripts=""):
    return f"""<footer class="site-footer">
<div class="wrap">
  <p>Poppa's recipes, gathered and kept for the family. Made with <span class="heart">&hearts;</span></p>
  <p><a href="{base}index.html">All Recipes</a> &nbsp;·&nbsp; <a href="{base}about.html">About Poppa</a></p>
</div>
</footer>
<script src="{base}assets/mode.js"></script>
{extra_scripts}</body>
</html>"""


def ing_line(i):
    return (f'{i["qty"]} {i["item"]}'.strip() if i.get("qty") else i["item"])


def search_signature(r):
    parts = [r["title"], r["category"]]
    parts += [i.get("item", "") or i.get("heading", "") for i in r["ingredients"]]
    return " ".join(parts).lower()


def clean_desc(r, dish=None):
    items = [i["item"] for i in r["ingredients"] if "item" in i]
    lead = f'Poppa\'s recipe for {dish or r["title"]}'
    if r.get("category"):
        lead += f' ({r["category"]})'
    if items:
        acc, out = 0, []
        for it in items:
            if acc + len(it) > 120:
                break
            out.append(it); acc += len(it) + 2
        if out:
            lead += " — " + ", ".join(out) + ("…" if len(out) < len(items) else "")
    return lead + "."


def recipe_jsonld(r, dish=None, enh=None):
    steps = enh["steps"] if (enh and enh.get("faithful") and enh.get("steps")) else r["steps"]
    data = {
        "@context": "https://schema.org", "@type": "Recipe",
        "name": dish or r["title"], "recipeCategory": r["category"],
        "recipeIngredient": [ing_line(i) for i in r["ingredients"] if "item" in i],
        "recipeInstructions": [{"@type": "HowToStep", "text": s} for s in steps],
        "url": f'{BASE_URL}/recipe/{r["slug"]}.html',
    }
    if enh and enh.get("intro"):
        data["description"] = enh["intro"]
    if r.get("servings"):
        data["recipeYield"] = r["servings"]
    if r.get("source"):
        data["author"] = {"@type": "Organization", "name": r["source"]}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{payload}</script>\n'


def render_directions(steps):
    if len(steps) <= 1:
        body = "".join(f'<li class="single-block">{E(s)}</li>' for s in steps)
        return f'<ol>{body}</ol>' if steps else '<p><em>No directions were recorded for this recipe.</em></p>'
    return "<ol>\n" + "\n".join(f'<li>{E(s)}</li>' for s in steps) + "\n</ol>"


class Site:
    def __init__(self):
        self.recipes = load("recipes.json", [])
        self.by_slug = {r["slug"]: r for r in self.recipes}
        self.groups = load("groups.json", [])
        self.enh = load("enhanced.json", {})       # {slug: {...}} or list
        if isinstance(self.enh, list):
            self.enh = {e["slug"]: e for e in self.enh}
        self.img = load("images.json", {})         # {slug: {file, creator, license, ...}}
        self.primary_of = {g["primary"]: g for g in self.groups}
        self.alt_of = {}
        for g in self.groups:
            for m in g["members"]:
                if m != g["primary"]:
                    self.alt_of[m] = g
        self.title_to_slug = {}
        for r in self.recipes:
            self.title_to_slug.setdefault(r["title"].lower(), r["slug"])

    # -- category helpers --------------------------------------------------
    def categories_of(self, slug):
        r = self.by_slug[slug]
        cats = [r["category"]]
        for c in (self.enh.get(slug, {}).get("also_categories") or []):
            if c in CATSET and c not in cats:
                cats.append(c)
        return cats

    def group_categories(self, g):
        cats = []
        for m in g["members"]:
            for c in self.categories_of(m):
                if c not in cats:
                    cats.append(c)
        return cats

    # -- link helpers ------------------------------------------------------
    def canonical_slug(self, slug):
        return self.alt_of[slug]["primary"] if slug in self.alt_of else slug

    def display_name(self, slug):
        if slug in self.primary_of:
            return self.primary_of[slug]["dish"]
        return self.by_slug[slug]["title"]

    def page_href(self, slug, base):
        cs = self.canonical_slug(slug)
        anchor = f"#v-{slug}" if slug in self.alt_of else ""
        return f"{base}recipe/{cs}.html{anchor}"

    def resolve_related(self, slug):
        enh = self.enh.get(slug, {})
        out, seen = [], set()
        home_group = self.alt_of.get(slug) or self.primary_of.get(slug)
        home_members = set(home_group["members"]) if home_group else {slug}
        for title in (enh.get("related") or []):
            t = self.title_to_slug.get(title.lower())
            if not t or t in home_members or t in seen:
                continue
            seen.add(t)
            out.append(t)
            if len(out) >= 4:
                break
        return out

    # -- image helpers -----------------------------------------------------
    def orig_photo(self, slug):
        return self.by_slug[slug].get("image")

    def web_photo(self, slug):
        return self.img.get(slug, {}).get("file")

    def credit_html(self, slug):
        c = self.img.get(slug)
        if not c or not c.get("license"):   # no entry, or a hand-dropped family photo
            return ""
        who = E(c.get("creator") or "Unknown")
        lic = E(c.get("license") or "")
        src = c.get("source") or ""
        who_html = f'<a href="{E(src)}" target="_blank" rel="noopener">{who}</a>' if src else who
        lic_html = f' ({lic})' if lic else ""
        return f'<p class="photo-credit">Photo: {who_html}{lic_html}</p>'

    # -- render one recipe's body (shared + mode-toggled) ------------------
    def render_body(self, slug, base, section_id=None, label=None):
        r = self.by_slug[slug]
        enh = self.enh.get(slug, {})
        # ingredients (shared)
        ing_html = []
        for i in r["ingredients"]:
            if "heading" in i:
                ing_html.append(f'<li class="ing-heading">{E(i["heading"])}</li>')
            else:
                ing_html.append(f'<li><span class="qty">{E(i.get("qty",""))}</span>'
                                 f'<span class="item">{E(i.get("item",""))}</span></li>')
        ingredients = "\n".join(ing_html)

        orig_dirs = render_directions(r["steps"])
        enh_steps = enh["steps"] if (enh.get("faithful") and enh.get("steps")) else r["steps"]
        enh_dirs = render_directions(enh_steps)

        # notes (shared)
        notes_block = ""
        parts = [f'<p class="note">{E(n)}</p>' for n in r.get("notes", [])]
        if r.get("source"):
            parts.append(f'<p class="source">Source: {E(r["source"])}</p>')
        if parts:
            notes_block = '<section class="recipe-notes"><h3>Notes</h3>\n' + "\n".join(parts) + '</section>'

        # images (per mode)
        op, wp = self.orig_photo(slug), self.web_photo(slug)
        enh_img = wp or op
        photo_html = ""
        if op:
            photo_html += f'<div class="only-original recipe-photo-slot"><img class="recipe-photo" src="{base}{E(op)}" alt="{E(r["title"])}"></div>'
        if enh_img:
            cred = self.credit_html(slug) if wp else ""
            photo_html += (f'<div class="only-enhanced recipe-photo-slot"><img class="recipe-photo" '
                           f'src="{base}{E(enh_img)}" alt="{E(r["title"])}" loading="lazy">{cred}</div>')

        intro = f'<p class="recipe-intro only-enhanced">{E(enh["intro"])}</p>' if enh.get("intro") else ""

        # cross-links
        rel = self.resolve_related(slug)
        cross = ""
        if rel:
            lis = "".join(f'<li><a href="{self.page_href(t, base)}">{E(self.display_name(t))}</a></li>' for t in rel)
            cross = f'<section class="crosslinks only-enhanced"><h3>Goes well with</h3><ul>{lis}</ul></section>'

        servings = f'<p class="recipe-servings">{E(r["servings"])}</p>' if r.get("servings") else ""
        ver_title = f'<h2 class="version-title">{E(label)}</h2>' if label else ""
        attrs = f' id="{section_id}"' if section_id else ""
        cls = "version" if section_id else "version single"

        return f"""<section class="{cls}"{attrs}>
    {ver_title}
    {servings}
    {photo_html}
    {intro}
    <div class="recipe-cols">
      <aside class="ingredients">
        <h3>Ingredients</h3>
        <ul>
{ingredients}
        </ul>
      </aside>
      <div class="method">
        <h3>Directions</h3>
        <div class="only-original">{orig_dirs}</div>
        <div class="only-enhanced">{enh_dirs}</div>
        {notes_block}
      </div>
    </div>
    {cross}
  </section>"""

    def has_enhancement(self, slug):
        e = self.enh.get(slug, {})
        return bool(self.web_photo(slug) or e.get("intro") or self.resolve_related(slug)
                    or (e.get("faithful") and e.get("steps")))

    def view_tabs(self, any_enh):
        if not any_enh:
            return ""
        return ('<div class="view-tabs" role="tablist" aria-label="Recipe view">'
                '<a class="view-tab" data-view="enhanced" href="#" role="tab">Enhanced</a>'
                '<a class="view-tab" data-view="original" href="#" role="tab">Original</a>'
                '</div>')

    # -- pages -------------------------------------------------------------
    def recipe_page(self, r):
        base = "../"
        slug = r["slug"]
        enh = self.enh.get(slug, {})
        canonical = f'{BASE_URL}/recipe/{slug}.html'
        img_url = f'{BASE_URL}/{self.web_photo(slug)}' if self.web_photo(slug) else (
            f'{BASE_URL}/{r["image"]}' if r.get("image") else "")
        return (
            head(f'{r["title"]} — {SITE_TITLE}', clean_desc(r), base, canonical,
                 image=img_url, extra_head=recipe_jsonld(r, enh=enh))
            + header(base, "", compact=True)
            + f"""<main id="main" class="wrap">
  <article class="recipe" data-view="original">
    <p class="breadcrumb"><a href="{base}index.html">Poppa's Recipes</a> &nbsp;/&nbsp; <a href="{base}index.html?c={quote(r['category'])}">{E(r['category'])}</a></p>
    {self.view_tabs(self.has_enhancement(slug))}
    <h1 class="recipe-title">{E(r['title'])}</h1>
    <div class="recipe-rule"></div>
    {self.render_body(slug, base)}
    <p class="print-source">{canonical}</p>
    <div class="recipe-foot">
      <a class="btn" href="{base}index.html">&larr; All recipes</a>
      <button class="btn" onclick="window.print()">Print this recipe</button>
    </div>
  </article>
</main>
"""
            + footer(base, f'<script src="{base}assets/recipe.js"></script>\n')
        )

    def group_page(self, g):
        base = "../"
        members = g["members"]
        dish = g["dish"]
        primary = self.by_slug[g["primary"]]
        canonical = f'{BASE_URL}/recipe/{g["slug"]}.html'
        labels, seen = [], {}
        for m in members:
            t = self.by_slug[m]["title"]; k = t.lower()
            seen[k] = seen.get(k, 0) + 1
            labels.append(t if seen[k] == 1 else f"{t} · {seen[k]}")
        img_slug = next((m for m in members if self.web_photo(m) or self.orig_photo(m)), None)
        img_url = ""
        if img_slug:
            wp = self.web_photo(img_slug) or self.orig_photo(img_slug)
            img_url = f"{BASE_URL}/{wp}"
        any_enh = any(self.has_enhancement(m) for m in members)
        pills = "\n".join(
            f'<a class="ver-pill" href="#v-{E(m)}" role="tab" aria-selected="{str(i==0).lower()}">{E(lab)}</a>'
            for i, (m, lab) in enumerate(zip(members, labels)))
        sections = "\n".join(self.render_body(m, base, section_id=f"v-{m}", label=lab)
                             for m, lab in zip(members, labels))
        return (
            head(f'{dish} — {SITE_TITLE}',
                 f"Poppa kept {len(members)} versions of {dish}. " + clean_desc(primary, dish),
                 base, canonical, image=img_url, extra_head=recipe_jsonld(primary, dish, self.enh.get(primary["slug"], {})))
            + header(base, "", compact=True)
            + f"""<main id="main" class="wrap">
  <article class="recipe" data-group="true" data-view="original">
    <p class="breadcrumb"><a href="{base}index.html">Poppa's Recipes</a> &nbsp;/&nbsp; <a href="{base}index.html?c={quote(g['category'])}">{E(g['category'])}</a></p>
    {self.view_tabs(any_enh)}
    <h1 class="recipe-title">{E(dish)}</h1>
    <div class="recipe-rule"></div>
    <p class="versions-intro">Poppa kept <strong>{len(members)}</strong> versions of this dish.</p>
    <p class="versions-note">Follow any recipe, mix and match, or use for inspiration for your own version. <em>That's how Poppa did it.</em></p>
    <div class="versions" role="tablist" aria-label="Versions of {E(dish)}">
      {pills}
    </div>
    {sections}
    <p class="print-source">{canonical}</p>
    <div class="recipe-foot">
      <a class="btn" href="{base}index.html">&larr; All recipes</a>
      <button class="btn" onclick="window.print()">Print this version</button>
    </div>
  </article>
</main>
"""
            + footer(base, f'<script src="{base}assets/recipe.js"></script>\n')
        )

    def alt_stub(self, alt, primary, dish):
        target = f'{primary}.html#v-{alt}'
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{E(dish)} — {SITE_TITLE}</title>
<link rel="canonical" href="{BASE_URL}/recipe/{primary}.html">
<meta http-equiv="refresh" content="0; url={target}">
<script>location.replace({json.dumps(target)});</script>
</head>
<body><p>This recipe is now shown together with Poppa's other versions of
<a href="{target}">{E(dish)}</a>.</p></body>
</html>"""

    def card(self, title, href, cats, search_sig, orig_img, enh_img, meta, is_group=False):
        photo = ""
        if orig_img:
            photo += (f'<div class="card-photo only-original"><img src="{E(orig_img)}" '
                      f'alt="{E(title)}" loading="lazy"></div>')
        if enh_img:
            photo += (f'<div class="card-photo only-enhanced"><img src="{E(enh_img)}" '
                      f'alt="{E(title)}" loading="lazy"></div>')
        ribbon = '<span class="card-ribbon">versions</span>' if is_group else ""
        meta_cls = "card-meta group" if is_group else "card-meta"
        cat_attr = E("|".join(cats), quote=True)
        return f"""<article class="card{' has-photo' if (orig_img or enh_img) else ''}{' is-group' if is_group else ''}" data-categories="{cat_attr}" data-search="{E(search_sig, quote=True)}">
  <a class="card-link" href="{E(href)}">
    {photo}{ribbon}
    <div class="card-body">
      <span class="card-kicker">{E(cats[0])}</span>
      <h2 class="card-title">{E(title)}</h2>
      <span class="{meta_cls}">{E(meta)}</span>
    </div>
  </a>
</article>"""

    def build_index(self):
        cards, counts = [], Counter()
        for r in self.recipes:
            slug = r["slug"]
            if slug in self.alt_of:
                continue
            if slug in self.primary_of:
                g = self.primary_of[slug]
                members = g["members"]
                cats = self.group_categories(g)
                sig = " ".join(search_signature(self.by_slug[m]) for m in members)
                oi = next((self.orig_photo(m) for m in members if self.orig_photo(m)), None)
                wi = next((self.web_photo(m) for m in members if self.web_photo(m)), None) or oi
                cards.append(self.card(g["dish"], f'recipe/{slug}.html', cats, sig, oi, wi,
                                       f"{len(members)} versions", is_group=True))
            else:
                cats = self.categories_of(slug)
                n = sum(1 for i in r["ingredients"] if "item" in i)
                oi = self.orig_photo(slug)
                wi = self.web_photo(slug) or oi
                cards.append(self.card(r["title"], f'recipe/{slug}.html', cats,
                                       search_signature(r), oi, wi,
                                       f'{n} ingredient{"s" if n != 1 else ""}'))
            for c in cats:
                counts[c] += 1

        chips = "\n".join(
            f'<button class="chip" data-cat="{E(c, quote=True)}" aria-pressed="false">'
            f'{E(c)} <span class="count">{counts[c]}</span></button>'
            for c in CATEGORIES if counts.get(c))
        mag = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
               'stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>')
        n = len(self.recipes)
        desc = (f"{n} of Poppa's recipes — chicken, meats, desserts, cookies, salads, soups "
                "and more, gathered for the family.")
        return (
            head(SITE_TITLE, desc, "", BASE_URL + "/")
            + header("", "home")
            + f"""<main id="main" class="wrap">
  <div class="controls">
    <div class="search-box">
      {mag}
      <input id="search" type="search" placeholder="Search {n} recipes — try “chicken”, “cabbage”, “chocolate”…" aria-label="Search recipes by name, category, or ingredient" autocomplete="off">
    </div>
    <div class="category-bar" role="group" aria-label="Filter by category">
      {chips}
    </div>
    <p class="result-meta" id="result-meta" role="status" aria-live="polite" aria-atomic="true">{n} recipes in the collection</p>
  </div>
  <div class="recipe-grid" id="recipe-grid">
    {"".join(cards)}
    <p class="no-results" id="no-results" role="status" style="display:none">No recipes match — try another word.</p>
  </div>
</main>
"""
            + footer("", '<script src="assets/search.js"></script>\n')
        )

    def build_about(self):
        return (
            head(f"About Poppa — {SITE_TITLE}", "About Poppa — the cook behind the recipes.", "", BASE_URL + "/about.html")
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
    for again and again, the holidays, the kitchen he stood in.</p>
    <p style="text-align:center; font-style:italic; color:var(--red); margin-top:2rem;">“Recipes worth keeping.”</p>
  </article>
</main>
"""
            + footer("")
        )

    def build_404(self):
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

    def build(self):
        dup = [s for s, n in Counter(r["slug"] for r in self.recipes).items() if n > 1]
        if dup:
            raise SystemExit(f"Duplicate slugs: {dup}")
        rec_dir = SITE / "recipe"
        if rec_dir.exists():
            shutil.rmtree(rec_dir)
        rec_dir.mkdir(parents=True)

        canon = [f"{BASE_URL}/", f"{BASE_URL}/about.html"]
        for r in self.recipes:
            slug = r["slug"]
            if slug in self.primary_of:
                (rec_dir / f"{slug}.html").write_text(self.group_page(self.primary_of[slug]), encoding="utf-8")
                canon.append(f"{BASE_URL}/recipe/{slug}.html")
            elif slug in self.alt_of:
                g = self.alt_of[slug]
                (rec_dir / f"{slug}.html").write_text(self.alt_stub(slug, g["primary"], g["dish"]), encoding="utf-8")
            else:
                (rec_dir / f"{slug}.html").write_text(self.recipe_page(r), encoding="utf-8")
                canon.append(f"{BASE_URL}/recipe/{slug}.html")

        (SITE / "index.html").write_text(self.build_index(), encoding="utf-8")
        (SITE / "about.html").write_text(self.build_about(), encoding="utf-8")
        (SITE / "404.html").write_text(self.build_404(), encoding="utf-8")
        (SITE / "favicon.svg").write_text(favicon_svg(), encoding="utf-8")
        items = "\n".join(f"  <url><loc>{u}</loc></url>" for u in canon)
        (SITE / "sitemap.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{items}\n</urlset>\n', encoding="utf-8")
        (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n", encoding="utf-8")
        (SITE / ".nojekyll").write_text("", encoding="utf-8")

        n_alt = len(self.alt_of)
        print(f"Built: {len(self.recipes)-n_alt} cards from {len(self.recipes)} recipes | "
              f"{len(self.groups)} groups | enhanced: {len(self.enh)} | web photos: {len(self.img)}")


if __name__ == "__main__":
    Site().build()
