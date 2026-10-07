"""Build the per-window proper-name index behind Similar Passages' "Same people and places" group.

Usage: python scripts/corpus/build_window_names.py OUT.db   (then swap OUT.db in as data/passage_index/window_names.db)
Run after any change to the passage index (window_texts.db); about 13 minutes, under 4 GB.

Pass 1: over every la/grc/en window, count for each word form how often it is capitalised
mid-line versus written in lower case. A form is a NAME when it is capitalised in at least
90 percent of its mid-line uses and seen capitalised at least 3 times. This keeps Celaenae
and Marsyas and drops Itaque, Fons and media.
Pass 2: map each window to the set of name KEYS it contains (key = accent-stripped,
Greek transliterated, ae->ai, c->k, ph->f, y->u, first 5 letters), with document frequency.
"""
import json, re, sqlite3, time, unicodedata, collections, sys
import os
IDX = os.environ.get('PASSAGE_INDEX_DIR', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'passage_index'))
OUT = sys.argv[1]
GR = {'α':'a','β':'b','γ':'g','δ':'d','ε':'e','ζ':'z','η':'e','θ':'th','ι':'i','κ':'k','λ':'l','μ':'m','ν':'n','ξ':'ks','ο':'o','π':'p','ρ':'r','σ':'s','ς':'s','τ':'t','υ':'u','φ':'f','χ':'kh','ψ':'ps','ω':'o'}
def strip(s): return ''.join(c for c in unicodedata.normalize('NFD', s) if not unicodedata.combining(c))
def key(tok):
    t = ''.join(GR.get(c, c) for c in strip(tok).lower()); t = re.sub(r'[^a-z]', '', t)
    for a, b in (('ph','f'),('th','t'),('ch','kh'),('ae','ai'),('oe','oi'),('c','k'),('y','u'),('x','ks'),('j','i'),('v','u')): t = t.replace(a, b)
    return t[:5] if len(t) >= 4 else None
TOK = re.compile(r"[^\W\d_]+", re.U)
END = re.compile(r'[.!?;:·;]\s*$')
def tokens(text):
    """(form, midline) for every word; midline False at a line start or after sentence punctuation."""
    for line in (text or '').split('\n'):
        first = True
        for m in TOK.finditer(line):
            w = m.group(0); before = line[max(0, m.start()-3):m.start()]
            mid = not first and not END.search(before)
            first = False
            yield w, mid
t0 = time.time()
con = sqlite3.connect(f'file:{IDX}/window_texts.db?mode=ro', uri=True)
LANGS = ('la', 'grc', 'en')
cap = collections.Counter(); low = collections.Counter(); fcap = collections.Counter(); flow = collections.Counter()
for (lang, text) in con.execute("select language, text from window_texts where language in ('la','grc','en')"):
    for w, mid in tokens(text):
        if not mid: continue
        k = key(w)
        if not k: continue
        f = strip(w).lower()
        if w[0].isupper(): cap[(lang, k)] += 1; fcap[(lang, f)] += 1
        else: low[(lang, k)] += 1; flow[(lang, f)] += 1
names = {lk for lk, n in cap.items() if n >= 3 and n >= 0.85 * (n + low[lk])}
fnames = {lf for lf, n in fcap.items() if n >= 2 and n >= 0.9 * (n + flow[lf]) and len(lf[1]) >= 4}
print('form-level names', len(fnames))
print(f'pass 1 {time.time()-t0:.0f}s: {len(names)} name keys', flush=True)
for lg, pf in (('grc','κελαιναι'),('grc','κελαιναις'),('la','rubiconem'),('la','rubicon'),('la','marsyas')):
    print('  form', lg, pf, 'name' if (lg,pf) in fnames else 'not', fcap[(lg,pf)], flow[(lg,pf)])
for lg, pk in (('la','kelai'),('grc','kelai'),('la','marsu'),('la','klean'),('grc','klean'),('la','aleks'),('la','itaqu'),('la','media'),('la','fons'),('la','faeto'),('la','dareu'),('la','rubik'),('grc','aleks')):
    print('  ', lg, pk, 'name' if (lg,pk) in names else 'not a name', cap[(lg,pk)], low[(lg,pk)])
out = sqlite3.connect(OUT); out.execute('drop table if exists window_names'); out.execute('create table window_names (id text, k text, form text)')
df = collections.Counter(); n = 0; batch = []
for wid, lang, text in con.execute("select id, language, text from window_texts where language in ('la','grc','en')"):
    ks = {}
    for w, mid in tokens(text):
        if w[0].isupper():
            k = key(w)
            if k and ((lang, k) in names or (lang, strip(w).lower()) in fnames): ks.setdefault(k, w)
    for k, form in ks.items(): batch.append((wid, k, form)); df[k] += 1
    n += 1
    if len(batch) > 200000: out.executemany('insert into window_names values (?,?,?)', batch); batch = []
out.executemany('insert into window_names values (?,?,?)', batch)
out.execute('create index ix_wn_id on window_names(id)'); out.execute('create index ix_wn_k on window_names(k)')
out.execute('drop table if exists name_df'); out.execute('create table name_df (k text primary key, df integer)')
out.executemany('insert into name_df values (?,?)', df.items()); out.execute('create table if not exists meta (key text, value text)')
out.execute("insert into meta values ('windows', ?)", (str(n),)); out.commit()
print(f'pass 2 {time.time()-t0:.0f}s: {n} windows, {sum(df.values())} window-name pairs, {len(df)} keys')
open(OUT + '.done', 'w').write('ok')
