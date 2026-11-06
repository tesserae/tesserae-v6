#!/usr/bin/env python3
"""Build a verse .tess file from Urdu Wikisource poem pages (wikisource_titles_fetch.py output).

One hemistich per line, as in wali.diwan_wikisource.tess, with the reference
`<work.poem.line>`. Poems are numbered in the order of PAGES_JSON (Wikisource's
alphabetical order of titles), except that the titles given with --last are
moved to the end in the order given, so a masnavi sits after the ghazals.
Lines are the page's text lines with runs of white space collapsed to one space
and nothing else changed (zero-width non-joiners and the takhallus sign stay).

Usage:
    wikisource_poems_to_tess.py PAGES_DIR WORK OUT.tess OUT.pages.json \
        [--site ur.wikisource.org --author-page TITLE --last TITLE ...]
Writes the .tess file and a page record in the shape of the earlier Urdu diwans
(site, author_page, license, fetched, pages with title, revid, url, lines, kept, poem).
Standard library only.
"""

import argparse
import datetime
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wikisource_html_text import paragraphs  # noqa: E402

DROP_PARA = re.compile(r"^(لوا خطا|سانچہ:|سانچه:|تغییرمسیر به|تغییر مسیر به)")


def page_lines(html_text):
    out = []
    for kind, text in paragraphs(html_text):
        if kind != "p":
            continue
        text = re.sub(r"\s+", " ", text).strip()
        if text and not DROP_PARA.match(text):
            out.append(text)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pages_dir")
    ap.add_argument("work")
    ap.add_argument("out_tess")
    ap.add_argument("out_record")
    ap.add_argument("--site", default="ur.wikisource.org")
    ap.add_argument("--author-page", default="")
    ap.add_argument("--last", action="append", default=[])
    a = ap.parse_args()

    titles = json.load(open(os.path.join(a.pages_dir, "pages.json"), encoding="utf-8"))
    index = {t: n for n, t in enumerate(titles)}
    order = [t for t in titles if t not in a.last] + list(a.last)
    for t in a.last:
        if t not in index:
            raise SystemExit(f"--last title not in pages.json: {t}")
    lines_out, pages = [], []
    for poem, t in enumerate(order, 1):
        d = json.load(open(os.path.join(a.pages_dir, "html", f"{index[t]:03d}.json"), encoding="utf-8"))
        lines = page_lines(d["html"])
        for k, text in enumerate(lines, 1):
            lines_out.append(f"<{a.work}.{poem}.{k}>\t{text}")
        url = f"https://{a.site}/wiki/" + urllib.parse.quote(t.replace(" ", "_"))
        pages.append({"title": t, "revid": d["revid"], "url": url, "lines": len(lines), "kept": True, "poem": poem})
    with open(a.out_tess, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_out) + "\n")
    rec = {
        "site": a.site,
        "author_page": a.author_page,
        "license": "CC-BY-SA-4.0 (Wikisource transcription); public-domain author",
        "fetched": datetime.date.today().isoformat(),
        "pages": pages,
    }
    json.dump(rec, open(a.out_record, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(a.work, len(pages), "poems", len(lines_out), "lines")


if __name__ == "__main__":
    main()
