"""Build the per-window proper-name index behind Similar Passages' "Same people and places" group.

Usage: python scripts/corpus/build_window_names.py OUT.db   (then swap OUT.db in as data/passage_index/window_names.db)
Run after any change to the passage index (window_texts.db); under 4 GB.

Latin, Greek and English (UNCHANGED, byte-for-byte the same names as before this script read
other scripts too):
Pass 1: over every la/grc/en window, count for each word form how often it is capitalised
mid-line versus written in lower case. A form is a NAME when it is capitalised in at least
90 percent of its mid-line uses and seen capitalised at least 3 times. This keeps Celaenae
and Marsyas and drops Itaque, Fons and media.
Pass 2: map each window to the set of name KEYS it contains (key = accent-stripped,
Greek transliterated, ae->ai, c->k, ph->f, y->u, first 5 letters), with document frequency.

Hebrew, Coptic, Persian and Urdu have no capital letters to key off, so each gets its own
source of proper-noun forms (research/theme_search/names_panel/OTHER_SCRIPTS_REPORT.md
has the sourcing and the quality check behind each choice):
- he: the BHSA nmpr (proper noun) tag in data/lemma_tables/hebrew_pos.json, already the
  table backend/hebrew/processor.py uses for live POS tags. No tagger, no threshold: BHSA's
  hand-tagged morphology is the name list, matched on the consonantal (unpointed) form.
- cop: data/inverted_index/syntax_coptic.db's upos column (Coptic Scriptorium's own hand-
  curated UD parses, not a tagger run here), kept where a surface form is tagged PROPN in
  at least 85% of its occurrences and occurs at least twice.
- fa / ur: pos_tags already cached per line in cache/lemmas/{fa,ur}/*.json (Stanza's own
  output, already on disk, no new tagger run), same 85%-purity rule at 3+ occurrences, UNION
  a short hand-built lexicon of names the purity filter misses (common in the poetry here but
  not frequent enough, or not consistently tagged, to clear the bar on their own: Biblical/
  Quranic prophets, the stock beloved/lover names of Persian and Urdu ghazal, Karbala and
  marsiya names for Urdu). The lexicon words are embedded below, not read from
  research/theme_search/names_panel/lexicons/ -- that directory is under research/, which
  stays out of the public repository entirely (CLAUDE.md), and these name
  lists are no longer research notes once production code depends on them at build time, so
  they get the data/lemma_tables/ treatment: tracked, not gitignored, sourced in a comment.
  Urdu additionally drops a short stoplist of stock ghazal nature-images (wine, rubies,
  dew, a leaf, a tulip...) that Stanza tags PROPN almost as consistently as a real name,
  because the poetic convention personifies them; see URDU_GHAZAL_STOPLIST below for how it
  was built.
- ar: held. Stanza finds zero PROPN across this corpus's 132 lines (OTHER_SCRIPTS_REPORT.md);
  the only workable source is hand-tagging the (dev-only) corpus directly, not a script.
  Revisit if Arabic is ever promoted out of dev-only status.

All five new-language passes write into the SAME window_names / name_df / meta tables the
la/grc/en pass does, with the same per-key document-frequency and the same IDF threshold
downstream (backend/passage_index.py NAMES_IDF_THRESHOLD, unchanged) -- a name is a name
regardless of which script it is written in.
"""
import json, re, sqlite3, time, unicodedata, collections, sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from backend.hebrew.processor import tokenize_hebrew          # noqa: E402
from backend.coptic.processor import normalize_coptic, tokenize_coptic   # noqa: E402
from backend.persian.processor import normalize_persian, tokenize_persian  # noqa: E402
from backend.urdu.processor import normalize_urdu, tokenize_urdu       # noqa: E402

IDX = os.environ.get('PASSAGE_INDEX_DIR', os.path.join(ROOT, 'data', 'passage_index'))
LEMMA_TABLES_DIR = os.path.join(ROOT, 'data', 'lemma_tables')
SYNTAX_COPTIC_DB = os.path.join(ROOT, 'data', 'inverted_index', 'syntax_coptic.db')
CACHE_LEMMAS_DIR = os.path.join(ROOT, 'cache', 'lemmas')

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


# ---------------------------------------------------------------------------
# Shared helpers for the he/cop/fa/ur passes (all pure functions: no file or
# database access, so they are the units the tests in
# tests/test_build_window_names_other_scripts.py exercise directly).
# ---------------------------------------------------------------------------

def hebrew_name_set(pos_table):
    """The BHSA proper-noun (nmpr) forms of a hebrew_pos.json-shaped table,
    already consonantal (unpointed) -- the same forms backend/hebrew/
    processor.py's live POS tagger treats as PROPN."""
    return {form for form, tag in pos_table.items() if tag == 'nmpr'}


def propn_purity_set(pairs, min_total, min_rate):
    """pairs: an iterable of (form, upos) for every tagged token occurrence
    (form already in whatever normalized shape the caller wants matched
    against window text). Keeps forms tagged PROPN in at least `min_rate` of
    their occurrences, with at least `min_total` occurrences total -- the
    same purity test the la/grc/en capitalisation pass runs, generalised
    from "capitalised or not" to "PROPN or not"."""
    total = collections.Counter(); propn = collections.Counter()
    for form, tag in pairs:
        total[form] += 1
        if tag == 'PROPN':
            propn[form] += 1
    return {f for f, t in total.items() if t >= min_total and propn[f] / t >= min_rate}


def names_in_window(original_tokens, normalized_tokens, names_set):
    """Map a window's token stream to {key: display form} for every token
    whose normalized form is in `names_set`, first occurrence wins -- the
    same shape the la/grc/en pass builds its per-window `ks` dict in."""
    ks = {}
    for orig, norm in zip(original_tokens, normalized_tokens):
        if norm in names_set:
            ks.setdefault(norm, orig)
    return ks


def parse_lexicon(words):
    """words: an iterable of 'word<TAB>gloss' or 'word' lines (comments
    starting with # and blank lines already excluded, or present -- both are
    skipped here too, so a lexicon list can be handed in raw). Returns the
    word column only, order preserved, blanks dropped."""
    out = []
    for line in words:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        word = line.split('\t', 1)[0].strip()
        if word:
            out.append(word)
    return out


def syntax_coptic_pairs(db_path, normalize_fn):
    """Yield (normalized form, upos) for every token Coptic Scriptorium's UD
    parses tag, straight from syntax_coptic.db's (tokens, upos) JSON-array
    columns -- one row per line/ref, both arrays the same length."""
    con = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    try:
        for toks_json, upos_json in con.execute('select tokens, upos from syntax'):
            toks = json.loads(toks_json or '[]')
            ups = json.loads(upos_json or '[]')
            for t, u in zip(toks, ups):
                yield normalize_fn(t), u
    finally:
        con.close()


def cache_pos_pairs(cache_dir, normalize_fn):
    """Yield (normalized form, upos) for every tokenized line already cached
    at cache/lemmas/{fa,ur}/*.json ('tokens' there is already normalized by
    the same normalize_fn the caller passes in, so this re-normalizes
    defensively rather than assuming it, which costs nothing and means a
    toy fixture using RAW tokens works the same as the real cache files)."""
    for fn in sorted(os.listdir(cache_dir)):
        if not fn.endswith('.json'):
            continue
        with open(os.path.join(cache_dir, fn), encoding='utf-8') as f:
            data = json.load(f)
        for unit in data.get('units_line') or []:
            toks = unit.get('tokens') or []
            pos = unit.get('pos_tags') or []
            for t, p in zip(toks, pos):
                yield normalize_fn(t), p


# ---------------------------------------------------------------------------
# Persian and Urdu hand lexicons. Sourced from research/theme_search/
# names_panel/lexicons/{fa,ur}.txt (2026-10-07, OTHER_SCRIPTS_REPORT.md);
# embedded here rather than read from research/ because that directory is
# gitignored (CLAUDE.md: nothing from research/ goes into the public
# repository) and a build script's input can't live somewhere the
# build script's own repository doesn't carry it. This is the same
# curated-data exception data/lemma_tables/ already gets, not a research
# write-up: a short, attributed, hand-checked word list a running build
# depends on.
# ---------------------------------------------------------------------------

# Quranic prophets (public domain: the Quran text and the roster of prophets'
# names are not under copyright), shared between fa and ur, plus the stock
# beloved/lover names of Persian ghazal and romance (Wikidata spot check
# 2026-10-07, CC0 dedication: Q14354376 Majnun, Q19967884 Farhad).
FA_LEXICON = parse_lexicon([
    'آدم\tAdam', 'ادریس\tIdris', 'نوح\tNoah', 'هود\tHud', 'صالح\tSalih',
    'ابراهیم\tAbraham/Ibrahim', 'لوط\tLot', 'اسماعیل\tIshmael', 'اسحاق\tIsaac',
    'یعقوب\tJacob', 'یوسف\tJoseph', 'شعیب\tShuayb', 'ایوب\tJob', 'موسی\tMoses',
    'هارون\tAaron', 'داود\tDavid', 'سلیمان\tSolomon', 'الیاس\tElijah',
    'یونس\tJonah', 'زکریا\tZechariah', 'یحیی\tJohn/Yahya', 'عیسی\tJesus',
    'محمد\tMuhammad', 'مریم\tMary',
    'مجنون\tMajnun', 'لیلی\tLayli/Layla', 'شیرین\tShirin', 'فرهاد\tFarhad',
    'زلیخا\tZuleikha', 'خضر\tKhezr/al-Khidr',
])

# Same Quranic roster (the subset research/.../ur.txt actually carries) plus
# the shared Perso-Urdu ghazal beloved names and a short Karbala/Shia
# marsiya list specific to Anis's marsiye, not covered by either list above.
UR_LEXICON = parse_lexicon([
    'آدم\tAdam', 'ادریس\tIdris', 'نوح\tNoah', 'ابراہیم\tAbraham/Ibrahim',
    'اسماعیل\tIshmael', 'اسحاق\tIsaac', 'یعقوب\tJacob', 'یوسف\tJoseph',
    'ایوب\tJob', 'موسی\tMoses', 'ہارون\tAaron', 'داود\tDavid',
    'سلیمان\tSolomon', 'یونس\tJonah', 'زکریا\tZechariah', 'یحیی\tJohn/Yahya',
    'عیسی\tJesus', 'محمد\tMuhammad', 'مریم\tMary',
    'مجنوں\tMajnun (epithet)', 'قیس\tQais (Majnun\'s given name)',
    'لیلیٰ\tLayla', 'شیریں\tShirin', 'فرہاد\tFarhad',
    'حسین\tHusayn ibn Ali', 'علی\tAli',
    'فاطمہ\tFatima', 'عباس\tAbbas ibn Ali', 'زینب\tZaynab bint Ali',
    'یزید\tYazid I', 'کربلا\tKarbala (place)',
])

# A hand stoplist of stock ghazal nature-images: words the purity filter
# above (85% PROPN, 3+ occurrences) keeps because Urdu ghazal convention
# addresses them as if they were a person or place almost as consistently as
# it names an actual one (OTHER_SCRIPTS_REPORT.md's Urdu section). Built by
# running the purity filter over the real cache/lemmas/ur/ data, reading the
# 200 most frequent passing forms by eye (2026-10-07), and pulling out the
# ones that are plainly conventional imagery rather than people or places.
# Counts observed at build time (PROPN-tagged / total occurrences), 3+
# occurrences and >=85% PROPN rate all already true of each (else the purity
# filter would have dropped them on its own and they would not need a stop
# entry at all):
#   می (wine) 84/91, لعل (ruby/lips) 74/86, شبنم (dew) 90/97, برگ (leaf)
#   78/81, محبوب (beloved) 90/100, لالہ (tulip) 109/120, نرگس (narcissus,
#   i.e. the beloved's eyes) 53/53, گلزار (rose-garden) 55/57, غنچۂ (bud of)
#   27/30, چاندني (moonlight) 34/37, نكہت (fragrance) 18/21, مژگان
#   (eyelashes) 15/15, انجم (stars) 42/48, یاقوت (ruby/sapphire) 14/15. The
#   last three were caught on a second and third pass (2026-10-07) reading
#   15 random post-build windows by eye each time (the "judge by eye" step
#   this spec asks for): مژگانِ "eyelashes of", انجم "the stars" and یاقوتِ
#   "ruby of" (all classic ghazal body/sky/gem imagery, the same class as
#   لعل) had slipped through the first reading of the top 200.
# Left IN the name set deliberately: a large amount of other grammar-word,
# verb-form and (in at least one body-description poem, nazeer.kulliyat's
# ghazal on a woman's appearance) clothing/anatomy-noun noise also clears
# the purity bar (اعدا "enemies", شود "becomes", ثم "then", اف "ugh",
# انگیا "bodice", چوٹی "braid", single letters and particles among them) --
# real tagger error on a different pattern from the stock-imagery one this
# stoplist targets, and a known Urdu limitation already called out in
# OTHER_SCRIPTS_REPORT.md ("the purity filter helps less here"); an
# exhaustive stoplist chasing every such word is a separate, open-ended
# piece of work, not scoped to this spec.
# Also left in deliberately: polysemous words that are a real name in some
# uses and a common noun in others (جلال "Jalal" / "majesty", پیر "a saint" /
# "an elder"). The exception is حسن: "beauty" in nearly every ghazal and the
# name Hasan ibn Ali only in Anis's marsiye, so it is removed from UR_LEXICON
# and stoplisted (2026-10-07 review), giving up the marsiye uses to keep the
# ghazal windows from being linked on a shared word for beauty.
URDU_GHAZAL_STOPLIST = frozenset(normalize_urdu(w) for w in [
    'حسن', 'می', 'لعل', 'شبنم', 'برگ', 'محبوب', 'لالہ', 'نرگس', 'گلزار', 'غنچۂ',
    'چاندني', 'نكہت', 'مژگان', 'انجم', 'یاقوت',
])


def main(out_path):
    t0 = time.time()
    con = sqlite3.connect(f'file:{IDX}/window_texts.db?mode=ro', uri=True)

    # -----------------------------------------------------------------
    # Latin, Greek, English -- UNCHANGED from the original single-language
    # build (byte-for-byte the same names; see the module docstring).
    # -----------------------------------------------------------------
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

    out = sqlite3.connect(out_path); out.execute('drop table if exists window_names'); out.execute('create table window_names (id text, k text, form text)')
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
    print(f'la/grc/en pass {time.time()-t0:.0f}s: {n} windows', flush=True)

    # -----------------------------------------------------------------
    # Hebrew: the BHSA nmpr table directly, no threshold.
    # -----------------------------------------------------------------
    he_pos_path = os.path.join(LEMMA_TABLES_DIR, 'hebrew_pos.json')
    if os.path.exists(he_pos_path):
        with open(he_pos_path, encoding='utf-8') as f:
            he_pos_table = json.load(f)
        he_names = hebrew_name_set(he_pos_table)
        he_batch = []; he_n = 0
        for wid, text in con.execute("select id, text from window_texts where language='he'"):
            orig, norm = tokenize_hebrew(text)
            for k, form in names_in_window(orig, norm, he_names).items():
                he_batch.append((wid, k, form)); df[k] += 1
            he_n += 1
        out.executemany('insert into window_names values (?,?,?)', he_batch)
        n += he_n
        print(f'Hebrew {time.time()-t0:.0f}s: {len(he_names)} BHSA proper-noun forms, '
              f'{he_n} windows, {len(he_batch)} window-name pairs', flush=True)
    else:
        print(f'Hebrew: {he_pos_path} not found, skipping', flush=True)

    # -----------------------------------------------------------------
    # Coptic: PROPN purity over syntax_coptic.db's own UD parses.
    # -----------------------------------------------------------------
    if os.path.exists(SYNTAX_COPTIC_DB):
        cop_names = propn_purity_set(
            syntax_coptic_pairs(SYNTAX_COPTIC_DB, normalize_coptic), min_total=2, min_rate=0.85)
        cop_batch = []; cop_n = 0
        for wid, text in con.execute("select id, text from window_texts where language='cop'"):
            orig, norm = tokenize_coptic(text)
            for k, form in names_in_window(orig, norm, cop_names).items():
                cop_batch.append((wid, k, form)); df[k] += 1
            cop_n += 1
        out.executemany('insert into window_names values (?,?,?)', cop_batch)
        n += cop_n
        print(f'Coptic {time.time()-t0:.0f}s: {len(cop_names)} purity-filtered PROPN forms, '
              f'{cop_n} windows, {len(cop_batch)} window-name pairs', flush=True)
    else:
        print(f'Coptic: {SYNTAX_COPTIC_DB} not found, skipping', flush=True)

    # -----------------------------------------------------------------
    # Persian: PROPN purity over the cached Stanza tags, union the lexicon.
    # -----------------------------------------------------------------
    fa_cache = os.path.join(CACHE_LEMMAS_DIR, 'fa')
    if os.path.isdir(fa_cache):
        fa_names = propn_purity_set(
            cache_pos_pairs(fa_cache, normalize_persian), min_total=3, min_rate=0.85)
        fa_names |= {normalize_persian(w) for w in FA_LEXICON}
        fa_batch = []; fa_n = 0
        for wid, text in con.execute("select id, text from window_texts where language='fa'"):
            orig, norm = tokenize_persian(text)
            for k, form in names_in_window(orig, norm, fa_names).items():
                fa_batch.append((wid, k, form)); df[k] += 1
            fa_n += 1
        out.executemany('insert into window_names values (?,?,?)', fa_batch)
        n += fa_n
        print(f'Persian {time.time()-t0:.0f}s: {len(fa_names)} names (purity + lexicon), '
              f'{fa_n} windows, {len(fa_batch)} window-name pairs', flush=True)
    else:
        print(f'Persian: {fa_cache} not found, skipping', flush=True)

    # -----------------------------------------------------------------
    # Urdu: same as Persian, minus the ghazal-imagery stoplist.
    # -----------------------------------------------------------------
    ur_cache = os.path.join(CACHE_LEMMAS_DIR, 'ur')
    if os.path.isdir(ur_cache):
        ur_names = propn_purity_set(
            cache_pos_pairs(ur_cache, normalize_urdu), min_total=3, min_rate=0.85)
        ur_names -= URDU_GHAZAL_STOPLIST
        ur_names |= {normalize_urdu(w) for w in UR_LEXICON}
        ur_batch = []; ur_n = 0
        for wid, text in con.execute("select id, text from window_texts where language='ur'"):
            orig, norm, _hemistich_breaks = tokenize_urdu(text)
            for k, form in names_in_window(orig, norm, ur_names).items():
                ur_batch.append((wid, k, form)); df[k] += 1
            ur_n += 1
        out.executemany('insert into window_names values (?,?,?)', ur_batch)
        n += ur_n
        print(f'Urdu {time.time()-t0:.0f}s: {len(ur_names)} names (purity + lexicon - stoplist), '
              f'{ur_n} windows, {len(ur_batch)} window-name pairs', flush=True)
    else:
        print(f'Urdu: {ur_cache} not found, skipping', flush=True)

    # Arabic (ar): held. See the module docstring -- Stanza finds no PROPN at
    # all in this corpus, and the 132-line dev-only corpus needs hand-tagging,
    # not a script. Nothing to build here.

    out.execute('create index ix_wn_id on window_names(id)'); out.execute('create index ix_wn_k on window_names(k)')
    out.execute('drop table if exists name_df'); out.execute('create table name_df (k text primary key, df integer)')
    out.executemany('insert into name_df values (?,?)', df.items()); out.execute('create table if not exists meta (key text, value text)')
    out.execute("insert into meta values ('windows', ?)", (str(n),)); out.commit()
    print(f'total {time.time()-t0:.0f}s: {n} windows, {sum(df.values())} window-name pairs, {len(df)} keys')
    open(out_path + '.done', 'w').write('ok')


if __name__ == '__main__':
    main(sys.argv[1])
