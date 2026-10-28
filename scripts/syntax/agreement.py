"""Compare a new parse of lines already in a syntax database with the stored rows.

  agreement.py todo --db DB --texts DIR --files a.tess b.tess --per-file 400 --todo T.jsonl --meta M.json
  agreement.py compare --db DB --meta M.json --out PARSED.jsonl
Only lines whose tag is also a stored ref are used (so the stored row is the
parse of that very line)."""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from syntax_gap_lib import *  # noqa
import difflib


def cmd_todo(a):
    conn = open_ro(a.db)
    names = dict(conn.execute('SELECT filename, text_id FROM texts'))
    meta, n = [], 0
    with open(a.todo, 'w', encoding='utf-8') as out:
        for f in a.files:
            tl = read_tess(os.path.join(a.texts, f))
            stored = {r: (t,) for r, t in conn.execute('SELECT ref, tokens FROM syntax WHERE text_id=?', (names[f],))}
            usable = [(t, x) for t, x in tl if t in stored and norm_key(x) == tokens_key(stored[t][0])]
            step = max(1, len(usable) // a.per_file)
            for t, x in usable[::step][:a.per_file]:
                out.write(json.dumps({'id': n, 'text': x}, ensure_ascii=False) + '\n')
                meta.append([n, f, t])
                n += 1
            print(f, 'usable', len(usable), 'sampled', len(usable[::step][:a.per_file]))
    json.dump(meta, open(a.meta, 'w'))


def cmd_compare(a):
    conn = open_ro(a.db)
    names = dict(conn.execute('SELECT filename, text_id FROM texts'))
    meta = {i: (f, t) for i, f, t in json.load(open(a.meta))}
    new = {}
    for line in open(a.out, encoding='utf-8'):
        o = json.loads(line)
        new[o['id']] = o
    per = {}
    for i, (f, t) in meta.items():
        if i not in new:
            continue
        r = conn.execute('SELECT tokens, lemmas, upos, heads, deprels FROM syntax WHERE text_id=? AND ref=?', (names[f], t)).fetchone()
        old = dict(zip(('tokens', 'lemmas', 'upos', 'heads', 'deprels'), map(json.loads, r)))
        n = new[i]
        s = per.setdefault(f, dict(lines=0, same_tok_lines=0, old_tok=0, matched_tok=0, aligned=0, lemma=0, upos=0, head=0, deprel=0, las=0))
        s['lines'] += 1
        s['old_tok'] += len(old['tokens'])
        sm = difflib.SequenceMatcher(None, old['tokens'], n['tokens'], autojunk=False)
        s['matched_tok'] += sum(b.size for b in sm.get_matching_blocks())
        if old['tokens'] == n['tokens']:
            s['same_tok_lines'] += 1
            for k in range(len(old['tokens'])):
                s['aligned'] += 1
                s['lemma'] += old['lemmas'][k] == n['lemmas'][k]
                s['upos'] += old['upos'][k] == n['upos'][k]
                h = old['heads'][k] == n['heads'][k]
                d = old['deprels'][k] == n['deprels'][k]
                s['head'] += h
                s['deprel'] += d
                s['las'] += h and d
    tot = {}
    for f, s in per.items():
        print(f, {k: s[k] for k in ('lines', 'same_tok_lines')},
              'tokens %.4f' % (s['matched_tok'] / max(1, s['old_tok'])),
              'lemma %.4f upos %.4f head(UAS) %.4f deprel %.4f LAS %.4f' % tuple(s[k] / max(1, s['aligned']) for k in ('lemma', 'upos', 'head', 'deprel', 'las')))
        for k, v in s.items():
            tot[k] = tot.get(k, 0) + v
    s = tot
    print('ALL', {k: s[k] for k in ('lines', 'same_tok_lines')},
          'line-level token-identical %.4f' % (s['same_tok_lines'] / max(1, s['lines'])),
          'tokens %.4f' % (s['matched_tok'] / max(1, s['old_tok'])),
          'lemma %.4f upos %.4f head(UAS) %.4f deprel %.4f LAS %.4f' % tuple(s[k] / max(1, s['aligned']) for k in ('lemma', 'upos', 'head', 'deprel', 'las')))


ap = argparse.ArgumentParser()
sp = ap.add_subparsers(dest='cmd', required=True)
t = sp.add_parser('todo')
t.add_argument('--db'); t.add_argument('--texts'); t.add_argument('--files', nargs='+')
t.add_argument('--per-file', type=int, default=400); t.add_argument('--todo'); t.add_argument('--meta')
c = sp.add_parser('compare')
c.add_argument('--db'); c.add_argument('--meta'); c.add_argument('--out')
a = ap.parse_args()
cmd_todo(a) if a.cmd == 'todo' else cmd_compare(a)
