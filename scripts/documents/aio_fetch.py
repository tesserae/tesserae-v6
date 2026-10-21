#!/usr/bin/env python3
"""Fetch Attic Inscriptions Online (AIO) through its REST API, politely.

One request per second at most, a User-Agent naming the project, two retries
per failure, every raw response stored so the fetch never repeats, and
resume from what is already stored. Stops after --max-seconds so a batch
fits inside one foreground call.

Usage: aio_fetch.py OUT_DIR [--max-seconds 540] [--html-for-greek]
OUT_DIR gets list/page_N.json, raw/<sourcevolume>__<id>.json, failures.json.
With --html-for-greek it also fetches the public HTML page of each inscription
that carries a Greek text (the API gives no date, monument type or findspot),
into html/<sourcevolume>__<id>.html, at the same pace.
"""
import argparse
import json
import os
import sys
import time
import urllib.request

BASE = "https://www.atticinscriptions.com"
UA = ("Tesserae Project, University at Buffalo (tesserae.caset.buffalo.edu) "
      "+https://tesserae.caset.buffalo.edu/")
_last = [0.0]


def get(url):
    wait = 1.05 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def get_retry(url):
    err = None
    for attempt in range(3):
        try:
            return get(url), None
        except Exception as e:  # recorded, not hidden
            err = f"{type(e).__name__}: {e}"
            time.sleep(5 * (attempt + 1))
    return None, err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--max-seconds", type=int, default=540)
    ap.add_argument("--html-for-greek", action="store_true")
    ap.add_argument("--html-for-bbaw", action="store_true",
                    help="also the HTML pages of the inscriptions paired with Berlin IG Greek "
                         "(list in OUT_DIR/bbaw_index.json from aio_fetch_bbaw.py)")
    a = ap.parse_args()
    t0 = time.time()
    os.makedirs(os.path.join(a.out, "list"), exist_ok=True)
    os.makedirs(os.path.join(a.out, "raw"), exist_ok=True)
    fail_path = os.path.join(a.out, "failures.json")
    failures = json.load(open(fail_path)) if os.path.exists(fail_path) else {}

    items, page = [], 1
    while True:
        p = os.path.join(a.out, "list", f"page_{page}.json")
        if os.path.exists(p):
            d = json.load(open(p))
        else:
            body, err = get_retry(f"{BASE}/inscription/list_all_inscriptions.json?page={page}")
            if body is None:
                print("LIST FAILED", page, err)
                return 2
            open(p, "wb").write(body)
            d = json.loads(body)
        items += d["inscriptions"]
        if not d.get("next"):
            break
        page += 1
    print("list:", len(items), "of", d["count"])

    done = skipped = 0
    for it in items:
        tail = it["api_url"].split("/inscription/", 1)[1][:-5]  # IGII31/292
        vol, ident = tail.split("/", 1)
        fn = os.path.join(a.out, "raw", f"{vol}__{ident.replace('/', '_')}.json")
        if os.path.exists(fn):
            skipped += 1
            continue
        if time.time() - t0 > a.max_seconds:
            print(f"TIME: stopped; fetched {done}, already had {skipped}")
            return 3
        body, err = get_retry(f"{BASE}/inscription/{vol}/{ident}.json")
        if body is None:
            failures[tail] = err
            json.dump(failures, open(fail_path, "w"), indent=1)
            continue
        failures.pop(tail, None)
        open(fn, "wb").write(body)
        done += 1
    json.dump(failures, open(fail_path, "w"), indent=1)
    bbaw_stems = set()
    if a.html_for_bbaw:
        bbaw_stems = set(json.load(open(os.path.join(a.out, "bbaw_index.json")))["per_inscription"])
    if a.html_for_greek or a.html_for_bbaw:
        os.makedirs(os.path.join(a.out, "html"), exist_ok=True)
        got = 0
        for it in items:
            tail = it["api_url"].split("/inscription/", 1)[1][:-5]
            vol, ident = tail.split("/", 1)
            stem = f"{vol}__{ident.replace('/', '_')}"
            hp = os.path.join(a.out, "html", stem + ".html")
            if os.path.exists(hp):
                continue
            rec = json.load(open(os.path.join(a.out, "raw", stem + ".json")))
            if not (rec.get("greek_epidoc") or (a.html_for_bbaw and stem in bbaw_stems)):
                continue
            if time.time() - t0 > a.max_seconds:
                print(f"TIME: stopped html; fetched {got}")
                return 3
            body, err = get_retry(f"{BASE}/inscription/{vol}/{ident}")
            if body is None:
                failures["html:" + tail] = err
                json.dump(failures, open(fail_path, "w"), indent=1)
                continue
            failures.pop("html:" + tail, None)
            open(hp, "wb").write(body)
            got += 1
        json.dump(failures, open(fail_path, "w"), indent=1)
        print(f"HTML COMPLETE: fetched {got}")
    print(f"COMPLETE: fetched {done}, already had {skipped}, failures {len(failures)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
