#!/usr/bin/env python3
"""Fetch one Ganjoor category (a whole book) poem by poem through the public API.

Polite and resumable: one request a second, a user agent naming the project,
every poem saved as its own JSON file, so a time-boxed run can be repeated until
nothing is left. A category with sub-categories is walked recursively.

Usage:
    ganjoor_fetch.py --url /moulavi/masnavi --out DIR [--max-seconds 540]

Writes DIR/tree.json (the category tree with poem ids, in order) and
DIR/poems/<id>.json. Prints how many poems are fetched and how many remain.
"""

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

UA = "TesseraeProject/6 (corpus import; https://tesserae.caset.buffalo.edu)"
API = "https://api.ganjoor.net/api/ganjoor"
_last = [0.0]


def get(url):
    for attempt in range(5):
        wait = 1.05 - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return json.loads(urllib.request.urlopen(req, timeout=40).read())
        except Exception as exc:  # network error or 5xx: back off and retry
            print("retry", attempt, url[-60:], exc, file=sys.stderr)
            time.sleep(3 * (attempt + 1))
    raise SystemExit("giving up on " + url)


def walk(cat_id, title, url):
    d = get(f"{API}/cat/{cat_id}?poems=true")["cat"]
    node = {
        "id": cat_id,
        "title": title,
        "url": url,
        "poems": [
            {"id": p["id"], "title": p["title"], "slug": p["urlSlug"]}
            for p in d.get("poems") or []
        ],
        "children": [],
    }
    for ch in d.get("children") or []:
        node["children"].append(walk(ch["id"], ch["title"], ch["fullUrl"]))
    return node


def all_poems(node):
    for p in node["poems"]:
        yield p
    for ch in node["children"]:
        yield from all_poems(ch)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-seconds", type=int, default=540)
    a = ap.parse_args()
    t0 = time.time()
    os.makedirs(os.path.join(a.out, "poems"), exist_ok=True)
    tree_path = os.path.join(a.out, "tree.json")
    if os.path.exists(tree_path):
        tree = json.load(open(tree_path, encoding="utf-8"))
    else:
        root = get(f"{API}/cat?url=" + urllib.parse.quote(a.url))["cat"]
        tree = walk(root["id"], root["title"], root["fullUrl"])
        json.dump(tree, open(tree_path, "w", encoding="utf-8"), ensure_ascii=False)
    todo = [
        p
        for p in all_poems(tree)
        if not os.path.exists(os.path.join(a.out, "poems", f"{p['id']}.json"))
    ]
    total = sum(1 for _ in all_poems(tree))
    for p in todo:
        if time.time() - t0 > a.max_seconds:
            break
        d = get(
            f"{API}/poem/{p['id']}?catInfo=false&catPoems=false&rhymes=false"
            "&recitations=false&images=false&songs=false&comments=false"
            "&verseDetails=true&navigation=false"
        )
        tmp = os.path.join(a.out, "poems", f"{p['id']}.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.rename(tmp, os.path.join(a.out, "poems", f"{p['id']}.json"))
    left = sum(
        1
        for p in all_poems(tree)
        if not os.path.exists(os.path.join(a.out, "poems", f"{p['id']}.json"))
    )
    print(f"poems {total} remaining {left}")
    return 0 if left == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
