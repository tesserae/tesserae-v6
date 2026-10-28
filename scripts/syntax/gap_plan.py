"""Plan the syntax parse gap for one language (no database is changed).

For every live .tess file of the language it decides, line by line:
  rekey   rows already stored under a ref that is not the file's tag get the tag
          (the ref rule, see syntax_gap_lib.py);
  copy    a line with no row takes the row of the same text from a related
          source: the whole work of a part file, the parts of a whole work, or
          a stored file that no longer exists on disk and holds at least half
          the file's lines (a rename);
  parse   a line still without a row is to be parsed;
  exclude a file under the restricted registry or from a source whose terms bar
          online copies is not parsed (rows may still be copied).
Writes PLAN.json and TODO.jsonl (one object per distinct text to parse).

  python scripts/syntax/gap_plan.py --lang la --db DB --texts DIR --out-dir DIR
"""
import argparse, collections, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'corpus'))
from syntax_gap_lib import *  # noqa


def natural(s):
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', s)]


def exclusion_reasons(texts_dir, files):
    """{file: reason} for files that must not be parsed."""
    import build_text_archives as bta
    from backend import restricted_texts
    index = bta.SourceIndex(bta.load_sources(ROOT))
    out = {}
    for f in files:
        if restricted_texts.is_restricted(f):
            out[f] = 'restricted registry (data/restricted_texts.json)'
            continue
        _, _, why = bta.manifest_row(os.path.join(texts_dir, f), f, index, 'x')
        if why:
            out[f] = 'source terms: ' + why
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lang', required=True)
    ap.add_argument('--db', required=True)
    ap.add_argument('--texts', required=True)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--orphan-min', type=float, default=0.5)
    ap.add_argument('--include-excluded', action='store_true',
                    help='parse the restricted and withheld texts too (local parsing sends nothing out; the 2026-10-28 decision)')
    ap.add_argument('--extend-todo', action='store_true',
                    help='keep the ids of an existing todo file and give new texts new ids, so earlier parse output stays valid')
    a = ap.parse_args()
    conn = open_ro(a.db)
    rows = load_rows(conn)
    files = sorted(f for f in os.listdir(a.texts) if f.endswith('.tess'))
    live = set(files)
    orphans = sorted(f for f in rows if f not in live)
    orphan_keys = collections.defaultdict(set)
    for fn in orphans:
        for _, k in rows[fn]:
            if k:
                orphan_keys[k].add(fn)
    parts_of = collections.defaultdict(list)
    for fn in rows:
        m = PART_RE.match(fn)
        if m:
            parts_of[m.group('base') + '.tess'].append(fn)
    for k in parts_of:
        parts_of[k].sort(key=natural)

    excluded = exclusion_reasons(a.texts, files)
    if a.include_excluded:
        excluded = {}
    plan = {'lang': a.lang, 'live': len(files), 'parsed_before': [], 'rekey': {}, 'copy': {}, 'parse': {},
            'excluded': excluded, 'empty': [], 'sources_used': {}, 'orphans': len(orphans), 'dup_tags': {}}
    texts_to_parse = {}
    for f in files:
        tl = read_tess(os.path.join(a.texts, f))
        if not tl:
            plan['empty'].append(f)
            continue
        tags_all = [t for t, _ in tl]
        if len(set(tags_all)) != len(tags_all):
            plan['dup_tags'][f] = len(tags_all) - len(set(tags_all))
        have = f in rows
        refs = set()
        if have:
            plan['parsed_before'].append(f)
            rs = rows[f]
            refs = {r for r, _ in rs}
            tagset = set(tags_all)
            bad_rows = [(r, k) for r, k in rs if r not in tagset]
            lone = [(t, x) for t, x in tl if t not in refs]
            if bad_rows and lone:
                m, _ = align(lone, bad_rows, prefer_same_ref=False)
                if m:
                    plan['rekey'][f] = m
                    refs |= set(m)
        need = [(t, x) for t, x in tl if t not in refs]
        if not need:
            continue
        # related sources
        pool, srcs = [], []
        m = PART_RE.match(f)
        if m and (m.group('base') + '.tess') in rows and (m.group('base') + '.tess') != f:
            srcs.append(m.group('base') + '.tess')
        if f in parts_of:
            srcs.extend(p for p in parts_of[f] if p != f)
        votes = collections.Counter()
        for t, x in need:
            for fn in orphan_keys.get(norm_key(x), ()):
                votes[fn] += 1
        if votes:
            best, n = votes.most_common(1)[0]
            if n / len(need) >= a.orphan_min and best not in srcs and best != f:
                srcs.append(best)
        for sfn in srcs:
            pool.extend((sfn + '\x00' + r, k) for r, k in rows[sfn])
        mp, un = ({}, [t for t, _ in need])
        if pool:
            mp, un = align(need, pool, prefer_same_ref=False)
        if mp:
            plan['copy'][f] = {t: v.split('\x00', 1) for t, v in mp.items()}
            for v in mp.values():
                sfn = v.split('\x00', 1)[0]
                plan['sources_used'].setdefault(f, {})
                plan['sources_used'][f][sfn] = plan['sources_used'][f].get(sfn, 0) + 1
        unset = set(un)
        left = [(t, x) for t, x in need if t in unset]
        # a repeated tag keeps its first line only
        seen = set()
        left2 = []
        for t, x in left:
            if t in seen:
                continue
            seen.add(t)
            left2.append((t, x))
        if left2 and f not in excluded:
            plan['parse'][f] = [t for t, _ in left2]
            for t, x in left2:
                texts_to_parse.setdefault(x, None)
    # distinct texts, shorter first so a chunk batches similar lengths
    order = sorted(texts_to_parse, key=lambda x: (len(x), x))
    todo_path = os.path.join(a.out_dir, f'todo_{a.lang}.jsonl')
    old = []
    if a.extend_todo and os.path.exists(todo_path):
        old = [json.loads(line) for line in open(todo_path, encoding='utf-8')]
    known = {o['text'] for o in old}
    nxt = max((o['id'] for o in old), default=-1) + 1
    new = [x for x in order if x not in known]
    with open(todo_path, 'w', encoding='utf-8') as fh:
        for o in old:
            fh.write(json.dumps(o, ensure_ascii=False) + '\n')
        for x in new:
            fh.write(json.dumps({'id': nxt, 'text': x}, ensure_ascii=False) + '\n')
            nxt += 1
    order = [o['text'] for o in old if o['text'] in texts_to_parse] + new
    plan['todo_texts'] = len(order)
    json.dump(plan, open(os.path.join(a.out_dir, f'plan_{a.lang}.json'), 'w'), ensure_ascii=False)
    n_copy = sum(len(v) for v in plan['copy'].values())
    n_parse = sum(len(v) for v in plan['parse'].values())
    new_files = [f for f in plan['parse'] if f not in rows]
    print(f"{a.lang}: live {len(files)}, parsed before {len(plan['parsed_before'])}, rekey {sum(len(v) for v in plan['rekey'].values())} lines in {len(plan['rekey'])} files, "
          f"copy {n_copy} lines in {len(plan['copy'])} files, to parse {n_parse} lines in {len(plan['parse'])} files "
          f"({len(order)} distinct texts), excluded {len(excluded)}, empty {len(plan['empty'])}, dup-tag files {len(plan['dup_tags'])}")


main()
