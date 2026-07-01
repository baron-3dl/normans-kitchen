# Poppa's Recipes

A family website for Poppa's recipe collection — **354 recipes** gathered over the years,
now a searchable, print-friendly keepsake. Built as a plain static site so it will keep
working for a very long time, with no build step required to view it.

**Live site:** https://baron-3dl.github.io/normans-kitchen/

<p align="center"><em>“recipes worth keeping”</em></p>

## What's here

```
site/                 The website itself (this is what gets published)
  index.html          Home — instant search + browse by category
  recipe/<slug>.html  One page per recipe (print-friendly)
  about.html          About Poppa (placeholder — add his story & photo)
  assets/             style.css (vintage-cookbook theme) + search.js
  images/             Recipe photos
data/recipes.json     All recipes as structured data (the single source of truth)
poppas-source/        The original "Living Cookbook" HTML exports (kept for reproducibility)
scripts/
  parse_recipes.py    poppas-source/*.htm  ->  data/recipes.json (+ copies photos)
  build_site.py       data/recipes.json    ->  the pages in site/
  test_search.mjs     Playwright functional test for the search/filter UI
```

## Rebuilding after a change

The site is generated from the source recipes. To regenerate everything:

```bash
python3 scripts/parse_recipes.py   # re-parse the HTML sources -> data/recipes.json
python3 scripts/build_site.py      # regenerate all pages in site/
```

`parse_recipes.py` needs `lxml` (`pip install lxml`). `build_site.py` uses only the
standard library.

### Editing recipes by hand

`data/recipes.json` is the source of truth. Edit a recipe there (fix a typo, add a
note), then run `python3 scripts/build_site.py` to rebuild the pages.

## The About page

`site/about.html` ships with placeholder text. Replace it with Poppa's real story, and
drop a photo at `site/images/poppa.jpg` (then point the photo frame in `about.html` at it).

## Testing

```bash
npm install playwright          # one-time (dev only; the site itself needs nothing)
python3 -m http.server 8765 --directory site &
node scripts/test_search.mjs    # exercises search, category filter, deep links
```

## Publishing

Any push to `main` republishes via GitHub Actions (`.github/workflows/pages.yml`),
which serves the `site/` folder on GitHub Pages.

---

*Made with ♥ for the family.*
