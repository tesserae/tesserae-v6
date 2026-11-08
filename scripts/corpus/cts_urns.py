#!/usr/bin/env python3
"""The CTS URN table, data/cts_urns.json: the Perseus / Open Greek and Latin
citation URN of each Latin and Greek work file.

A URN such as urn:cts:latinLit:phi0690.phi003 (Vergil, Aeneid) is what Perseus,
Scaife and the Open Greek and Latin repositories cite by. The backend reads the
table (backend/cts_urns.py) to answer /api/passages/by-urn and to put a `urn`
on connector passages. Procedure: docs/DATA_OPERATIONS.md, "Adding a text".

Table shape: {"_description", "_last_updated", "la": {"vergil.aeneid.tess":
{"urn": ..., "source": "catalog|url|manual|none", "note": optional}}, "grc": {...}}.
A key is the whole-work file name; a work held only as parts keeps the name it
would have as one file, and every part resolves to it.

Commands:
  fill    add an entry for every la and grc work that has none. Never changes an
          existing entry. Order of evidence: (1) the author and title matching a work of the
          Perseus and Open Greek and Latin inventories (__cts__.xml of canonical-latinLit,
          canonical-greekLit, First1KGreek and csel-dev), exact after normalization (source
          "catalog"); (2) with --hopper-cache, the Perseus hopper document id in the work's
          e_source_url in backend/text_sources.json, whose page names the URN (source "url");
          (3) a URN written in e_source_url, kept only when the inventory lists it under a
          title that agrees with ours (source "url"). Fuzzy matches
          are never written by themselves: --fuzzy-report lists them for a person to
          read, and --accept FILE (a JSON object {key: {"urn", "source", "note"}} of the
          ones read and kept, keys written "la:name.tess" or "grc:name.tess") writes those.
  none    record that a work has no CTS URN (a medieval or modern text no inventory lists),
          after a person has looked: none --language la KEY... --note "why". The entry is
          {"urn": null, "source": "none", "note": ...}; verify_text_coverage reads it as done.
  check   exit 1 and list every table entry whose text file (whole or part) is
          gone, and every entry without a well-formed URN (a "none" entry is allowed).
  lookup  print what a URN resolves to: lookup urn:cts:latinLit:phi0690.phi003:1.1-1.7

Options: --table PATH, --texts DIR (default texts/ in the repository),
--extra-texts DIR (a folder that has files --texts lacks), --inventory DIR
(repeatable; a folder holding clones of the three repositories, treated as data).
The lookup function the backend uses is backend.cts_urns.lookup, re-exported here.
"""
import argparse
import datetime
import difflib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request
from html import unescape

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from backend.cts_urns import (LANGUAGES, NAMESPACES, PART_RE, lookup, parse_urn,  # noqa: E402,F401
                              work_key)

DEFAULT_TABLE = os.path.join(REPO, 'data', 'cts_urns.json')
DEFAULT_TEXTS = os.path.join(REPO, 'texts')
SOURCES = os.path.join(REPO, 'backend', 'text_sources.json')
DESCRIPTION = ('The CTS URN (the citation form of Perseus, Scaife and the Open Greek and Latin '
               'repositories) of each Latin and Greek work file, keyed by the whole-work file name; '
               'part files resolve to their work. "source" says how the entry was found: catalog '
               '(author and title matched in the Perseus / Open Greek and Latin inventories), url '
               '(the work\'s Perseus hopper page or credit row names the URN and its title agrees), manual (confirmed '
               'by reading the work\'s page) or none (a person looked and no CTS URN exists, so urn is null). '
               'scripts/corpus/cts_urns.py fills and checks it.')
URN_IN_URL = re.compile(r'urn:cts:(?:latinLit|greekLit):[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+')
WORK_URN = re.compile(r'^urn:cts:(latinLit|greekLit):[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+$')


# ---- the table ----------------------------------------------------------

def read_table(path):
    if not os.path.exists(path):
        return {'_description': DESCRIPTION, '_last_updated': '', 'la': {}, 'grc': {}}
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save_table(path, table):
    table['_description'] = DESCRIPTION
    table['_last_updated'] = datetime.date.today().isoformat()
    for lang in LANGUAGES:
        table[lang] = dict(sorted((table.get(lang) or {}).items()))
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(table, f, ensure_ascii=False, indent=1)
        f.write('\n')


# ---- our works ----------------------------------------------------------

def list_works(texts, extra=None):
    """{lang: {whole-work key: first file name}} for la and grc, parts folded into their work."""
    found = {lang: {} for lang in LANGUAGES}
    for root in (texts, extra):
        if not root:
            continue
        for lang in LANGUAGES:
            d = os.path.join(root, lang)
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                if fn.endswith('.tess'):
                    found[lang].setdefault(work_key(fn), os.path.join(d, fn))
    return found


# ---- the inventory ------------------------------------------------------

def _attr(tag, name):
    m = re.search(rf'\b{name}="([^"]*)"', tag)
    return m.group(1) if m else None


def read_inventory(dirs):
    """Works of the CTS inventories under `dirs`: [{urn, language, author_names, titles}].

    The __cts__.xml files are third-party data and are read with regular
    expressions, never handed to an XML parser or executed.
    """
    groups, works = {}, []
    for root in dirs:
        for dirpath, _dirs, files in os.walk(root):
            if '__cts__.xml' not in files or '/.git' in dirpath:
                continue
            with open(os.path.join(dirpath, '__cts__.xml'), encoding='utf-8', errors='replace') as f:
                xml = f.read()
            m = re.search(r'<ti:textgroup\b[^>]*>', xml)
            if m:
                urn = _attr(m.group(0), 'urn')
                names = [unescape(re.sub(r'\s+', ' ', n)).strip()
                         for n in re.findall(r'<ti:groupname\b[^>]*>(.*?)</ti:groupname>', xml, re.S)]
                if urn:
                    groups.setdefault(urn, []).extend(n for n in names if n)
                continue
            m = re.search(r'<ti:work\b[^>]*>', xml)
            if m:
                urn, group = _attr(m.group(0), 'urn'), _attr(m.group(0), 'groupUrn')
                titles = [unescape(re.sub(r'\s+', ' ', t)).strip()
                          for t in re.findall(r'<ti:title\b[^>]*>(.*?)</ti:title>', xml, re.S)]
                labels = [unescape(re.sub(r'\s+', ' ', t)).strip()
                          for t in re.findall(r'<ti:label\b[^>]*>(.*?)</ti:label>', xml, re.S)]
                if urn and WORK_URN.match(urn):
                    works.append({'urn': urn, 'group': group, 'titles': [t for t in titles if t],
                                  'labels': [t for t in labels if t]})
    out = []
    for w in works:
        w['author_names'] = groups.get(w['group'], [])
        w['language'] = NAMESPACES[w['urn'].split(':')[2]]
        out.append(w)
    return out


# ---- matching -----------------------------------------------------------

def norm(s):
    """Lowercase, accents and punctuation gone, ae/oe spelled out, j as i and v as u."""
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace('æ', 'ae').replace('œ', 'oe').replace('j', 'i').replace('v', 'u')
    return re.sub(r'[^a-z0-9]+', '', s)


def is_pseudo(names):
    """True when any of the names marks a work as pseudonymous ("Pseudo-Cyprian", "Cyprian, Pseudo")."""
    return any('pseudo' in norm(n) for n in names)


def author_variants(names):
    """Every way an inventory author is written: whole, each parenthetical, each comma part."""
    out = set()
    for n in names:
        out.add(norm(n))
        for piece in re.split(r'[()\[\],;/]', n):
            if norm(piece):
                out.add(norm(piece))
    return {v for v in out if v}


def ratio(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def best_ratio(ours, theirs, containment=False):
    """Best similarity of any of ours to any of theirs. With containment, a name of four or
    more letters that sits inside the other ("lucian" in "lucianofsamosata") scores 0.9."""
    best = 0.0
    for o in ours:
        for t in theirs:
            r = ratio(o, t)
            if containment and min(len(o), len(t)) >= 4 and (o in t or t in o):
                r = max(r, 0.9)
            best = max(best, r)
    return best


def index_inventory(inventory):
    """Per language: [(work, author_variants, normalized titles, normalized titles and edition labels)].
    Only the work's own titles count for an exact match: an edition label can name another
    work (the label of Cicero De Fato's edition reads De Divinatione)."""
    idx = {lang: [] for lang in LANGUAGES}
    for w in inventory:
        w['pseudo'] = is_pseudo(w['author_names'])
        titles = {norm(t) for t in w['titles'] if norm(t)}
        both = titles | {norm(t) for t in w.get('labels', []) if norm(t)}
        idx[w['language']].append((w, author_variants(w['author_names']), titles, both))
    return idx


def our_names(lang, path, sources):
    """Authors and titles one work goes by: the display names the site shows (backend.utils)
    and the credit row's author and work."""
    from backend.utils import get_text_metadata
    meta = get_text_metadata(path)
    authors = {norm(meta.get('author'))}
    titles = {norm(meta.get('work')), norm(meta.get('title'))}
    base = os.path.basename(work_key(path))[:-5]
    parts = base.split('.', 1)
    authors.add(norm(parts[0].replace('_', ' ')))
    if len(parts) > 1:
        titles.add(norm(parts[1].replace('_', ' ')))
    row = sources.get(((meta.get('author') or '').strip().lower(), (meta.get('work') or '').strip().lower()))
    if row:
        authors.add(norm(row.get('author')))
        titles.add(norm(row.get('work')))
    return {a for a in authors if a}, {t for t in titles if t}, row


def load_sources():
    if not os.path.exists(SOURCES):
        return {}
    with open(SOURCES, encoding='utf-8') as f:
        rows = json.load(f)
    return {((r.get('author') or '').strip().lower(), (r.get('work') or '').strip().lower()): r for r in rows}


# ---- the Perseus hopper page ---------------------------------------------

HOPPER_DOC = re.compile(r'doc=Perseus(?:%3[Aa]|:)text(?:%3[Aa]|:)(\d{4}\.\d{2}\.\d{4})(?![\d\-]|%3[Aa]|:)')
WORK_URN_ANY = re.compile(r'urn:cts:(?:latinLit|greekLit):[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+(?![A-Za-z0-9_\-]|\.[A-Za-z0-9_\-])')


def hopper_doc_id(row):
    """The bare Perseus hopper document id in a credit row's e_source_url ("1999.02.0056"),
    or None. A link to a part of a document (a speech, a section, a -2 variant) is not a
    whole-work id and gives None."""
    m = HOPPER_DOC.search((row or {}).get('e_source_url') or '')
    return m.group(1) if m else None


def hopper_page(doc_id, cache, pause=1.0):
    """{'urn', 'title'} read from the hopper page of a document: the work URN the page names most
    often (None when two tie) and the page title ("Lucian, Hippias, section 1"). The page is read
    as text only (a regular expression over the HTML); results are kept in `cache`. None when
    the page could not be fetched (not cached, so the next run tries again)."""
    if doc_id in cache:
        return cache[doc_id]
    url = f'http://www.perseus.tufts.edu/hopper/text?doc=Perseus%3atext%3a{doc_id}'
    try:
        time.sleep(pause)
        req = urllib.request.Request(url, headers={'User-Agent': 'Tesserae CTS URN table builder'})
        with urllib.request.urlopen(req, timeout=40) as r:  # nosec B310 - a fixed http URL
            html = r.read().decode('utf-8', errors='replace')
    except OSError:
        return None
    counts = {}
    for u in WORK_URN_ANY.findall(html):
        counts[u] = counts.get(u, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    urn = ranked[0][0] if ranked and (len(ranked) == 1 or ranked[0][1] > ranked[1][1]) else None
    m = re.search(r'<title>(.*?)</title>', html, re.S)
    title = unescape(re.sub(r'\s+', ' ', m.group(1))).strip() if m else ''
    cache[doc_id] = {'urn': urn, 'title': title}
    return cache[doc_id]


def hopper_match(lang, titles, file_titles, row, idx, cache):
    """('url', urn, detail) when the credit row's hopper document names a work of this language
    and the work's title agrees with ours: the inventory's title for that URN, or failing that a
    comma-separated part of the page's own title ("Vergil, Eclogues"), at least 0.8 alike. The
    title check keeps a document that holds many works (the Isocrates speeches) from taking the
    URN of its first."""
    doc = hopper_doc_id(row)
    page = hopper_page(doc, cache) if doc else None
    if not page or not page['urn'] or page['urn'].split(':')[2] != {'la': 'latinLit', 'grc': 'greekLit'}[lang]:
        return None
    if best_ratio(file_titles, {norm(x) for x in page['title'].split(',')[1:] if norm(x)}) >= 0.8:
        return 'url', page['urn'], f'hopper document {doc} ("{page["title"]}")'
    for w, _av, _t, both in idx[lang]:
        if w['urn'] == page['urn'] and best_ratio(titles, both) >= 0.8 and best_ratio(file_titles, both) >= 0.5:
            return 'url', page['urn'], f'hopper document {doc}'
    return None


def url_match(lang, titles, file_titles, row, idx):
    """('url', urn, detail) when the work's credit row carries a URN, that URN is a work of this
    language in the inventories, and one of its titles is at least 0.8 like one of ours and at least
    0.5 like the title in the file name (a credit row is shared by files whose display titles are
    set from it, such as Aristotle's lost first part of the Constitution). Credit
    rows have carried stale URNs (several Archimedes and Aristotle works, Pseudo-Lucian), so a
    URN that fails either test is not written."""
    m = URN_IN_URL.search((row or {}).get('e_source_url') or '')
    if not m or m.group(0).split(':')[2] != {'la': 'latinLit', 'grc': 'greekLit'}[lang]:
        return None
    for w, _av, _t, both in idx[lang]:
        if w['urn'] == m.group(0) and best_ratio(titles, both) >= 0.8 and best_ratio(file_titles, both) >= 0.5:
            return 'url', m.group(0), 'in e_source_url, and its inventory title agrees'
    return None


def match_work(lang, authors, titles, file_titles, row, idx, hopper_cache=None, pseudo=False):
    """('catalog'|'url'|'fuzzy'|None, urn, detail), in the order of evidence:
    (1) author and title both equal after normalization and exactly one inventory work fits (a
    pseudonymous work, one whose author is marked pseudo, only matches another such work);
    (2) the credit row's Perseus hopper document id, when its page names a work whose title agrees;
    (3) a URN in the credit row's e_source_url that the inventory confirms;
    (4) a fuzzy candidate, which is only reported for a person to read."""
    exact = sorted({w['urn'] for w, av, tn, both in idx[lang]
                    if authors & av and titles & tn and w['pseudo'] == pseudo
                    and (not file_titles or best_ratio(file_titles, both) >= 0.5)})
    if len(exact) == 1:
        return 'catalog', exact[0], 'author and title equal after normalization'
    if len(exact) > 1:
        return 'fuzzy', exact[0], 'ambiguous: ' + ' '.join(exact)
    if hopper_cache is not None:
        hit = hopper_match(lang, titles, file_titles, row, idx, hopper_cache)
        if hit:
            return hit
    hit = url_match(lang, titles, file_titles, row, idx)
    if hit:
        return hit
    scored = []
    for w, av, _, tn in idx[lang]:
        if w['pseudo'] != pseudo:
            continue
        a, t = best_ratio(authors, av, containment=True), best_ratio(titles, tn)
        if a >= 0.6 and t >= 0.6:
            scored.append((0.5 * a + 0.5 * t, w['urn'], a, t, w['author_names'][:1], w['titles'][:1]))
    scored.sort(reverse=True)
    if scored and scored[0][0] >= 0.75:
        s = scored[0]
        return 'fuzzy', s[1], f'score {s[0]:.2f} author {s[2]:.2f} title {s[3]:.2f}: {s[4]} / {s[5]}'
    return None, None, ''


# ---- commands -----------------------------------------------------------

def cmd_fill(args):
    table = read_table(args.table)
    inventory = read_inventory(args.inventory)
    idx = index_inventory(inventory)
    sources = load_sources()
    works = list_works(args.texts, args.extra_texts)
    hopper_cache = None
    if args.hopper_cache:
        hopper_cache = json.load(open(args.hopper_cache)) if os.path.exists(args.hopper_cache) else {}
    added, fuzzy, left = {lg: 0 for lg in LANGUAGES}, [], []
    for lang in LANGUAGES:
        entries = table.setdefault(lang, {})
        for key, path in works[lang].items():
            if key in entries:
                continue
            authors, titles, row = our_names(lang, path, sources)
            file_titles = {norm(key[:-5].split('.', 1)[1].replace('_', ' '))} if '.' in key[:-5] else set()
            kind, urn, detail = match_work(lang, authors, titles, file_titles, row, idx, hopper_cache,
                                           pseudo='pseudo' in os.path.basename(key).split('.')[0])
            if kind in ('url', 'catalog'):
                entries[key] = {'urn': urn, 'source': kind}
                added[lang] += 1
            elif kind == 'fuzzy':
                fuzzy.append({'language': lang, 'key': key, 'urn': urn, 'detail': detail,
                              'ours': [sorted(authors)[:2], sorted(titles)[:2]]})
                left.append((lang, key))
            else:
                left.append((lang, key))
    accepted = {lg: 0 for lg in LANGUAGES}
    if args.accept:
        with open(args.accept, encoding='utf-8') as f:
            decisions = json.load(f)
        for key, entry in decisions.items():
            lang, _, key = key.partition(':')
            if lang not in LANGUAGES:
                continue
            if key in table[lang] or not entry.get('urn') or not WORK_URN.match(entry['urn']):
                continue
            table[lang][key] = {k: v for k, v in entry.items() if k in ('urn', 'source', 'note')}
            accepted[lang] += 1
            left = [x for x in left if x != (lang, key)]
    if args.hopper_cache:
        with open(args.hopper_cache, 'w') as f:
            json.dump(hopper_cache, f, indent=1)
    if args.fuzzy_report:
        with open(args.fuzzy_report, 'w', encoding='utf-8') as f:
            json.dump(fuzzy, f, ensure_ascii=False, indent=1)
    if not args.dry_run:
        save_table(args.table, table)
    for lang in LANGUAGES:
        total = len(works[lang])
        have = sum(1 for k in works[lang] if k in table[lang])
        print(f'{lang}: {have} of {total} works have a URN '
              f'(added {added[lang]} by name or URL, {accepted[lang]} from --accept); '
              f'{total - have} left, {sum(1 for f in fuzzy if f["language"] == lang)} fuzzy candidates to read')
    unmatched = [f'{lg}:{k}' for lg, k in left]
    print('unmatched (first 40):', ', '.join(unmatched[:40]))
    if args.unmatched_report:
        with open(args.unmatched_report, 'w', encoding='utf-8') as f:
            f.write('\n'.join(unmatched) + '\n')
    return 0


def cmd_check(args):
    table = read_table(args.table)
    works = list_works(args.texts, args.extra_texts)
    bad = []
    for lang in LANGUAGES:
        for key, entry in (table.get(lang) or {}).items():
            urn = entry.get('urn') if isinstance(entry, dict) else None
            if urn is None and isinstance(entry, dict) and entry.get('source') == 'none':
                if key not in works[lang]:
                    bad.append(f'{lang}/{key}: no text file (whole or part)')
                continue
            if not urn or not WORK_URN.match(urn) or urn.split(':')[2] != {'la': 'latinLit', 'grc': 'greekLit'}[lang]:
                bad.append(f'{lang}/{key}: not a work URN for this language ({urn!r})')
            elif key not in works[lang]:
                bad.append(f'{lang}/{key}: no text file (whole or part)')
    for line in bad:
        print(line)
    n = sum(len(table.get(lg) or {}) for lg in LANGUAGES)
    print(f'{n} entries, {len(bad)} problems')
    return 1 if bad else 0


def cmd_none(args):
    table = read_table(args.table)
    works = list_works(args.texts, args.extra_texts)
    for key in args.keys:
        key = work_key(key)
        if key not in works[args.language]:
            print(f'{args.language}/{key}: no text file, not recorded')
            return 1
        if key in table.setdefault(args.language, {}):
            print(f'{args.language}/{key}: already has an entry, left alone')
            continue
        table[args.language][key] = {'urn': None, 'source': 'none', 'note': args.note}
    save_table(args.table, table)
    return 0


def cmd_lookup(args):
    table = read_table(args.table)
    for urn in args.urns:
        try:
            print(urn, '->', lookup(urn, texts_dir=args.texts, table=table))
        except (ValueError, LookupError) as e:
            print(urn, '->', type(e).__name__, e)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--table', default=DEFAULT_TABLE)
    ap.add_argument('--texts', default=DEFAULT_TEXTS)
    ap.add_argument('--extra-texts', default=None)
    sub = ap.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('fill')
    f.add_argument('--inventory', action='append', required=True)
    f.add_argument('--accept')
    f.add_argument('--hopper-cache', help='JSON file; when given, a work the inventories do not match is looked up by its Perseus hopper document id (one request a second) and the cache is kept here')
    f.add_argument('--fuzzy-report')
    f.add_argument('--unmatched-report')
    f.add_argument('--dry-run', action='store_true')
    sub.add_parser('check')
    nn = sub.add_parser('none')
    nn.add_argument('--language', required=True, choices=LANGUAGES)
    nn.add_argument('--note', required=True)
    nn.add_argument('keys', nargs='+')
    lk = sub.add_parser('lookup')
    lk.add_argument('urns', nargs='+')
    args = ap.parse_args(argv)
    return {'fill': cmd_fill, 'check': cmd_check, 'lookup': cmd_lookup, 'none': cmd_none}[args.cmd](args)


if __name__ == '__main__':
    sys.exit(main())
