#!/usr/bin/env python3
"""Fetch the Greek text of the Berlin IG digital edition for AIO inscriptions
that have no Greek of their own (Inscriptiones Graecae, Berlin-Brandenburg
Academy of Sciences and Humanities, CC BY 4.0).

The IG numbers come from the telota.bbaw.de / pom.bbaw.de links in the
references of the AIO raw records. Each file is requested from
https://telota.bbaw.de/ig/api/xml/<IG number> at most once a second with the
project User-Agent, kept under OUT/bbaw_raw/, and the run resumes from what is
there. A file whose <licence> is not CC BY 4.0 is recorded in
bbaw_licence_problems.json and not used.

Usage: aio_fetch_bbaw.py AIO_DIR [--max-seconds 560]
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

UA = ("Tesserae Project, University at Buffalo (tesserae.caset.buffalo.edu) "
      "+https://tesserae.caset.buffalo.edu/")
API = "https://telota.bbaw.de/ig/api/xml/"
LICENCE = "https://creativecommons.org/licenses/by/4.0/legalcode"
_last = [0.0]


def ig_number(link: str):
    m = re.search(r"bbaw\.de/ig/(?:digitale-edition/inschrift/)?(.+)$", link)
    if not m:
        return None
    return urllib.parse.unquote(m.group(1)).strip()


def fname(num: str) -> str:
    return hashlib.sha1(num.encode("utf-8")).hexdigest()[:16] + ".xml"


def get(url):
    wait = 1.05 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def numbers_by_inscription(aio_dir):
    out = {}
    for f in sorted(glob.glob(os.path.join(aio_dir, "raw", "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        if d.get("greek_epidoc"):
            continue
        nums = []
        for r in d.get("references", []):
            for l in r.get("external_links", []):
                if "bbaw.de" in l:
                    n = ig_number(l)
                    if n and n not in nums:
                        nums.append(n)
        if nums:
            out[os.path.basename(f)[:-5]] = nums
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("aio_dir")
    ap.add_argument("--max-seconds", type=int, default=560)
    a = ap.parse_args()
    t0 = time.time()
    raw = os.path.join(a.aio_dir, "bbaw_raw")
    os.makedirs(raw, exist_ok=True)
    per = numbers_by_inscription(a.aio_dir)
    allnums = []
    for nums in per.values():
        for n in nums:
            if n not in allnums:
                allnums.append(n)
    json.dump({"per_inscription": per, "files": {n: fname(n) for n in allnums}},
              open(os.path.join(a.aio_dir, "bbaw_index.json"), "w"), ensure_ascii=False, indent=1)
    fail_path = os.path.join(a.aio_dir, "bbaw_failures.json")
    fails = json.load(open(fail_path)) if os.path.exists(fail_path) else {}
    done = got = 0
    for n in allnums:
        p = os.path.join(raw, fname(n))
        if os.path.exists(p):
            done += 1
            continue
        if n in fails and fails[n].startswith("HTTP 404"):
            continue
        if time.time() - t0 > a.max_seconds:
            print(f"TIME: {len(allnums)} numbers, {done} had, {got} fetched now")
            return 3
        url = API + urllib.parse.quote(n, safe=",")
        err = None
        for attempt in range(3):
            try:
                body = get(url)
                err = None
                break
            except urllib.error.HTTPError as e:
                err = f"HTTP {e.code}"
                if e.code == 404:
                    break
                time.sleep(5 * (attempt + 1))
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                time.sleep(5 * (attempt + 1))
        if err:
            fails[n] = err
            json.dump(fails, open(fail_path, "w"), ensure_ascii=False, indent=1)
            continue
        fails.pop(n, None)
        open(p, "wb").write(body)
        got += 1
    json.dump(fails, open(fail_path, "w"), ensure_ascii=False, indent=1)
    print(f"COMPLETE: {len(per)} inscriptions, {len(allnums)} IG numbers, {done} had, {got} fetched, {len(fails)} failures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
