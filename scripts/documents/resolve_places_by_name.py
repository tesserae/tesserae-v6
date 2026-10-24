#!/usr/bin/env python3
"""Give documents with no usable Pleiades place one, from the place name they carry.

  resolve_places_by_name.py OUTDIR [--metadata PATH] [--points PATH] [--crosswalk PATH]
                            [--pleiades-dump PATH] [--gateway] [--min-gateway-docs N]
                            [--sample N --seed S] [--apply-to NEW_METADATA.db]

A document's point comes from its `pleiades_id`, or from its `place_tm_id` through the
Trismegistos-to-Pleiades crosswalk. All EDR inscriptions, a fifth of EDH and some papyri have
neither, only an `ancient_place` string. For each distinct string the script looks, in order of
trust, for

  a  siblings: other documents with the same name (after normalizing) that already have a
     Pleiades place with a point. Taken when one place holds at least 80 percent of them.
  b  an exact match of the name on the title of a Pleiades place, or, when no title matches,
     on one of the place's names (read from the local Pleiades dump, which holds the same
     names the place's JSON page does, so nothing is fetched). Only places attested in the
     Roman world count (a name or location that overlaps -300 to 500). A single such place is
     taken when the region of the documents does not contradict it.
  c  more than one place: those inconsistent with the documents' region (the spread of the
     points of resolved documents of that region) are dropped. If one remains it is taken.
     Otherwise, with --gateway, the free gateway model chooses among the candidates (every
     answer is logged). A name still ambiguous is left unresolved and listed.

Normalizing: accents and case are folded, punctuation dropped. A name is also tried without
"?", without ", bei ...", without " - Portus"-type suffixes and without a parenthesis, each only
as a further variant, so the base name has to resolve on its own. A name holding "/", a milestone's ", inter" (between two places) or none is
left alone ("unbekannt", "unknown location").

A document that already has a `pleiades_id`, or a crosswalk place, is never touched.

Writes OUTDIR/place_names_to_pleiades.tsv, OUTDIR/document_pleiades_fill.tsv, OUTDIR/coverage.json,
OUTDIR/unresolved_names.tsv and, with --sample, OUTDIR/hand_check_sample.tsv. With --apply-to the
`pleiades_id` of the filled documents is written into a COPY of the metadata database (never the
input, never under /var/www).
"""
import argparse
import collections
import csv
import gzip
import json
import math
import os
import random
import re
import shutil
import sqlite3
import sys
import unicodedata

PROD = '/var/www/tesseraev6_flask/data'
HOME = os.path.expanduser('~')
DEFAULT_META = os.path.join(PROD, 'documents', 'metadata.db')
DEFAULT_POINTS = os.path.join(HOME, 'tesserae-backups', 'events_proto', 'pleiades_points.tsv')
DEFAULT_CW = os.path.join(HOME, 'tesserae-docs', 'stage2', 'crosswalk', 'trismegistos_to_pleiades.tsv')
DEFAULT_DUMP = os.path.join(HOME, 'tesserae-docs', 'raw', 'pleiades', 'pleiades-places-latest.json.gz')

DOMINANCE = 0.8
ENVELOPE_FLOOR_KM = 300.0
ROMAN_START, ROMAN_END = -300, 500
NO_PLACE = {'unbekannt', 'unknown', 'unknown location', 'unbestimmt', 'ignotus', 'incertus'}


def fold(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c)).casefold()
    s = re.sub(r'[^\w\s]', ' ', s.replace('æ', 'ae').replace('œ', 'oe'))
    return ' '.join(s.split())


_BEI = re.compile(r',?\s*\b(bei|nahe|prope|near|ca\.?|aus|haud recte)\b.*$', re.I)
_EQUALS = re.compile(r'\(\s*=\s*([^)]+)\)')
_HONORIFIC = {'colonia', 'municipium', 'civitas', 'vicus'}
_SUFFIX = re.compile(r'\s+-\s+.*$')
_PAREN = re.compile(r'\s*\([^)]*\)')


def strip_chain(name):
    """The name as found, then the same with each decoration removed in turn (cumulatively)."""
    name = ' '.join((name or '').split())
    if not name:
        return []
    out = [name]
    cur = name
    for rx in (re.compile(r'\?'), _BEI, _SUFFIX, _PAREN):
        nxt = ' '.join(rx.sub('', cur).split()).strip(' ,;-')
        if nxt and nxt != cur:
            out.append(nxt)
            cur = nxt
    return dedupe(out)


def variants(name):
    """strip_chain plus the readings of "(= X)", a Latin plural ending (-ae to -a) and the bare name of a Colonia X."""
    out = strip_chain(name)
    if not out:
        return []
    m = _EQUALS.search(out[0])
    if m:
        out.insert(1, m.group(1).strip())
    last = out[-1]
    words = last.split()
    if len(words) >= 2 and fold(words[0]) in _HONORIFIC and len(words[-1]) >= 6:
        out.append(words[-1])
    for v in list(out[-2:]):
        if fold(v).endswith('ae') and len(v) > 5:
            out.append(fold(v)[:-2] + 'a')
    return dedupe(out)


def dedupe(out):
    seen, res = set(), []
    for v in out:
        k = fold(v)
        if k and k not in seen:
            seen.add(k)
            res.append(v)
    return res


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(a))


def load_points(path):
    pts = {}
    with open(path, encoding='utf-8') as f:
        for r in csv.DictReader(f, delimiter='\t'):
            try:
                pts[r['pleiades_id']] = (float(r['lat']), float(r['lon']), r['title'])
            except (ValueError, KeyError):
                pass
    return pts


def load_crosswalk(path):
    with open(path, encoding='utf-8') as f:
        return {str(r['tm_place_id']): r['pleiades_id'] for r in csv.DictReader(f, delimiter='\t')}


def roman_ok(place):
    for part in (place.get('locations') or []) + (place.get('names') or []):
        s, e = part.get('start'), part.get('end')
        if s is None and e is None:
            continue
        s = -10 ** 6 if s is None else s
        e = 10 ** 6 if e is None else e
        if s <= ROMAN_END and e >= ROMAN_START:
            return True
    return False


def iter_graph(path, chunk=1 << 22):
    """Yield the places of the dump's "@graph" array one at a time (the whole file does not fit a 4 GB cap)."""
    dec = json.JSONDecoder()
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        buf = ''
        while '"@graph"' not in buf:
            more = f.read(chunk)
            if not more:
                return
            buf += more
        pos = buf.index('[', buf.index('"@graph"')) + 1
        while True:
            while pos < len(buf) and buf[pos] in ' \n\r\t,':
                pos += 1
            if pos < len(buf) and buf[pos] == ']':
                return
            try:
                if pos >= len(buf):
                    raise json.JSONDecodeError('end', buf, pos)
                obj, end = dec.raw_decode(buf, pos)
            except json.JSONDecodeError:
                more = f.read(chunk)
                if not more:
                    return
                buf = buf[pos:] + more
                pos = 0
                continue
            yield obj
            pos = end


def build_place_index(dump_path, points, cache_path):
    """{id: {title, names, types, desc, roman}} for the places that have a point."""
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, encoding='utf-8') as f:
            return json.load(f)
    idx = {}
    for p in iter_graph(dump_path):
        pid = str(p.get('id'))
        if pid not in points:
            continue
        names = []
        for n in p.get('names') or []:
            for k in ('romanized', 'attested'):
                v = n.get(k)
                if v and v not in names:
                    names.append(v)
        idx[pid] = {'title': p.get('title') or '', 'names': names, 'types': p.get('placeTypes') or [],
                    'desc': (p.get('description') or '')[:300], 'roman': roman_ok(p)}
    if cache_path:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(idx, f, ensure_ascii=False)
    return idx


def sibling_votes(rows, points, cw):
    """{folded name variant: Counter(pleiades_id)} from documents that already have a point."""
    sib = collections.defaultdict(collections.Counter)
    for src, ancient, modern, region, pid, tm, n in rows:
        eff = pid or cw.get(str(tm))
        if not ancient or not eff or eff not in points:
            continue
        vs = strip_chain(ancient)
        for v in {vs[0], vs[-1]} if vs else ():
            sib[fold(v)][eff] += n
    return sib


def region_envelopes(rows, points, cw, min_docs=20):
    """{region: (lat, lon, radius_km)} from resolved documents: median point, 80th percentile distance (a few wrong ids in a region must not widen it)."""
    pts = collections.defaultdict(list)
    for src, ancient, modern, region, pid, tm, n in rows:
        eff = pid or cw.get(str(tm))
        if region and eff in points:
            pts[region.rstrip('?').strip()].extend([points[eff][:2]] * min(n, 50))
    env = {}
    for reg, ps in pts.items():
        if len(ps) < min_docs:
            continue
        la = sorted(p[0] for p in ps)[len(ps) // 2]
        lo = sorted(p[1] for p in ps)[len(ps) // 2]
        ds = sorted(haversine_km(la, lo, p[0], p[1]) for p in ps)
        env[reg] = (la, lo, ds[int(0.8 * (len(ds) - 1))])
    return env


def in_envelope(env, region, pt):
    e = env.get((region or '').rstrip('?').strip())
    if not e:
        return True
    return haversine_km(e[0], e[1], pt[0], pt[1]) <= max(ENVELOPE_FLOOR_KM, 1.5 * e[2])


def title_name_candidates(key, title_ix, name_ix, places):
    """Roman-world places whose title or one of whose names is `key`, title matches first.
    Returns (ids, how) where how is 'title' when every one matched by title, else 'name'."""
    by_title = [p for p in title_ix.get(key, ()) if places[p]['roman']]
    by_name = [p for p in name_ix.get(key, ()) if places[p]['roman'] and p not in by_title]
    return by_title + by_name, ('title' if by_title and not by_name else 'name' if by_name and not by_title else 'title+name')


def supports(places, pid, keys):
    """True when the place's title or one of its names holds all the words of one of the folded name variants."""
    pl = places.get(pid)
    if not pl:
        return False
    for n in [pl['title']] + pl['names']:
        words = set(fold(n).split())
        for k in keys:
            if k and set(k.split()) <= words:
                return True
    return False


def gateway_choice(cfg, name, region, modern, cands, places, points, log):
    import urllib.request
    lines = []
    for p in cands:
        pl = places[p]
        lines.append('%s | %s | %s | %.2f N %.2f E | %s' % (p, pl['title'], ', '.join(pl['types']),
                                                           points[p][0], points[p][1], pl['desc'][:200].replace('\n', ' ')))
    prompt = ('An ancient inscription or papyrus record gives its findspot as "%s". Region: %s. Modern place: %s.\n'
              'Which Pleiades place is meant? Candidates (id | title | types | point | description):\n%s\n'
              'Answer with the id of one candidate, or NONE if you cannot tell which one is meant. Answer with the id or NONE only.'
              % (name, region or 'unknown', modern or 'unknown', '\n'.join(lines)))
    body = json.dumps({'model': cfg['model'], 'temperature': 0, 'max_tokens': 40,
                       'messages': [{'role': 'user', 'content': prompt}],
                       'chat_template_kwargs': {'enable_thinking': False}}).encode()
    req = urllib.request.Request(cfg['url'].rstrip('/') + '/chat/completions' if cfg['url'].rstrip('/').endswith('/v1')
                                 else cfg['url'].rstrip('/') + '/v1/chat/completions',
                                 data=body, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + cfg['key']})
    ans = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as x:
                d = json.loads(x.read())
            ans = (d['choices'][0]['message']['content'] or '').strip()
            break
        except Exception as e:  # noqa: BLE001
            ans = None
            err = type(e).__name__
    log.write(json.dumps({'name': name, 'region': region, 'modern': modern, 'candidates': cands, 'answer': ans},
                         ensure_ascii=False) + '\n')
    log.flush()
    if not ans:
        return None
    m = re.search(r'\d{3,}', ans)
    return m.group(0) if m and m.group(0) in cands else None


def load_gateway_cfg():
    from dotenv import dotenv_values
    v = dotenv_values(os.path.join(PROD, '..', '.env'))
    if not (v.get('TESSERAE_LLM_URL') and v.get('TESSERAE_LLM_MODEL') and v.get('TESSERAE_LLM_API_KEY')):
        sys.exit('gateway settings missing')
    return {'url': v['TESSERAE_LLM_URL'], 'model': v['TESSERAE_LLM_MODEL'], 'key': v['TESSERAE_LLM_API_KEY']}


def resolve_names(unresolved, sib, places, title_ix, name_ix, points, env, gw=None, min_gateway_docs=3, log=None):
    """unresolved: {(name, region): {'n': docs, 'region': the region, 'modern': most common modern place}}.
    Returns ({name: (normalized, pid, source, note)}, [(name, n, reason)])."""
    res, left = {}, []
    for nk, info in sorted(unresolved.items(), key=lambda kv: -kv[1]['n']):
        name = nk[0]
        vs = variants(name)
        if not vs or fold(name) in NO_PLACE or '/' in name or re.search(r',\s*inter\b', name):
            left.append((name, info['n'], 'no usable name', info['region']))
            continue
        region, modern = info['region'], info['modern']
        done = False
        reason = 'no match'
        pending = None  # candidates to settle at the end
        for v in vs:
            key = fold(v)
            votes = sib.get(key)
            if votes:
                # an id from another province's namesake is dropped when the region of these documents excludes it
                votes = collections.Counter({p: n for p, n in votes.items() if in_envelope(env, region, points[p])})
            if votes:
                pid, top = votes.most_common(1)[0]
                if top / sum(votes.values()) >= DOMINANCE:
                    # siblings carry an id from another source, and the crosswalk behind it is not always right
                    # (EDH files its Ostia stones under Roma). The id stands when the place has the name among its
                    # own; otherwise one other place that has it wins.
                    named, v2s = [], []
                    for v2 in vs:
                        named, _how = title_name_candidates(fold(v2), title_ix, name_ix, places)
                        if named:
                            v2s = [fold(v2)]  # the support test uses the most specific variant that names a place
                            break
                    named = list(dict.fromkeys(named))
                    if named and pid not in named and not supports(places, pid, v2s):
                        ok = [c for c in named if in_envelope(env, region, points[c])]
                        if len(ok) == 1:
                            res[nk] = (key, ok[0], 'b', 'name of this place, siblings %d of %d say %s' % (top, sum(votes.values()), pid))
                            done = True
                            break
                        pending = (key, list(dict.fromkeys([pid] + (ok or named))), 'a-conflict')
                        reason = 'siblings and name disagree'
                        break
                    res[nk] = (key, pid, 'a', 'siblings %d of %d' % (top, sum(votes.values())))
                    done = True
                    break
                pending = (key, [p for p, _ in votes.most_common(6)], 'a-split')
                reason = 'siblings split'
                break
        if done:
            continue
        if pending is None:
            for v in vs:
                key = fold(v)
                cands, how = title_name_candidates(key, title_ix, name_ix, places)
                if cands:
                    pending = (key, cands, how)
                    break
        if pending is None:
            left.append((name, info['n'], reason, info['region']))
            continue
        key, cands, how = pending
        cands = list(dict.fromkeys(cands))
        if len(cands) == 1:
            p = cands[0]
            if in_envelope(env, region, points[p]):
                res[nk] = (key, p, 'b', 'one place by ' + how)
            elif gw and info['n'] >= min_gateway_docs and gateway_choice(gw, name, region, modern, [p], places, points, log):
                res[nk] = (key, p, 'c', 'one place outside the region spread, model confirmed')
            else:
                left.append((name, info['n'], 'one candidate outside its region', info['region']))
            continue
        kept = [p for p in cands if in_envelope(env, region, points[p])]
        if len(kept) == 1:
            res[nk] = (key, kept[0], 'c', 'region leaves one of %d' % len(cands))
            continue
        if not kept:
            left.append((name, info['n'], 'candidates all outside region', info['region']))
            continue
        if gw and len(kept) <= 8 and info['n'] >= min_gateway_docs:
            pick = gateway_choice(gw, name, region, modern, kept, places, points, log)
            if pick:
                res[nk] = (key, pick, 'c', 'gateway model chose from %d' % len(kept))
                continue
            left.append((name, info['n'], 'gateway: none chosen among %d' % len(kept), info['region']))
            continue
        left.append((name, info['n'], 'ambiguous among %d' % len(kept), info['region']))
    return res, left


def effective(row_pid, tm, cw):
    return row_pid or cw.get(str(tm))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('outdir')
    ap.add_argument('--metadata', default=DEFAULT_META)
    ap.add_argument('--points', default=DEFAULT_POINTS)
    ap.add_argument('--crosswalk', default=DEFAULT_CW)
    ap.add_argument('--pleiades-dump', default=DEFAULT_DUMP)
    ap.add_argument('--gateway', action='store_true')
    ap.add_argument('--min-gateway-docs', type=int, default=3)
    ap.add_argument('--sample', type=int, default=0)
    ap.add_argument('--seed', type=int, default=1024)
    ap.add_argument('--apply-to', default=None)
    a = ap.parse_args(argv)
    os.makedirs(a.outdir, exist_ok=True)

    points = load_points(a.points)
    cw = load_crosswalk(a.crosswalk)
    places = build_place_index(a.pleiades_dump, points, os.path.join(a.outdir, 'pleiades_index.json'))
    title_ix, name_ix = collections.defaultdict(list), collections.defaultdict(list)
    for pid, pl in places.items():
        title_ix[fold(pl['title'])].append(pid)
        for n in pl['names']:
            if pid not in name_ix[fold(n)]:
                name_ix[fold(n)].append(pid)

    meta = sqlite3.connect('file:%s?mode=ro' % a.metadata, uri=True)
    rows = meta.execute("SELECT source, ancient_place, modern_place, region, pleiades_id, place_tm_id, COUNT(*) "
                        "FROM documents GROUP BY 1,2,3,4,5,6").fetchall()
    sib = sibling_votes(rows, points, cw)
    env = region_envelopes(rows, points, cw)

    unresolved = {}
    mod_c = collections.defaultdict(collections.Counter)
    docs_by = collections.Counter()
    for src, ancient, modern, region, pid, tm, n in rows:
        if effective(pid, tm, cw) or not ancient:
            continue
        k = (ancient, region or '')
        docs_by[k] += n
        if modern:
            mod_c[k][modern] += n
    for k, n in docs_by.items():
        unresolved[k] = {'n': n, 'region': k[1] or None, 'modern': mod_c[k].most_common(1)[0][0] if mod_c[k] else None}

    gw = load_gateway_cfg() if a.gateway else None
    log = open(os.path.join(a.outdir, 'gateway_answers.jsonl'), 'a', encoding='utf-8') if gw else None
    # Pass 1 with the regions' spread from documents that already have a point; pass 2 with the spread widened by the
    # pass-1 results, because EDR's regions (Regio I to XI) appear in no document that already has a point.
    res, left = resolve_names(unresolved, sib, places, title_ix, name_ix, points, env, None, a.min_gateway_docs, None)
    rows2 = list(rows) + [('pass1', n[0], None, unresolved[n]['region'], res[n][1], None, unresolved[n]['n']) for n in res]
    env = region_envelopes(rows2, points, cw)
    res, left = resolve_names(unresolved, sib, places, title_ix, name_ix, points, env, gw, a.min_gateway_docs, log)

    with open(os.path.join(a.outdir, 'place_names_to_pleiades.tsv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter='\t')
        w.writerow(['name', 'region', 'normalized', 'pleiades_id', 'lat', 'lon', 'source', 'documents', 'pleiades_title', 'note'])
        for nk, (key, pid, src, note) in sorted(res.items(), key=lambda kv: -unresolved[kv[0]]['n']):
            w.writerow([nk[0], nk[1], key, pid, points[pid][0], points[pid][1], src, unresolved[nk]['n'], places[pid]['title'] if pid in places else points[pid][2], note])
    with open(os.path.join(a.outdir, 'unresolved_names.tsv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter='\t')
        w.writerow(['name', 'documents', 'reason', 'region'])
        for r in sorted(left, key=lambda r: -r[1]):
            w.writerow(r)

    # per-document fill
    fill, by_src, total_src = [], collections.Counter(), collections.Counter()
    before_id, before_pt = collections.Counter(), collections.Counter()
    for did, src, ancient, region, pid, tm in meta.execute('SELECT id, source, ancient_place, region, pleiades_id, place_tm_id FROM documents'):
        total_src[src] += 1
        eff = effective(pid, tm, cw)
        if eff:
            before_id[src] += 1
        if eff in points:
            before_pt[src] += 1
        if not eff and (ancient, region or '') in res:
            fill.append((did, res[(ancient, region or '')][1], res[(ancient, region or '')][2], src))
            by_src[src] += 1
    with open(os.path.join(a.outdir, 'document_pleiades_fill.tsv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter='\t')
        w.writerow(['doc_id', 'pleiades_id', 'how'])
        for did, pid, how, _ in fill:
            w.writerow([did, pid, how])
    by_how = collections.Counter(h for _, _, h, _ in fill)
    cov = {'documents': sum(total_src.values()),
           'with_id_or_crosswalk_before': dict(before_id), 'with_point_before': dict(before_pt),
           'total_by_source': dict(total_src), 'filled_by_source': dict(by_src), 'filled_by_how': dict(by_how),
           'with_point_after': {s: before_pt[s] + sum(1 for d, p, h, ss in fill if ss == s and p in points) for s in total_src},
           'names_resolved': len(res), 'names_unresolved': len(left), 'documents_filled': len(fill)}
    with open(os.path.join(a.outdir, 'coverage.json'), 'w') as f:
        json.dump(cov, f, indent=1, ensure_ascii=False)
    print(json.dumps(cov, indent=1, ensure_ascii=False))
    print('top unresolved:')
    for r in sorted(left, key=lambda r: -r[1])[:30]:
        print('  %6d  %s  (%s) [%s]' % (r[1], r[0], r[2], r[3]))

    if a.sample:
        rng = random.Random(a.seed)
        pool = {n: unresolved[n]['n'] for n in res}
        chosen = []
        while pool and len(chosen) < a.sample:
            tot = sum(pool.values())
            x = rng.random() * tot
            acc = 0
            for n in sorted(pool):
                acc += pool[n]
                if acc >= x:
                    chosen.append(n)
                    del pool[n]
                    break
        with open(os.path.join(a.outdir, 'hand_check_sample.tsv'), 'w', encoding='utf-8', newline='') as f:
            w = csv.writer(f, delimiter='\t')
            w.writerow(['name', 'documents', 'pleiades_id', 'pleiades_title', 'types', 'lat', 'lon', 'source', 'region', 'modern_place', 'description'])
            for n in chosen:
                pid = res[n][1]
                w.writerow([n[0], unresolved[n]['n'], pid, places[pid]['title'], ','.join(places[pid]['types']), points[pid][0], points[pid][1],
                            res[n][2], unresolved[n]['region'], unresolved[n]['modern'], places[pid]['desc'][:200]])

    if a.apply_to:
        out = os.path.abspath(a.apply_to)
        if out == os.path.abspath(a.metadata) or os.path.realpath(out).startswith('/var/www'):
            sys.exit('--apply-to must be a copy outside /var/www')
        shutil.copyfile(a.metadata, out)
        con = sqlite3.connect(out)
        n0 = con.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
        n = 0
        for did, pid, how, src in fill:
            c = con.execute("UPDATE documents SET pleiades_id = ? WHERE id = ? AND (pleiades_id IS NULL OR pleiades_id = '')", (pid, did))
            n += c.rowcount
        con.commit()
        n1 = con.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
        con.execute('VACUUM')
        con.close()
        print('applied to %s: rows %d -> %d, pleiades_id filled on %d documents' % (out, n0, n1, n))
        if n0 != n1:
            sys.exit('row count changed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
