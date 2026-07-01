#!/usr/bin/env python3
"""
Source a freely-licensed (CC) photo for each recipe from Openverse.

Only images under clearly reusable licences (CC0, PDM, CC-BY, CC-BY-SA) are
kept, and only when the result is actually relevant to the dish (token overlap),
so we show a good match or nothing — never a random photo. Downloads the
~600px Openverse thumbnail into site/images/web/<slug>.jpg and records
attribution in data/images.json (credit is shown on the enhanced view; CC-BY
requires it). Idempotent: skips recipes already fetched.

Enhanced-mode only — Poppa's 23 original photos are untouched.
"""
from __future__ import annotations
import json, re, time, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECIPES = ROOT / "data" / "recipes.json"
OUT_DIR = ROOT / "site" / "images" / "web"
OUT_JSON = ROOT / "data" / "images.json"
API = "https://api.openverse.org/v1/images/"
UA = "normans-kitchen/1.0 (personal family recipe site)"
OK_LICENSES = {"cc0", "pdm", "by", "by-sa"}  # commercially reusable, with credit
STOP = {"and", "with", "the", "of", "in", "a", "an", "for", "or", "to", "on",
        "poppas", "poppa", "style", "recipe", "make", "ahead", "easy", "no",
        "old", "best", "good", "homemade", "family"}


def tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", s.lower()) if len(w) >= 4 and w not in STOP}


def get(url: str, timeout=25) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def search(query: str):
    q = urllib.parse.urlencode({
        "q": query, "page_size": 8, "license": ",".join(OK_LICENSES),
        "mature": "false",
    })
    for attempt in range(3):
        try:
            data = json.loads(get(f"{API}?{q}"))
            return data.get("results", [])
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(3 * (attempt + 1)); continue
            return []
        except Exception:
            time.sleep(1); continue
    return []


def relevant(results, want: set[str]):
    """All results whose title/tags overlap the dish name and have a usable licence."""
    out = []
    for r in results:
        if (r.get("license") or "").lower() not in OK_LICENSES:
            continue
        hay = tokens(r.get("title") or "")
        for t in (r.get("tags") or []):
            hay |= tokens(t.get("name", "") if isinstance(t, dict) else str(t))
        if want & hay:
            out.append(r)
    return out


def save_web(path, data, maxw=900):
    """Downscale to a sane web size and save as optimized JPEG. Returns True on success."""
    try:
        from PIL import Image
        import io
        im = Image.open(io.BytesIO(data)).convert("RGB")
        if im.width > maxw:
            im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
        im.save(path, "JPEG", quality=82, optimize=True)
        return True
    except Exception:
        try:
            path.write_bytes(data)  # PIL unavailable — keep the original
            return True
        except Exception:
            return False


def download_image(r):
    """Try the Openverse thumbnail then the original url; return image bytes or None."""
    for src in (r.get("thumbnail"), r.get("url")):
        if not src:
            continue
        try:
            img = get(src)
            if img[:3] == b"\xff\xd8\xff" or img[:8] == b"\x89PNG\r\n\x1a\n":
                return img
        except Exception:
            continue
    return None


def credit(r) -> dict:
    lic = (r.get("license") or "").upper()
    ver = r.get("license_version") or ""
    label = "CC0" if lic == "CC0" else ("Public Domain" if lic == "PDM" else f"CC {lic} {ver}".strip())
    return {
        "creator": r.get("creator") or "Unknown",
        "license": label,
        "license_url": r.get("license_url") or "",
        "source": r.get("foreign_landing_url") or r.get("url") or "",
        "title": (r.get("title") or "").strip()[:120],
    }


def main():
    recipes = json.loads(RECIPES.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    store = json.loads(OUT_JSON.read_text(encoding="utf-8")) if OUT_JSON.exists() else {}

    todo = [r for r in recipes if r["slug"] not in store]
    print(f"{len(recipes)} recipes, {len(store)} already sourced, {len(todo)} to try", flush=True)
    got = 0
    for n, r in enumerate(todo, 1):
        slug, title = r["slug"], r["title"]
        want = tokens(title) or tokens(r["category"])
        cands = relevant(search(title), want)
        if not cands:                     # retry with a simplified dish-type query
            simple = re.sub(r"\(.*?\)", "", title)
            simple = " ".join(w for w in simple.split() if w.lower() not in STOP)
            if simple and simple.lower() != title.lower():
                cands = relevant(search(simple), want)
        for hit in cands[:4]:             # try candidates until one actually downloads
            img = download_image(hit)
            if img and save_web(OUT_DIR / f"{slug}.jpg", img):
                store[slug] = {"file": f"images/web/{slug}.jpg", **credit(hit)}
                got += 1
                break
        if n % 20 == 0:
            OUT_JSON.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  {n}/{len(todo)} tried, {got} new images", flush=True)
        time.sleep(0.4)

    OUT_JSON.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Done. {len(store)} recipes now have a sourced image ({got} new).", flush=True)


if __name__ == "__main__":
    main()
