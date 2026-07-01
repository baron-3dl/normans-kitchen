#!/usr/bin/env python3
"""
Build data/groups.json — collections of recipes that are versions of ONE dish,
folded together as alternates under a primary.

Sources of grouping:
  1. Same-title clusters — recipes whose titles normalize to the same dish
     (e.g. two "Chicken Cacciatore", "Swiss Steak" + "Swiss Steak I").
  2. CROSS_TITLE_GROUPS — curated groups where the SAME dish is filed under
     DIFFERENT names (e.g. "Meat Pie" + "French Meat Pie" = tourtière), and
     primaries chosen deliberately. Confirmed by an adversarial grouping pass.

Nothing here rewrites a recipe: each version keeps its exact ingredients and
directions. Grouping only changes how they are presented (one card per dish,
alternates selectable on the dish's page). Edit this file's curated section or
data/groups.json directly to change groupings/primaries, then rebuild.
"""
from __future__ import annotations
import json, re, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# --- curated cross-title groups (same dish, different names) ------------------
# members: any order; primary: the version to feature. Confirmed by the
# recipe-variation-grouping workflow + user preference.
CROSS_TITLE_GROUPS = [
    # Poppa's favourite tourtière is the well-spiced, browned "Meat Pie".
    {"dish": "Meat Pie", "primary": "meat-pie",
     "members": ["meat-pie", "french-meat-pie", "french-meat-pie-2"]},
    # --- confirmed by the recipe-variation-grouping workflow (same dish, ------
    #     different names). Delete any line to un-group that dish. -------------
    {"dish": "Cretons (Gorton)", "primary": "cretons-gorton",
     "members": ["cretons-gorton", "gorton"]},
    {"dish": "Chicken with Potato Crust", "primary": "crispy-chicken-w-potato-crust",
     "members": ["crispy-chicken-w-potato-crust", "chicken-with-potato-crust"]},
    {"dish": "Chicken Parmesan", "primary": "parmesan-chicken",
     "members": ["parmesan-chicken", "chicken-parmesan"]},
    {"dish": "Portuguese Oven-Roasted Potatoes", "primary": "oven-roasted-potatoes",
     "members": ["oven-roasted-potatoes", "oven-roasted"]},
    {"dish": "Pepper Steak", "primary": "slow-cooked-pepper-steak",
     "members": ["slow-cooked-pepper-steak", "savory-pepper-steak"]},
    {"dish": "Shredded Pork Sandwiches", "primary": "pork-bbq-sandwiches",
     "members": ["pork-bbq-sandwiches", "shredded-pork-sandwiches"]},
    {"dish": "Oven-Baked Rice", "primary": "baked-rice",
     "members": ["baked-rice", "oven-rice"]},
    {"dish": "Sex in a Pan", "primary": "chocolate-cheese-squares",
     "members": ["chocolate-cheese-squares", "sex-in-a-pan"]},
]

# override the auto-picked primary for a same-title cluster: {group_key: slug}
PRIMARY_OVERRIDES: dict[str, str] = {}


def base_title(t: str) -> str:
    """Drop a trailing version marker so the group's dish name reads cleanly
    ('Sauerkraut Salad II' -> 'Sauerkraut Salad', 'Bread Pudding I' -> ...)."""
    return re.sub(r"\s+(i{1,3}|\d+)$", "", t, flags=re.I).strip()


def norm(t: str) -> str:
    s = t.lower()
    s = re.sub(r"\(.*?\)", "", s)                 # drop parentheticals
    s = s.replace("&", "and")
    s = re.sub(r"\bw[-/]\s*", " with ", s)        # w- / w/ -> with
    s = s.replace("meat balls", "meatballs")
    s = re.sub(r"\b(i{1,3}|2|3|ii|iii)\b", " ", s)  # version suffixes
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def richness(r: dict) -> int:
    return (len([i for i in r["ingredients"] if "item" in i])
            + len(r["steps"]) + len(r["notes"]) + (3 if r.get("image") else 0))


def order_members(slugs, primary, by_slug):
    rest = sorted((s for s in slugs if s != primary),
                  key=lambda s: -richness(by_slug[s]))
    return [primary] + rest


def main():
    recipes = json.loads((DATA / "recipes.json").read_text(encoding="utf-8"))
    by_slug = {r["slug"]: r for r in recipes}

    groups = []
    claimed: set[str] = set()

    # 1. curated cross-title groups take precedence -------------------------
    for g in CROSS_TITLE_GROUPS:
        members = [m for m in g["members"] if m in by_slug and m not in claimed]
        if len(members) < 2:
            continue
        primary = g["primary"] if g["primary"] in members else members[0]
        members = order_members(members, primary, by_slug)
        groups.append({
            "slug": primary,
            "dish": g.get("dish") or by_slug[primary]["title"],
            "primary": primary,
            "members": members,
            "category": by_slug[primary]["category"],
        })
        claimed.update(members)

    # 2. same-title clusters ------------------------------------------------
    clusters = collections.defaultdict(list)
    for r in recipes:
        clusters[norm(r["title"])].append(r)

    for key, recs in sorted(clusters.items()):
        members = [r["slug"] for r in recs if r["slug"] not in claimed]
        if len(members) < 2:
            continue
        primary = PRIMARY_OVERRIDES.get(key)
        if primary not in members:
            primary = max(members, key=lambda s: richness(by_slug[s]))
        members = order_members(members, primary, by_slug)
        groups.append({
            "slug": primary,
            "dish": base_title(by_slug[primary]["title"]),
            "primary": primary,
            "members": members,
            "category": by_slug[primary]["category"],
        })
        claimed.update(members)

    groups.sort(key=lambda g: g["dish"].lower())
    (DATA / "groups.json").write_text(
        json.dumps(groups, ensure_ascii=False, indent=2), encoding="utf-8")

    folded = sum(len(g["members"]) for g in groups)
    print(f"{len(groups)} dish groups covering {folded} recipes "
          f"({folded - len(groups)} alternates folded under primaries)")
    for g in groups:
        alts = ", ".join(by_slug[m]["title"] for m in g["members"][1:])
        print(f"  {g['dish']}  ←  {alts}")


if __name__ == "__main__":
    main()
