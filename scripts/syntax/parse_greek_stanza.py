"""Parse Greek lines with Stanza's default Ancient Greek models, in resumable chunks.

Follows evaluation/scripts/build_greek_syntax_db.py, which built syntax_greek.db
on 2026-03-09. That script calls stanza.Pipeline("grc", processors="tokenize,
pos,lemma,depparse") with no package, so Stanza used its DEFAULT package for
Ancient Greek, which is `perseus` (tokenize perseus, pos/lemma/depparse
perseus_nocharlm; the model files in ~/stanza_resources are dated 2026-03-07).
The database's syntax_source row says "grc_proiel", but the rows were not made
with the proiel package: its tokenizer and the stored tokens disagree, the
perseus ones agree (see scripts/syntax/README.md). Same fallbacks as that
script: lemma falls back to the token text, upos to "X", deprel to "dep",
feats to "".

Input and output are the JSONL files described in parse_latinpipe.py. A line
the tokenizer splits into several sentences is stored as one row. Heads stay
sentence-local, as in the March build (about one stored row in four has more
than one root for that reason); --shift-heads makes them line-wide instead.

  python parse_greek_stanza.py --resources DIR --todo todo.jsonl --out out.jsonl --budget 420
"""
import argparse, json, os, sys, time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--resources', required=True, help='stanza_resources directory holding the grc models')
    ap.add_argument('--package', default='default', help='stanza package; the March build used the default (perseus)')
    ap.add_argument('--todo', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--budget', type=float, default=420)
    ap.add_argument('--threads', type=int, default=16)
    ap.add_argument('--lines-per-call', type=int, default=200)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--shard', default='0/1', help='i/n: parse only lines whose id mod n is i, so n jobs can share one todo file')
    ap.add_argument('--shift-heads', action='store_true', help='shift the heads of later sentences of a line (the March build did not)')
    a = ap.parse_args()
    t_start = time.time()
    done = set()
    if os.path.exists(a.out):
        for line in open(a.out, encoding='utf-8'):
            try:
                done.add(json.loads(line)['id'])
            except ValueError:
                pass
    si, sn = map(int, a.shard.split('/'))
    todo = [o for o in map(json.loads, open(a.todo, encoding='utf-8')) if o['id'] not in done and o['id'] % sn == si]
    if a.limit:
        todo = todo[:a.limit]
    print(f'todo {len(todo)} lines, {len(done)} already done', flush=True)
    if not todo:
        return
    import torch
    torch.set_num_threads(a.threads)
    import stanza
    nlp = stanza.Pipeline('grc', package=a.package, processors='tokenize,pos,lemma,depparse',
                          dir=a.resources, download_method=None, use_gpu=False, verbose=False)
    print(f'pipeline ready after {time.time() - t_start:.0f}s', flush=True)
    out = open(a.out, 'a', encoding='utf-8')
    t0 = time.time()
    pos = n_done = n_tok = 0
    while pos < len(todo) and time.time() - t_start < a.budget:
        chunk = todo[pos:pos + a.lines_per_call]
        pos += len(chunk)
        docs = nlp([stanza.Document([], text=o['text']) for o in chunk])
        for o, doc in zip(chunk, docs):
            row = {'id': o['id'], 'tokens': [], 'lemmas': [], 'upos': [], 'heads': [], 'deprels': [], 'feats': []}
            off = 0
            for sent in doc.sentences:
                for w in sent.words:
                    row['tokens'].append(w.text)
                    row['lemmas'].append(w.lemma if w.lemma else w.text)
                    row['upos'].append(w.upos if w.upos else 'X')
                    row['heads'].append((w.head + off) if (w.head and a.shift_heads) else (w.head or 0))
                    row['deprels'].append(w.deprel if w.deprel else 'dep')
                    row['feats'].append(w.feats or '')
                off += len(sent.words)
            if row['tokens']:
                out.write(json.dumps(row, ensure_ascii=False) + '\n')
                n_done += 1
                n_tok += len(row['tokens'])
        out.flush()
    dt = time.time() - t0
    print(f'parsed {n_done} lines, {n_tok} tokens in {dt:.0f}s: {n_done / max(dt, 1e-9):.1f} lines/s; '
          f'{len(todo) - pos} lines still to do', flush=True)


if __name__ == '__main__':
    main()
