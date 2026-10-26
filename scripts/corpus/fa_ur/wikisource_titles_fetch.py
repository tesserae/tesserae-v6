#!/usr/bin/env python3
"""Fetch a given list of Wikisource pages as rendered HTML (one request a second).

Usage:
    wikisource_titles_fetch.py LANG TITLES_JSON OUT_DIR
TITLES_JSON is a JSON list of page titles. Saves OUT_DIR/html/<n>.json (n is the
position in the list) with the title, revision id and rendered HTML, and
OUT_DIR/pages.json with the list. Resumable: pages already saved are skipped.
Reuses the polite request loop of wikisource_fetch.py.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wikisource_fetch import api  # noqa: E402


def main():
    lang, titles_path, out = sys.argv[1:4]
    titles = json.load(open(titles_path, encoding="utf-8"))
    os.makedirs(os.path.join(out, "html"), exist_ok=True)
    json.dump(titles, open(os.path.join(out, "pages.json"), "w", encoding="utf-8"), ensure_ascii=False)
    missing = 0
    for n, t in enumerate(titles):
        f = os.path.join(out, "html", f"{n:03d}.json")
        if os.path.exists(f):
            continue
        d = api(lang, action="parse", page=t, prop="text|revid", disablelimitreport=1, redirects=1)
        if "parse" not in d:
            print("missing", t)
            missing += 1
            continue
        json.dump(
            {"title": t, "revid": d["parse"]["revid"], "html": d["parse"]["text"]["*"]},
            open(f, "w", encoding="utf-8"),
            ensure_ascii=False,
        )
    print(len(titles), "pages", missing, "missing")
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
