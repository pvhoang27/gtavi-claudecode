"""Source finder: GTA 6 videos you may legally reuse, in English, with no watermark.

1. Searches YouTube with the Creative Commons filter (relevance and newest) for several queries.
2. Keeps videos whose license really is "Creative Commons Attribution" (checked per video), whose
   language is English, 1 to 30 minutes long, and whose title has nothing banned (leaks, glitches...).
3. Watermark check: downloads a low-res copy, samples frames across the whole video and looks for
   static graphics (channel logos, burned-in text, facecams) that sit still while the game moves.
   Writes a contact sheet per video so a human (or Claude) can confirm by eye.

Writes sources.md (ranked, clean ones first) and sources.json.

usage: python sources.py [--query "gta 6 gameplay" ...] [--limit 25] [--top 8] [--min-views 5000]
"""
import argparse, json, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from common import JOBS, LANG, ROOT, run, save_json, tool, ytdlp_base, ytdlp_json

CC_RELEVANCE = "EgIwAQ%253D%253D"   # filter: Creative Commons
CC_NEWEST = "CAISAjAB"               # sort by upload date + Creative Commons
QUERIES = ["gta 6 gameplay", "gta 6", "gta 6 what happens if", "gta 6 no commentary"]
BAD_TITLE = re.compile(r"leak|glitch|play early|free download|crack|mod menu|afk|gta 5\b|gta v\b|concept|fan ?made|"
                       r"trailer reaction|unboxing|settings|how to play on pc|\bai\b|"
                       # talk / commentary / drama videos: not gameplay, usually a talking head
                       r"thoughts|opinion|outrage|woke|explained|reacts?\b|reaction|podcast|\bep\.? ?\d|review|drama|news", re.I)


def search(q, sp, limit):
    url = f"https://www.youtube.com/results?search_query={q.replace(' ', '+')}&sp={sp}"
    try:
        flat = ytdlp_json(url, ["--flat-playlist", "--playlist-end", str(limit)])
    except SystemExit:
        return []
    return [e["id"] for e in flat.get("entries", []) if e.get("id") and "/shorts/" not in (e.get("url") or "")]


def detail(vid):
    time.sleep(0.4)  # stay under YouTube's "confirm you're not a bot" threshold
    try:
        return ytdlp_json(f"https://www.youtube.com/watch?v={vid}", ["--skip-download"])
    except SystemExit:
        return None


def is_english(i):
    lang = (i.get("language") or "").lower()
    if lang:
        return lang.startswith(LANG)
    title = i.get("title") or ""
    return sum(c.isascii() for c in title) / max(1, len(title)) > 0.95  # no language tag: judge the title


def watermark_scan(i, d):
    """Return (score, boxes, sheet). score = share of the frame covered by static graphics outside the
    centre; boxes = their bounding boxes as fractions. Low score = clean."""
    import cv2
    low = d / "preview.mp4"
    if not low.exists():
        args = ytdlp_base() + ["-f", "bv*[height<=360][ext=mp4]/bv*[height<=480]/b[height<=480]", "-o", str(low)]
        if (i.get("duration") or 0) > 900:
            args += ["--download-sections", "*0-900"]
        run(args + [i["webpage_url"]], check=False)
    if not low.exists():
        return None, [], None
    cap = cv2.VideoCapture(str(low))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    frames, thumbs = [], []
    for k in range(30):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * (0.03 + 0.94 * k / 29)))
        ok, f = cap.read()
        if not ok:
            continue
        f = cv2.resize(f, (640, 360))
        frames.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
        if k % 3 == 0:
            thumbs.append(f)
    cap.release()
    if len(frames) < 8:
        return None, [], None
    st = np.stack(frames).astype(np.float32)
    edges = np.stack([cv2.Canny(f, 80, 200) > 0 for f in frames])
    persist = edges.mean(0)                     # how often a pixel is an edge
    still = st.std(0) < 10                      # how little it changes
    mask = ((persist > 0.7) & still).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    nlab, lab, stats, _ = cv2.connectedComponentsWithStats(mask)
    boxes, area = [], 0
    for j in range(1, nlab):
        x, y, w, h, a = stats[j]
        if a < 60 or w * h < 300:
            continue
        cx, cy = (x + w / 2) / 640, (y + h / 2) / 360
        if 0.3 < cx < 0.7 and 0.3 < cy < 0.7:   # crosshair / centre HUD, not a watermark
            continue
        boxes.append([round(x / 640, 3), round(y / 360, 3), round(w / 640, 3), round(h / 360, 3)])
        area += w * h
    sheet = d / "contact-sheet.jpg"
    tiles = thumbs[:9] + [np.zeros_like(thumbs[0])] * (9 - len(thumbs[:9]))
    grid = np.vstack([np.hstack(tiles[r * 3:r * 3 + 3]) for r in range(3)])
    over = cv2.cvtColor(mask * 255, cv2.COLOR_GRAY2BGR)
    for b in boxes:
        x, y, w, h = int(b[0] * 640), int(b[1] * 360), int(b[2] * 640), int(b[3] * 360)
        cv2.rectangle(over, (x, y), (x + w, y + h), (0, 0, 255), 2)
    cv2.imwrite(str(sheet), np.vstack([grid, np.hstack([over, cv2.cvtColor(frames[len(frames) // 2], cv2.COLOR_GRAY2BGR),
                                                         np.zeros_like(over)])]))
    return round(area / (640 * 360), 4), boxes, sheet


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", action="append", help="repeatable; default: a built-in list of GTA 6 queries")
    ap.add_argument("--limit", type=int, default=15, help="results per query and sort")
    ap.add_argument("--top", type=int, default=8, help="how many to watermark-scan (best by views per day)")
    ap.add_argument("--min-views", type=int, default=5000)
    ap.add_argument("--max-age-days", type=float, default=30)
    ap.add_argument("--out", default=str(ROOT / "sources.md"))
    a = ap.parse_args()
    ids = []
    for q in a.query or QUERIES:
        for sp in (CC_RELEVANCE, CC_NEWEST):
            ids += [x for x in search(q, sp, a.limit) if x not in ids]
    print(f"{len(ids)} Creative Commons search hits, checking each...")
    with ThreadPoolExecutor(3) as ex:
        infos = [i for i in ex.map(detail, ids) if i]
    now, rows = time.time(), []
    for i in infos:
        lic = i.get("license") or ""
        dur = i.get("duration") or 0
        age_d = max(0.1, (now - (i.get("timestamp") or now)) / 86400)
        why = []
        if "creative commons" not in lic.lower(): why.append(f"license: {lic or 'standard'}")
        if not is_english(i): why.append(f"language: {i.get('language')}")
        if not 60 <= dur <= 1800: why.append(f"length {dur}s")
        if BAD_TITLE.search(i.get("title") or ""): why.append("title")
        if (i.get("view_count") or 0) < a.min_views: why.append("views")
        if age_d > a.max_age_days: why.append("old")
        if i.get("is_live") or i.get("was_live"): why.append("stream")
        rows.append({"id": i["id"], "title": i.get("title"), "channel": i.get("channel") or i.get("uploader"),
                     "url": i.get("webpage_url"), "license": lic, "language": i.get("language"), "duration": dur,
                     "views": i.get("view_count") or 0, "views_per_day": round((i.get("view_count") or 0) / age_d),
                     "heatmap": bool(i.get("heatmap")), "skip": why, "info": i})
    ok = sorted([r for r in rows if not r["skip"]], key=lambda r: -r["views_per_day"])
    print(f"{len(ok)} pass license/language/length/title, scanning the top {min(a.top, len(ok))} for watermarks...")
    cache = JOBS / "_sources"
    for r in ok[:a.top]:
        d = cache / r["id"]; d.mkdir(parents=True, exist_ok=True)
        score, boxes, sheet = watermark_scan(r["info"], d)
        r.update(watermark_score=score, watermark_boxes=boxes, sheet=str(sheet) if sheet else None,
                 clean=score is not None and score < 0.004)
        print(f"  {r['id']} score {score} {'clean' if r['clean'] else 'CHECK'}  {r['title'][:60]}")
    for r in rows:
        r.pop("info", None)
    ranked = sorted(ok[:a.top], key=lambda r: (not r.get("clean"), -r["views_per_day"]))
    save_json(Path(a.out).with_suffix(".json"), {"checked": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "ranked": ranked,
                                                "rejected": [r for r in rows if r["skip"]]})
    md = [f"# Reusable sources ({time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())})", "",
          "Creative Commons Attribution (reuse allowed), English, watermark-scanned. Credit the creator in every post.", "",
          "| # | clean | wm score | views/day | min | channel | title | sheet |", "|---|---|---|---|---|---|---|---|"]
    for k, r in enumerate(ranked, 1):
        md.append(f"| {k} | {'yes' if r.get('clean') else 'CHECK'} | {r.get('watermark_score')} | {r['views_per_day']:,} | "
                  f"{r['duration'] / 60:.0f} | {r['channel']} | [{r['title'][:70]}]({r['url']}) | {r.get('sheet') or ''} |")
    Path(a.out).write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[4:]))


if __name__ == "__main__":
    main()
