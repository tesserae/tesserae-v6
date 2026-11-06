#!/usr/bin/env python3
"""Fetch a Wikisource work and its subpages as rendered HTML (one request a second).

Usage:
    wikisource_fetch.py LANG "Main title" OUT_DIR
LANG is fa or ur. Lists every page whose title starts with "Main title" (the main
page and its subpages), saves OUT_DIR/pages.json (titles in site order) and one
OUT_DIR/html/<n>.json per page with the revision id and the rendered HTML.
Resumable: pages already saved are skipped.
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request

UA = "TesseraeProject/6 (corpus import; https://tesserae.caset.buffalo.edu)"
_last = [0.0]


def api(lang, **params):
    params["format"] = "json"
    url = f"https://{lang}.wikisource.org/w/api.php?" + urllib.parse.urlencode(params)
    for attempt in range(5):
        wait = 1.05 - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return json.loads(urllib.request.urlopen(req, timeout=60).read())
        except Exception as exc:
            print("retry", attempt, exc, file=sys.stderr)
            time.sleep(3 * (attempt + 1))
    raise SystemExit("giving up")


def main():
    lang, title, out = sys.argv[1:4]
    os.makedirs(os.path.join(out, "html"), exist_ok=True)
    pj = os.path.join(out, "pages.json")
    if os.path.exists(pj):
        titles = json.load(open(pj, encoding="utf-8"))
    else:
        titles = []
        cont = {}
        while True:
            d = api(
                lang, action="query", list="allpages", apprefix=title,
                aplimit=500, **cont
            )
            titles += [p["title"] for p in d["query"]["allpages"]]
            if "continue" not in d:
                break
            cont = d["continue"]
        titles = [t for t in titles if t == title or t.startswith(title + "/")]
        json.dump(titles, open(pj, "w", encoding="utf-8"), ensure_ascii=False)
    for n, t in enumerate(titles):
        f = os.path.join(out, "html", f"{n:03d}.json")
        if os.path.exists(f):
            continue
        d = api(lang, action="parse", page=t, prop="text|revid", disablelimitreport=1)
        if "parse" not in d:
            print("missing", t)
            continue
        json.dump(
            {"title": t, "revid": d["parse"]["revid"], "html": d["parse"]["text"]["*"]},
            open(f, "w", encoding="utf-8"),
            ensure_ascii=False,
        )
    print(title, len(titles), "pages")


if __name__ == "__main__":
    main()
