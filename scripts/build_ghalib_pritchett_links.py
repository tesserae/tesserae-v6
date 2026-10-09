#!/usr/bin/env python3
"""Build the verse-level link table from our Ghalib corpus refs to Frances W.
Pritchett's "A Desertful of Roses" verse pages (franpritchett.com/00ghalib/).

Why this exists: Pritchett's English translations and commentary carry no
stated license, so they cannot be copied into Tesserae; a link to her verse
page is what the Reader offers instead. This script builds the lookup table
consumed by backend/translations.py (and by backend/blueprints/passages.py's
/passages/translation route) at data/translations/links/ur__ghalib_pritchett_links.json.

Two corpus facts drive the approach:

1. Only `ghalib.diwan_wikisource` (272 ghazals, Wikisource's own numbering)
   ships in texts/ur/ today. A third edition, `ghalib.diwan_pritchett`
   (234 ghazals, numbered exactly as her site numbers them), was retired
   from the served corpus on 2026-09-07 (commit 0de9fabf) so a Ghalib
   passage could not appear three times over in Theme Search / Similar
   Passages / cross-language results. It survives only outside this repo,
   as a cross-reference for exactly this kind of alignment; this script
   reads it from wherever PRITCHETT_TESS points (see --pritchett-tess) and
   never writes it back into the tree.

2. Wikisource's ghazal numbering does NOT match Pritchett's (Wikisource has
   272 ghazals in its own order; Pritchett published 234). The two editions
   must be aligned by TEXT, not by number: first the opening verse (matla)
   of each ghazal, to pair up ghazals; then verse by verse inside each
   matched pair, again by text, because the retired Pritchett file is not
   uniformly one tess-line per half-line (misra) -- some ghazals store each
   verse as a split misra pair (2 tess lines), others as one joined line
   (both misras run together), and a few mix the two (ordinary verses
   followed by a trailing block of "x"-numbered manuscript-variant verses,
   which Pritchett's site also appends after the regular numbering, e.g.
   {1,6x} and {1,7x} after {1,1}..{1,5}). Her own per-ghazal index page
   (fetched separately, see fetch step below) gives the true, ordered verse
   label list per ghazal, including those "x" verses, so the split is
   inferred from that count rather than guessed from line length alone.

Pipeline:
  1. Fetch each of her 234 per-ghazal index pages once (cached to disk),
     one request at a time with a pause, identified by a plain User-Agent.
     Each page's verse links (e.g. "98_04.html", "1_06x.html") give the
     ordered, authoritative list of verse labels for that ghazal.
  2. Parse the retired Pritchett file's raw lines per ghazal and partition
     them into that many ordered chunks (1 or 2 tess lines each) by solving
     for how many chunks must be pairs vs singles to match the counted
     label list. A ghazal where no non-negative split solves this is
     flagged AMBIGUOUS and contributes no links at all (left unmapped,
     reported, never guessed).
  3. Parse `ghalib.diwan_wikisource.tess` into raw lines per ghazal.
  4. Match ghazals pairwise by fuzzy text similarity of the opening verse,
     trying both a one-line and a two-line (joined misra) reading on each
     side since the two corpora disagree about which. Keep the best match
     above a score and margin-over-runner-up threshold.
  5. Inside each matched ghazal pair, match every wikisource LINE against
     every Pritchett RAW line (not the chunk, so a split pair still matches
     at single-misra granularity) and take the best match above a
     threshold; unmatched wikisource lines (annotation lines such as a
     "in the Hamidiyah manuscript, additionally:" editorial header, or
     verses she does not cover) are left out, which is the expected case.
  6. Emit one JSON record per matched wikisource ref: the Pritchett verse
     URL, plus enough of the matching evidence (score, Pritchett ghazal/
     verse label) to audit a given link later.

Usage:
    python scripts/build_ghalib_pritchett_links.py \\
        --pritchett-tess /path/to/retired/texts/ur/ghalib.diwan_pritchett.tess \\
        --index-cache /path/to/scratch/pritchett_index_pages \\
        --out data/translations/links/ur__ghalib_pritchett_links.json

The index-page fetch is skipped (and the cache reused) on a second run.
"""
import argparse
import difflib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from backend.urdu.processor import normalize_urdu  # noqa: E402

BASE_URL = 'https://franpritchett.com/00ghalib'
UA = ('Mozilla/5.0 (compatible; TesseraeV6-research/1.0; '
      '+https://tesserae.caset.buffalo.edu)')
VERSE_RE = re.compile(r'(\d+)_(\d+)(x?)\.html')
GHAZAL_COUNT = 234

GHAZAL_MATCH_MIN_SCORE = 0.55
GHAZAL_MATCH_MIN_MARGIN = 0.05
VERSE_MATCH_MIN_SCORE = 0.55

_PUNCT_RE = re.compile(r'[،؛؟۔!,\."\'""‘’()\[\]{}:;٭*]')
_SPACE_RE = re.compile(r'\s+')


def norm(text):
    text = normalize_urdu(text or '')
    text = _PUNCT_RE.sub(' ', text)
    text = _SPACE_RE.sub(' ', text).strip()
    return text


def sim(a, b):
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


# ---------------------------------------------------------------------------
# Step 1: fetch (and cache) Pritchett's per-ghazal index pages.
# ---------------------------------------------------------------------------

def fetch_index_pages(cache_dir, pause=1.2, log=print):
    os.makedirs(cache_dir, exist_ok=True)
    verses = {}
    errors = {}
    for n in range(1, GHAZAL_COUNT + 1):
        dirname = f'{n:03d}'
        cache_path = os.path.join(cache_dir, f'{dirname}.html')
        if os.path.exists(cache_path):
            with open(cache_path, encoding='utf-8', errors='replace') as fh:
                html = fh.read()
        else:
            url = f'{BASE_URL}/{dirname}/index_{dirname}.html'
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    html = resp.read().decode('utf-8', errors='replace')
            except Exception as e:  # noqa: BLE001 -- report and move on
                errors[n] = str(e)
                log(f'  ghazal {n}: fetch failed: {e}')
                time.sleep(pause)
                continue
            with open(cache_path, 'w', encoding='utf-8') as fh:
                fh.write(html)
            time.sleep(pause)  # one request at a time, a pause between

        seen = []
        for m in VERSE_RE.finditer(html):
            g, v, x = m.groups()
            if int(g) != n:
                continue
            label = f'{g}_{v}{x}.html'
            if label not in seen:
                seen.append(label)
        verses[n] = seen
        if n % 50 == 0:
            log(f'  ...through ghazal {n}')
    return verses, errors


# ---------------------------------------------------------------------------
# Step 2/3: parse a .tess file into raw lines per ghazal.
# ---------------------------------------------------------------------------

def parse_tess_by_ghazal(path, ref_prefix):
    """{ghazal_num: [(ref, raw_text), ...]} in file order.

    Our two Ghalib editions tag refs differently: the Wikisource file uses
    "<ghalib.diwan_wikisource.ghazal.G.V>"; the retired Pritchett file uses
    "<ghalib.diwan_pritchett.G.V>" with no literal ".ghazal" segment. Both
    are accepted so one function serves either file unchanged.
    """
    pat = re.compile(r'^<' + re.escape(ref_prefix) + r'\.(?:ghazal\.)?(\d+)\.(\d+)>\t(.*)$')
    out = {}
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            m = pat.match(line)
            if not m:
                continue
            g = int(m.group(1))
            # Stored WITHOUT angle brackets: the rest of the codebase's ref
            # strings (ref_to_unit keys in the aligned-translation files,
            # normalize_ref, the align_*.py scripts) are the bare tag
            # content, never "<...>".
            out.setdefault(g, []).append((line[1:line.index(">")], m.group(3)))
    return out


# ---------------------------------------------------------------------------
# Step 2: partition Pritchett's raw lines per ghazal into (text, href) chunks
# matching the index page's verse count, pairs-first-singles-trailing (the
# "x" verses are always a trailing contiguous block on her site).
# ---------------------------------------------------------------------------

def chunk_pritchett_ghazal(raw_lines, hrefs):
    """Returns (chunks, ok). chunks: [(joined_text, [raw_texts], href), ...].
    ok is False when no valid split exists (ambiguous; left unmapped)."""
    n = len(raw_lines)
    v = len(hrefs)
    m = n - v        # number of 2-line (split-misra) chunks
    k = 2 * v - n    # number of 1-line (joined-verse) chunks
    if m < 0 or k < 0 or m + k != v:
        return None, False
    chunks = []
    idx = 0
    for _ in range(m):
        pair = raw_lines[idx:idx + 2]
        idx += 2
        chunks.append((' '.join(t for _, t in pair), [t for _, t in pair]))
    for _ in range(k):
        single = raw_lines[idx:idx + 1]
        idx += 1
        chunks.append((single[0][1], [single[0][1]]))
    if idx != n or len(chunks) != v:
        return None, False
    out = [(text, raws, href) for (text, raws), href in zip(chunks, hrefs)]
    return out, True


# ---------------------------------------------------------------------------
# Step 4: match ghazals between editions by opening-verse (matla) text.
# ---------------------------------------------------------------------------

def _opening_variants(raw_lines):
    if not raw_lines:
        return ['']
    one = norm(raw_lines[0][1])
    if len(raw_lines) > 1:
        two = norm(raw_lines[0][1] + ' ' + raw_lines[1][1])
    else:
        two = one
    return [one, two]


def matla_score(p_lines, w_lines):
    p_variants = _opening_variants(p_lines)
    w_variants = _opening_variants(w_lines)
    return max(sim(a, b) for a in p_variants for b in w_variants)


def match_ghazals(pritchett_lines, wikisource_lines, log=print):
    """For each wikisource ghazal, the best-matching Pritchett ghazal (or
    None). Returns {w_ghazal: {'pritchett': g or None, 'score': s,
    'runner_up': s2, 'confidence': 'high'|'ambiguous'|'unmatched'}}."""
    p_nums = sorted(pritchett_lines)
    out = {}
    for w_g, w_lines in sorted(wikisource_lines.items()):
        scored = []
        for p_g in p_nums:
            s = matla_score(pritchett_lines[p_g], w_lines)
            scored.append((s, p_g))
        scored.sort(reverse=True)
        best_score, best_g = scored[0]
        runner_up = scored[1][0] if len(scored) > 1 else 0.0
        if best_score < GHAZAL_MATCH_MIN_SCORE:
            conf = 'unmatched'
            best_g = None
        elif (best_score - runner_up) < GHAZAL_MATCH_MIN_MARGIN:
            conf = 'ambiguous'
        else:
            conf = 'high'
        out[w_g] = {'pritchett': best_g, 'score': round(best_score, 3),
                     'runner_up': round(runner_up, 3), 'confidence': conf}
    return out


# ---------------------------------------------------------------------------
# Step 5/6: verse-level alignment inside a matched ghazal pair, and the
# final link records.
# ---------------------------------------------------------------------------

def align_and_build(pritchett_lines, wikisource_lines, ghazal_map,
                     pritchett_chunks, pritchett_ghazal_num_str):
    links = {}            # wikisource ref -> link record
    unmapped = []          # (ref, reason)
    ambiguous_verse = []   # refs where >1 pritchett line tied for best match

    for w_g, w_lines in sorted(wikisource_lines.items()):
        info = ghazal_map[w_g]
        p_g = info['pritchett']
        if p_g is None:
            for ref, _ in w_lines:
                unmapped.append((ref, 'no matching Pritchett ghazal'))
            continue
        chunks = pritchett_chunks.get(p_g)
        if chunks is None:
            for ref, _ in w_lines:
                unmapped.append((ref, f'Pritchett ghazal {p_g} verse count is ambiguous'))
            continue

        # Flatten chunks to (raw_text, href) for misra-granularity matching.
        flat = []
        for _, raws, href in chunks:
            for raw in raws:
                flat.append((raw, href))

        for ref, text in w_lines:
            nt = norm(text)
            scored = []
            for raw, href in flat:
                scored.append((sim(nt, norm(raw)), raw, href))
            scored.sort(key=lambda t: t[0], reverse=True)
            best = scored[0]
            if best[0] < VERSE_MATCH_MIN_SCORE:
                unmapped.append((ref, 'no Pritchett verse text matched closely enough'))
                continue
            tie = [s for s in scored if s[0] >= best[0] - 0.01 and s[2] != best[2]]
            if tie:
                ambiguous_verse.append(ref)
                unmapped.append((ref, 'tied between more than one Pritchett verse'))
                continue
            m = re.match(r'(\d+)_(\d+x?)\.html', best[2])
            verse_label = m.group(2) if m else best[2]
            url = f'{BASE_URL}/{p_g:03d}/{best[2]}'
            links[ref] = {
                'url': url,
                'pritchett_ghazal': p_g,
                'pritchett_verse': verse_label,
                'match_score': round(best[0], 3),
                'ghazal_match_score': info['score'],
            }
    return links, unmapped, ambiguous_verse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pritchett-tess', required=True,
                     help='Path to the retired ghalib.diwan_pritchett.tess (not in this repo)')
    ap.add_argument('--wikisource-tess',
                     default=os.path.join(REPO_ROOT, 'texts', 'ur', 'ghalib.diwan_wikisource.tess'))
    ap.add_argument('--index-cache', required=True,
                     help='Directory to cache fetched index_NNN.html pages in')
    ap.add_argument('--out', default=os.path.join(
        REPO_ROOT, 'data', 'translations', 'links', 'ur__ghalib_pritchett_links.json'))
    ap.add_argument('--report', default=None,
                     help='Optional path to write a plain-text coverage report')
    ap.add_argument('--no-fetch', action='store_true',
                     help='Use only what is already cached; fail if a ghazal is missing')
    args = ap.parse_args()

    print('[1/5] Pritchett per-ghazal index pages (cached fetch, one at a time)...')
    if args.no_fetch:
        verses = {}
        for n in range(1, GHAZAL_COUNT + 1):
            p = os.path.join(args.index_cache, f'{n:03d}.html')
            with open(p, encoding='utf-8') as fh:
                html = fh.read()
            verses[n] = [f'{m.group(1)}_{m.group(2)}{m.group(3)}.html'
                         for m in VERSE_RE.finditer(html) if int(m.group(1)) == n]
        errors = {}
    else:
        verses, errors = fetch_index_pages(args.index_cache)
    if errors:
        print(f'  {len(errors)} ghazal index pages failed to fetch: {sorted(errors)}')

    print('[2/5] Parsing the retired Pritchett file and chunking by verse count...')
    pritchett_lines = parse_tess_by_ghazal(args.pritchett_tess, 'ghalib.diwan_pritchett')
    pritchett_chunks = {}
    ambiguous_ghazals = []
    for g, raws in pritchett_lines.items():
        hrefs = verses.get(g, [])
        chunks, ok = chunk_pritchett_ghazal(raws, hrefs)
        if ok:
            pritchett_chunks[g] = chunks
        else:
            ambiguous_ghazals.append(g)
    print(f'  {len(pritchett_chunks)}/{len(pritchett_lines)} Pritchett ghazals cleanly chunked; '
          f'{len(ambiguous_ghazals)} ambiguous: {sorted(ambiguous_ghazals)}')

    print('[3/5] Parsing the Wikisource file...')
    wikisource_lines = parse_tess_by_ghazal(args.wikisource_tess, 'ghalib.diwan_wikisource')
    print(f'  {len(wikisource_lines)} Wikisource ghazals, '
          f'{sum(len(v) for v in wikisource_lines.values())} lines')

    print('[4/5] Matching ghazals by opening-verse (matla) text...')
    ghazal_map = match_ghazals(pritchett_lines, wikisource_lines)
    high = sum(1 for v in ghazal_map.values() if v['confidence'] == 'high')
    amb = sum(1 for v in ghazal_map.values() if v['confidence'] == 'ambiguous')
    unm = sum(1 for v in ghazal_map.values() if v['confidence'] == 'unmatched')
    print(f'  {high} high-confidence ghazal matches, {amb} ambiguous, {unm} unmatched '
          f'(out of {len(ghazal_map)} Wikisource ghazals)')

    print('[5/5] Aligning verses inside matched ghazals and building links...')
    links, unmapped, ambiguous_verse = align_and_build(
        pritchett_lines, wikisource_lines, ghazal_map, pritchett_chunks, None)

    total_ws_lines = sum(len(v) for v in wikisource_lines.values())
    print(f'  {len(links)}/{total_ws_lines} Wikisource verses linked; '
          f'{len(unmapped)} unmapped; {len(ambiguous_verse)} tied/ambiguous')

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    payload = {
        'work': 'ghalib.diwan_wikisource',
        'language': 'ur',
        'translator': 'Frances W. Pritchett',
        'site_title': 'A Desertful of Roses',
        'source_url': 'https://franpritchett.com/00ghalib/',
        'generated_by': 'scripts/build_ghalib_pritchett_links.py',
        'note': ('Maps ghalib.diwan_wikisource refs to the Pritchett verse page that '
                 'carries the same couplet, by text alignment through a retired, '
                 'Pritchett-numbered edition kept only for this cross-reference (not '
                 'part of the served corpus). No translation text is copied; the link '
                 'points to her own page.'),
        'wikisource_ghazal_count': len(wikisource_lines),
        'pritchett_ghazal_count': len(pritchett_lines),
        'ambiguous_pritchett_ghazals': sorted(ambiguous_ghazals),
        'links': links,
    }
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print(f'Wrote {args.out} ({len(links)} links)')

    if args.report:
        with open(args.report, 'w', encoding='utf-8') as fh:
            fh.write(f'Wikisource lines total: {total_ws_lines}\n')
            fh.write(f'Linked: {len(links)}\n')
            fh.write(f'Unmapped: {len(unmapped)}\n')
            fh.write(f'Ambiguous (tied match): {len(ambiguous_verse)}\n\n')
            fh.write('Ambiguous Pritchett ghazals (verse count could not be split): '
                      f'{sorted(ambiguous_ghazals)}\n\n')
            fh.write('Ghazal match confidence:\n')
            for w_g, info in sorted(ghazal_map.items()):
                fh.write(f'  wikisource {w_g} -> pritchett {info["pritchett"]} '
                          f'score={info["score"]} runner_up={info["runner_up"]} '
                          f'{info["confidence"]}\n')
            fh.write('\nUnmapped / ambiguous wikisource refs:\n')
            for ref, reason in unmapped:
                fh.write(f'  {ref}: {reason}\n')
        print(f'Wrote report to {args.report}')


if __name__ == '__main__':
    main()
