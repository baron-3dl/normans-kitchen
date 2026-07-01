#!/usr/bin/env python3
"""
Parse Poppa's Living Cookbook HTML exports into clean structured JSON.

Input : poppas-source/**/*.htm   (iso-8859-1 encoded, table-based markup)
Output: data/recipes.json        (utf-8, one array of recipe objects)
        site/images/<slug>.jpg    (referenced photos copied + renamed)

A "recipe" is any file with at least one real ingredient or one direction step.
Commodity nutrition-fact files (Salt, Sugars, Vinegar, ...) and empty stubs have
neither and are dropped. Exact duplicates (same normalized title + ingredients)
collapse to the richer record.

Parser hardening (informed by an adversarial field-by-field audit of all 354
recipes against source): mixed-case-shouty titles are normalized; categories come
from the source folder before any title keyword; two-column unit/item splits are
recombined; layout junk (XXX spacers, ALL-CAPS section dividers, cookbook page
references, stray instructions) is filtered; soft hyphens are stripped; servings
are recovered from the "Yield:/Serves/Makes" tail of the directions.
"""
from __future__ import annotations
import os, re, json, shutil, hashlib
from pathlib import Path
import lxml.html

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "poppas-source"
DATA = ROOT / "data"
IMG_OUT = ROOT / "site" / "images"

# ---------------------------------------------------------------- categories
CATEGORIES = [
    "Chicken & Poultry", "Beef", "Pork", "Meats", "Fish & Seafood", "Pasta",
    "Rice", "Potatoes", "Vegetables", "Salads & Dressings", "Soups & Chowders",
    "Desserts, Pies & Cakes", "Cookies & Bars", "Sauces & Seasonings",
    "Kids' Corner", "Miscellaneous",
]

BEEF_KW = ("beef", "steak", "hamburger", "brisket", "meatball", "meat ball",
           "meatloaf", "meat loaf", "sukiyaki", "lombardi", "cottage pie",
           "sausage", "chourico", "ragout", "sloppy")
PORK_KW = ("pork", "bacon", "chop", "cretons", "creton", "gorton", "cacoila",
           "ham ", "ham,", "shoulder", "tenderloin", "hot dog", "frank")
SEAFOOD_KW = ("shrimp", "crab", "lobster", "clam", "scallop", "salmon",
              "tilapia", "flounder", "sole", "tuna", "cod", "haddock",
              "seafood", "oyster", "mussel")
SOUP_KW = ("soup", "chowder", "bisque", "pistou")
SALAD_KW = ("salad", "slaw", "dressing", "vinaigrette")

# Many recipes were mis-filed in the source folder tree, so their folder-derived
# category is wrong for their actual content. Keyed by source path. Confirmed by
# an adversarial category-accuracy audit of all 353 recipes (each mismatch
# independently verified). Mixed beef+pork dishes intentionally live in "Meats".
CATEGORY_OVERRIDES = {
    # from the earlier parse audit
    "Cookies/Cookies/Hot Crab Dip.htm": "Fish & Seafood",   # savory crab dip, not a cookie
    "pics/Chocolate Cheese Squares.htm": "Cookies & Bars",  # dessert bar, not "misc"
    "SSSSSSSSS/Shrimp Creole.htm": "Fish & Seafood",         # shrimp main dish
    # from the category-accuracy audit — recipes filed by folder, not content
    "Meats/Beef/Fish and Chips.htm": "Fish & Seafood",      # battered fish, no beef
    "Meats/Beef/Mock Lobster Casserole.htm": "Fish & Seafood",  # haddock
    "Meats/Beef/Stuffed Lobster Supreme.htm": "Fish & Seafood",  # lobster tails
    "Meats/Beef/Chourico Stewed w-Cabbage.htm": "Pork",     # chourico (pork sausage)
    "Meats/Beef/Sausage and Pepper Ragout.htm": "Pork",     # sausage
    "Meats/Beef/Leg of Lamb w-Beans.htm": "Meats",          # lamb -> other meats
    "Meats/Beef/French Meat Pie.htm": "Meats",              # beef+pork tourtière
    "Meats/Beef/Swedish Meat Balls.htm": "Meats",           # mixed beef+pork
    "Meats/Swedish Meatballs.htm": "Meats",                 # mixed beef+pork
    "Meats/Beef/Best Baked Beans.htm": "Vegetables",        # meatless bean side
    "Meats/Spicy Marinated Eye Round.htm": "Beef",          # eye round = beef
    "Meats/Italian Meat Rolls.htm": "Beef",                 # ground beef loaves
    "Meats/Pork/Barbeque Sauce.htm": "Sauces & Seasonings",   # standalone sauce
    "Meats/Pork/Molasses BBQ Sauce.htm": "Sauces & Seasonings",  # standalone sauce
    "Miscellaneous/CHILI.htm": "Beef",                      # beef chili
    "Miscellaneous/MANHATTAN CLAM CHOWDER.htm": "Soups & Chowders",  # it's a chowder
    "Rice/Rice/Special Rice Dessert (make a day ahead).htm": "Desserts, Pies & Cakes",
    "SSSSSSSSS/SaladDressings/Honey and Wild Rice Dressing.htm": "Rice",  # rice stuffing, not a salad dressing
    "Desserts/Chocolate Refrigerator Bars.htm": "Cookies & Bars",
    "Desserts/PiesCakes/Heavenly Hash.htm": "Cookies & Bars",
    "Cookies/Cookies/Fat Free Frosting.htm": "Desserts, Pies & Cakes",
    "Cookies/Cookies/Grape Nut Pudding.htm": "Desserts, Pies & Cakes",
    "Cookies/Cookies/Devil Dog Filling.htm": "Desserts, Pies & Cakes",
    "Cookies/Cookies/Graham Cracker Retirement Puffs.htm": "Desserts, Pies & Cakes",
    "Cookies/Cookies/Dark Chocolate Sauce.htm": "Sauces & Seasonings",  # a dessert sauce, but a sauce
}


# Hand-dropped family photos: source path -> image path already placed under site/.
IMAGE_OVERRIDES = {
    "Meats/Meat Pie.htm": "images/meat-pie.jpg",
}


def categorize(rel_parts: list[str], title: str) -> str:
    p = [s.lower() for s in rel_parts]
    joined = "/".join(p)
    t = title.lower()

    def any_in(kws, hay):
        return any(k in hay for k in kws)

    # 1. strong folder signals ----------------------------------------------
    if "chicken" in joined:
        return "Chicken & Poultry"
    if "fish" in joined:
        return "Fish & Seafood"
    if "cookies" in joined:
        return "Cookies & Bars"
    if "desserts" in joined or "piescakes" in joined:
        return "Desserts, Pies & Cakes"
    if "pasta" in joined:
        return "Pasta"
    if p and p[0] == "rice":
        return "Rice"
    if p and p[0] == "potatoes":
        return "Potatoes"
    if "spices" in joined:
        return "Sauces & Seasonings"
    if "kids" in joined:
        return "Kids' Corner"
    if "saladdressings" in joined:
        return "Salads & Dressings"
    if "soup" in joined:                       # SSSSSSSSS/Soup folder
        return "Soups & Chowders"

    # 2. meats tree — folder decides BEFORE any title keyword ---------------
    if "beef" in joined:
        return "Beef"
    if "pork" in joined:
        return "Pork"
    if p and p[0] == "meats":
        if "veal" in t or "lamb" in t:
            return "Meats"
        if any_in(BEEF_KW, t):
            return "Beef"
        if any_in(PORK_KW, t):
            return "Pork"
        return "Meats"

    # 3. vegetables tree + stray onion folder -------------------------------
    if "vegetables" in joined or "veggies" in joined or (p and p[0] == "oooooo"):
        return "Vegetables"

    # 4. title-keyword fallbacks (SSSSSSSSS root, single-letter folders, misc)
    if "veal" in t or "lamb" in t:
        return "Meats"
    if any_in(SEAFOOD_KW, t):
        return "Fish & Seafood"
    if any_in(SALAD_KW, t):
        return "Salads & Dressings"
    if any_in(SOUP_KW, t):
        return "Soups & Chowders"
    if any_in(PORK_KW, t):
        return "Pork"
    if any_in(BEEF_KW, t):
        return "Beef"

    # 5. miscellaneous grab-bag ---------------------------------------------
    if "miscellaneous" in joined:
        if any_in(("sauce", "barbecue", "bbq", "creole", "seasoning"), t):
            return "Sauces & Seasonings"
    return "Miscellaneous"


# ---------------------------------------------------------------- title case
SMALL = {"a", "an", "and", "as", "at", "but", "by", "for", "in", "of", "on",
         "or", "the", "to", "with", "w", "au", "de", "la", "le", "n"}


def smart_title(s: str) -> str:
    """Title-case a shouty title. Fires when the title is predominantly
    uppercase (handles UPPERCASE-main + lowercase-tail like
    'CHICKEN IN WINE in no time'); leaves normal mixed-case titles alone."""
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return s.strip()
    upper_ratio = sum(c.isupper() for c in letters) / len(letters)
    if upper_ratio < 0.55:
        return s.strip()

    def cap_word(w, edge):
        low = w.lower()
        if low in SMALL and not edge:
            return low
        return "-".join(seg[:1].upper() + seg[1:].lower() if seg else seg
                        for seg in low.split("-"))

    words = s.split()
    out = [cap_word(w, i == 0 or i == len(words) - 1) for i, w in enumerate(words)]
    return " ".join(out).strip()


def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[''`]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-") or "recipe"


def clean_text(s: str) -> str:
    s = s.replace("\xa0", " ")
    for ch in ("\xad", "​", "‌", "‍", "﻿"):  # soft hyphen / zero-width
        s = s.replace(ch, "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\s*\n\s*", " ", s)
    return s.strip()


# ------------------------------------------------------- ingredient cleaning
UNITS = {"tbs", "tbsp", "tbl", "tblsp", "tsp", "teaspoon", "teaspoons",
         "tablespoon", "tablespoons", "cup", "cups", "oz", "ounce", "ounces",
         "lb", "lbs", "pound", "pounds", "clove", "cloves", "can", "cans",
         "pkg", "pkgs", "package", "packages", "qt", "pt", "gal", "stick",
         "sticks", "pinch", "dash", "quart", "quarts", "pint", "pints"}
DIVIDER_WORDS = {"SAUCE", "FILLING", "TOPPING", "CRUST", "DRESSING", "GLAZE",
                 "MARINADE", "GARNISH", "BATTER", "DOUGH", "RUB", "ICING",
                 "FROSTING", "CAKE", "COATING", "STREUSEL"}
DROP_ITEMS = {"blend well with mixer"}
PLACEHOLDER = re.compile(r"^[xX]{4,}$")
PAGE_REF = re.compile(r"^(?:pag\w*|pg\.?|p\.?)\s*\d+", re.I)  # "Page 66", "Pagee 66" (source typo)


def clean_ingredients(raw: list[dict]) -> tuple[list[dict], list[str]]:
    notes_out: list[str] = []
    tmp: list[dict] = []
    for ing in raw:
        if "heading" in ing:
            tmp.append(ing)
            continue
        item = ing.get("item", "").strip()
        qty = ing.get("qty", "").strip()
        if not item:
            continue
        if PLACEHOLDER.match(item.replace(" ", "")):        # XXXXX spacer rows
            continue
        if not qty and PAGE_REF.match(item):                # "Pagee 66 Creative Cooking"
            notes_out.append(item)
            continue
        if item.lower() in DROP_ITEMS:                      # stray instruction
            continue
        if not qty and item.isupper():                      # ALL-CAPS section divider
            first = item.split()[0] if item.split() else ""
            if "INGREDIENT" in item or item in DIVIDER_WORDS or first in DIVIDER_WORDS:
                tmp.append({"heading": item.title()})
                continue
        tmp.append({"qty": qty, "item": item})

    # recombine two-column splits where a bare unit word landed in its own cell,
    # separated from its ingredient (next row has no quantity). Two shapes:
    #   {qty:'2', item:'tbs'} + {item:'lemon juice'}  -> {qty:'2 tbs', item:'lemon juice'}
    #   {item:'cloves'}       + {item:'garlic'}        -> {item:'cloves garlic'}  (count lost in source)
    merged: list[dict] = []
    i = 0
    while i < len(tmp):
        cur = tmp[i]
        nxt = tmp[i + 1] if i + 1 < len(tmp) else None
        if ("item" in cur
                and cur["item"].strip().lower().rstrip(".") in UNITS
                and nxt is not None and "item" in nxt and not nxt.get("qty")):
            q = cur.get("qty", "").strip()
            if q:
                merged.append({"qty": f'{q} {cur["item"]}', "item": nxt["item"]})
            else:
                merged.append({"qty": "", "item": f'{cur["item"]} {nxt["item"]}'})
            i += 2
        else:
            merged.append(cur)
            i += 1
    return merged, notes_out


# --------------------------------------------------------- servings recovery
def derive_servings(steps: list[str], existing: str) -> tuple[str, list[str]]:
    if existing or not steps:
        return existing, steps
    text = " ".join(steps)
    serv = ""
    for pat, pre in ((r"\bYield:?\s*([0-9][^.\n]{0,30})", "Makes "),
                     (r"\bMakes\s+([0-9][^.\n]{0,30})", "Makes "),
                     (r"\bServes\s+([0-9][^.\n]{0,25})", "Serves ")):
        m = re.search(pat, text, re.I)
        if m:
            serv = pre + m.group(1).strip()
            break
    # a trailing "Yield: N ..." is a label, redundant with the servings line
    steps = list(steps)
    steps[-1] = re.sub(r"\s*Yield:?\s*[0-9][^.\n]*\.?\s*$", "", steps[-1], flags=re.I).strip()
    if not steps[-1]:
        steps = steps[:-1]
    return serv, steps


def cell_class(el) -> str:
    return (el.get("class") or "").strip()


# ---------------------------------------------------------------- image index
def build_image_index() -> dict[str, Path]:
    idx: dict[str, Path] = {}
    for p in SRC.rglob("*"):
        if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif") and "__MACOSX" not in str(p):
            idx.setdefault(p.name.lower(), p)
    return idx


IMG_INDEX = build_image_index()


def parse_file(path: Path) -> dict | None:
    raw = path.read_text(encoding="latin-1", errors="replace")
    doc = lxml.html.fromstring(raw)

    # ---- title
    title_el = doc.xpath('//td[contains(@class,"title") or contains(@class,"page_heading")]')
    title = clean_text(title_el[0].text_content()) if title_el else path.stem
    title = smart_title(title)

    # ---- ingredients (innermost ingredient tables only; wrappers nest) -----
    raw_ingredients = []
    for tbl in doc.xpath('//table[contains(@class,"ingredient") and '
                         'not(.//table[contains(@class,"ingredient")])]'):
        for tr in tbl.xpath('.//tr'):
            head = tr.xpath('./td[contains(@class,"ingredient_heading")]')
            if head:
                h = clean_text(head[0].text_content())
                if h:
                    raw_ingredients.append({"heading": h})
                continue
            item_cell = tr.xpath('./td[@width="93%"]')
            if not item_cell:
                continue
            item = clean_text(item_cell[0].text_content())
            if not item:
                continue
            qty_cell = tr.xpath('./td[@width="5%"]')
            qty = clean_text(qty_cell[0].text_content()) if qty_cell else ""
            raw_ingredients.append({"qty": qty, "item": item})

    ingredients, page_notes = clean_ingredients(raw_ingredients)

    # ---- directions (leaf procedure cells, in document order) --------------
    steps = []
    for td in doc.xpath('//td[normalize-space(@class)="procedure"]'):
        if td.xpath('.//td'):
            continue
        txt = clean_text(td.text_content())
        if txt:
            steps.append(txt)

    # ---- notes / source (mostly Living Cookbook metadata; keep the real bits)
    def collect(cls):
        out = []
        for td in doc.xpath(f'//td[normalize-space(@class)="{cls}"]'):
            if td.xpath('.//td'):
                continue
            txt = clean_text(td.text_content())
            if txt:
                out.append(txt)
        return out

    BOILER = ("inventory item", "more recipes", "percent daily", "serving size",
              "nutrition source", "daily value", "calories from", "usda",
              "other serving sizes")

    def is_boiler(s):
        low = s.lower()
        return any(b in low for b in BOILER)

    source = ""
    notes = list(page_notes)
    for n in collect("notes"):
        low = n.lower()
        if low.startswith("source:"):
            source = n.split(":", 1)[1].strip() or n
        elif not is_boiler(n):
            notes.append(n)
    for t in collect("tips"):
        if len(t) > 15 and " " in t and not is_boiler(t) and not t.lower().startswith("source:"):
            notes.append(t)

    servings_list = collect("servings")
    servings = servings_list[0] if servings_list else ""
    servings, steps = derive_servings(steps, servings)

    # ---- drop commodity nutrition files and empty stubs --------------------
    real_ings = [i for i in ingredients if "item" in i]
    if not real_ings and not steps:
        return None

    # ---- image -------------------------------------------------------------
    image = None
    m = re.search(r'src="[^"]*?([^"/]+\.(?:jpe?g|png|gif))"', raw, re.I)
    if m:
        src = IMG_INDEX.get(m.group(1).lower())
        if src:
            image = src

    rel_parts = path.relative_to(SRC).parts[:-1]
    source_file = str(path.relative_to(SRC))
    category = CATEGORY_OVERRIDES.get(source_file, categorize(list(rel_parts), title))

    return {
        "title": title,
        "category": category,
        "source_file": source_file,
        "source_folder": "/".join(rel_parts),
        "servings": servings,
        "ingredients": ingredients,
        "steps": steps,
        "notes": notes,
        "source": source,
        "_image_src": str(image) if image else None,
        "_image_override": IMAGE_OVERRIDES.get(source_file),
    }


def ingredient_sig(rec) -> str:
    items = [i.get("item", "") for i in rec["ingredients"] if "item" in i]
    return hashlib.md5("|".join(items).lower().encode()).hexdigest()


def richness(rec) -> int:
    return (len(rec["steps"]) + len(rec["ingredients"]) + len(rec["notes"]) * 2
            + (5 if rec["_image_src"] else 0))


def main():
    files = sorted(p for p in SRC.rglob("*.htm") if "__MACOSX" not in str(p))
    parsed = []
    for f in files:
        try:
            rec = parse_file(f)
        except Exception as e:
            print(f"  ! parse error {f.name}: {e}")
            rec = None
        if rec:
            parsed.append(rec)

    # ---- dedupe exact duplicates ------------------------------------------
    seen: dict[tuple, dict] = {}
    for rec in parsed:
        key = (slugify(rec["title"]), ingredient_sig(rec))
        if key not in seen or richness(rec) > richness(seen[key]):
            seen[key] = rec
    recipes = list(seen.values())

    recipes.sort(key=lambda r: (CATEGORIES.index(r["category"]) if r["category"] in CATEGORIES else 99,
                                r["title"].lower()))
    used = set()
    IMG_OUT.mkdir(parents=True, exist_ok=True)
    for rec in recipes:
        base = slugify(rec["title"])
        slug, n = base, 2
        while slug in used:
            slug = f"{base}-{n}"; n += 1
        used.add(slug)
        rec["slug"] = slug
        if rec.get("_image_override"):          # a family photo dropped in by hand
            rec["image"] = rec["_image_override"]
        elif rec["_image_src"]:
            src = Path(rec["_image_src"])
            ext = ".jpg" if src.suffix.lower() == ".jpeg" else src.suffix.lower()
            shutil.copyfile(src, IMG_OUT / f"{slug}{ext}")
            rec["image"] = f"images/{slug}{ext}"
        else:
            rec["image"] = None
        rec.pop("_image_src", None)
        rec.pop("_image_override", None)

    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "recipes.json").write_text(
        json.dumps(recipes, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- report ------------------------------------------------------------
    from collections import Counter
    cats = Counter(r["category"] for r in recipes)
    print(f"\nParsed {len(files)} files -> {len(parsed)} recipes -> "
          f"{len(recipes)} after dedupe ({len(parsed)-len(recipes)} dupes removed)")
    print(f"With photos: {sum(1 for r in recipes if r['image'])} | "
          f"with servings: {sum(1 for r in recipes if r['servings'])}")
    print("By category:")
    for c in CATEGORIES:
        if cats.get(c):
            print(f"  {cats[c]:>4}  {c}")
    for c in set(cats) - set(CATEGORIES):
        print(f"  {cats[c]:>4}  [UNMAPPED] {c}")


if __name__ == "__main__":
    main()
