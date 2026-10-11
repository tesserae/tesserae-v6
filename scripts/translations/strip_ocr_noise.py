#!/usr/bin/env python3
"""Strip the facing-page OCR noise out of translations aligned from Loeb scans.

THE FAULT

Twenty-five translation files were aligned from Internet Archive scans of Loeb
volumes (Rogers' Aristophanes, Paton's Greek Anthology, Heath's Euclid, Lamb and
Fowler's Plato, Fairclough's Catalepton, Storr-Best's Varro). The scan's OCR of
the facing Greek or Latin page bled into the English block, so a unit carries
runs such as "143 ARISTOPHANES > / dwvi) juapd, yeyovas Kak@s ..." after a
running header. The alignment scripts had a GREEK_PAGE guard meant to drop such
pages; on this scan it never fired (see align_aristophanes.py).

THE METHOD

1. Vocabulary. There is no system word list, so English is learned from the
   translation files themselves: every alphabetic token (lower-cased, apostrophes
   stripped) found in at least three of the files NOT on the noisy list, plus
   every token of the noisy files found in at least five distinct units of the
   clean files.
2. Each whitespace token of a unit is English-like or not. English-like: its
   alphabetic core is in the vocabulary (a capitalised or all-capital word of
   three letters or more counts by its lower case), a number, a Roman numeral,
   a single ordinary punctuation mark, or a name (the words of the matching
   .tess text's reference tags, the capitalised words of a Latin .tess text,
   and any capitalised word that occurs three or more times in the file, which
   keeps "Paphlagon" and "Demus" and the speaker abbreviations). In Euclid the
   capital-letter labels of the diagrams ("ABC", "EC") also count.
3. Runs. Over any window of eight tokens with fewer than three English-like, the
   window is marked bad. A maximal bad stretch is trimmed to its first and last
   non-English token and extended while the next token is not English-like. A
   stretch of eight tokens or more is removed. A shorter stretch (a Greek
   quotation of five words in a footnote) stays.
4. Running headers ("143 ARISTOPHANES", "THE KNIGHTS 142", "GREEK ANTHOLOGY
   227") are removed wherever they stand; the pattern is built from the file's
   own title words.
5. A unit that nothing touched is written back byte for byte. A unit that lost
   something is re-joined with single spaces and tidied before punctuation. The
   unit keeps its index, so ref_to_unit stays valid; an emptied unit becomes "".
6. Guard: a file whose English-like token count falls by more than 3 percent is
   not written, and is reported instead.

Nothing here touches production: --src is read, --out receives the cleaned
files, --report receives report.md and a samples.md beside it.

  python3 scripts/translations/strip_ocr_noise.py \
      --src /var/www/tesseraev6_flask/data/translations \
      --out ~/tesserae-backups/translations_ocr_clean_2026-10-11/cleaned \
      --report ~/tesserae-backups/translations_ocr_clean_2026-10-11/report.md
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

# The 25 files whose English carries the noise (measured 2026-10-11).
NOISY_FILES = [
    'grc__aristophanes.wasps.json', 'grc__aristophanes.acharnians.json',
    'grc__aristophanes.knights.json',
    'grc__anthologia_graeca.part.10.json', 'grc__anthologia_graeca.part.11.json',
    'grc__anthologia_graeca.part.13.json', 'grc__anthologia_graeca.part.12.json',
    'grc__anthologia_graeca.part.7.json', 'grc__anthologia_graeca.part.15.json',
    'grc__anthologia_graeca.part.14.json', 'grc__anthologia_graeca.part.16.json',
    'grc__euclid.elements.json', 'grc__aristophanes.ecclesiazusae.json',
    'grc__aristophanes.plutus.json', 'grc__anthologia_graeca.part.8.json',
    'grc__aristophanes.thesmophoriazusae.json', 'grc__aristophanes.peace.json',
    'grc__plato.hipparchus.json', 'grc__plato.sophista.json',
    'grc__aristophanes.lysistrata.json', 'grc__aristophanes.frogs.json',
    'grc__plato.statesman.json', 'grc__aristophanes.birds.json',
    'la__vergil_pseudo.catalepton.json', 'la__varro.res_rusticae.json',
]

WINDOW = 8
MIN_ENGLISH_IN_WINDOW = 3
MIN_RUN = 8
GUARD_DROP = 0.03
VOCAB_MIN_FILES = 3
VOCAB_MIN_UNITS = 5
NAME_MIN_COUNT = 3

_WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*")
_ROMAN = re.compile(r'^(?=[IVXLCDM])M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$')
_PUNCT_OK = set('.,;:!?-—–"\'“”‘’()[]*')
_SEP = re.compile(r'[-—–/]+')
_VOWELS = set('aeiouyAEIOUY')


def _fold(s):
    """Accents removed, so a Latin-script word looks the same everywhere."""
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if not unicodedata.combining(c))


def norm_word(w):
    """Lower-cased, accent-folded, apostrophes stripped."""
    return _fold(w).replace("'", '').replace('’', '').lower()


def alpha_tokens(text):
    return _WORD.findall(text)


_ASCII_WORD = re.compile(r"[A-Za-z]+(?:['\u2019][A-Za-z]+)*")


def ascii_tokens(text):
    """The alphabetic tokens the junk measure counts (ASCII letters only, so
    accented Greek and Latin letters split a token the way the first
    measurement of 2026-10-11 did)."""
    return _ASCII_WORD.findall(text)


def is_junk_word(w):
    """The measuring test: no vowel, a lower-case letter followed by a capital,
    or a capital run followed by lower case."""
    w = _fold(w).replace("'", '').replace('’', '')
    if not w:
        return False
    if not (set(w) & _VOWELS):
        return True
    if re.search(r'[a-z][A-Z]', w):
        return True
    if re.search(r'[A-Z]{2,}[a-z]', w):
        return True
    return False


def junk_stats(units):
    n = j = 0
    for u in units:
        for w in ascii_tokens(u):
            n += 1
            if is_junk_word(w):
                j += 1
    return n, j


# ---------------------------------------------------------------- vocabulary

def _units_of(data):
    if isinstance(data, dict):
        return [u for u in data.get('units', []) if isinstance(u, str)]
    if isinstance(data, list):
        return [u for u in data if isinstance(u, str)]
    return []


def _load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _ascii_word(w):
    return bool(w) and w.isascii() and w.isalpha()


def build_vocab(src, noisy):
    """Return (vocab set, stats dict). See the module docstring, step 1."""
    noisy = set(noisy)
    files = sorted(fn for fn in os.listdir(src)
                   if fn.endswith('.json') and fn != 'manifest.json')
    clean_files = [fn for fn in files if fn not in noisy]
    df = Counter()
    clean_data = {}
    for fn in clean_files:
        try:
            units = _units_of(_load(os.path.join(src, fn)))
        except (OSError, ValueError):
            continue
        clean_data[fn] = units
        seen = set()
        for u in units:
            for w in alpha_tokens(u):
                seen.add(norm_word(w))
        df.update(w for w in seen if _ascii_word(w))
    vocab = {w for w, c in df.items() if c >= VOCAB_MIN_FILES}
    base = len(vocab)
    noisy_tokens = set()
    for fn in noisy:
        p = os.path.join(src, fn)
        if os.path.exists(p):
            for u in _units_of(_load(p)):
                for w in alpha_tokens(u):
                    w = norm_word(w)
                    if _ascii_word(w):
                        noisy_tokens.add(w)
    unit_count = Counter()
    for units in clean_data.values():
        for u in units:
            for w in {norm_word(x) for x in alpha_tokens(u)}:
                if w in noisy_tokens:
                    unit_count[w] += 1
    extra = {w for w, c in unit_count.items() if c >= VOCAB_MIN_UNITS}
    vocab |= extra
    return vocab, {'clean_files': len(clean_files), 'from_files': base,
                   'from_units_extra': len(vocab) - base, 'size': len(vocab)}


# --------------------------------------------------------------------- names

def tess_names(tess_dir, tess_work):
    """Words from the reference tags of the matching .tess text and, for Latin,
    its capitalised words."""
    names = set()
    if not tess_dir or not tess_work or '/' not in tess_work:
        return names
    lang, work = tess_work.split('/', 1)
    path = os.path.join(tess_dir, lang, work + '.tess')
    if not os.path.exists(path):
        return names
    with open(path, encoding='utf-8') as f:
        for line in f:
            m = re.match(r'\s*<([^>]*)>\s*(.*)', line)
            if not m:
                continue
            for w in alpha_tokens(m.group(1)):
                if len(w) > 1:
                    names.add(norm_word(w))
            if lang == 'la':
                for w in alpha_tokens(m.group(2)):
                    if w[0].isupper() and len(w) >= 3:
                        names.add(norm_word(w))
    return names


def local_names(units):
    c = Counter()
    for u in units:
        for w in alpha_tokens(u):
            if re.fullmatch(r"[A-Z][a-z]+", w) and len(w) >= 3:
                c[norm_word(w)] += 1
    return {w for w, n in c.items() if n >= NAME_MIN_COUNT}


# ------------------------------------------------------------------ headers

def header_regex(tess_work):
    """Pattern for the running header: a page number beside the work's title
    words in capitals, either side, with the stray mark OCR leaves after it."""
    work = tess_work.split('/', 1)[-1]
    author, _, title = work.partition('.')
    title = re.sub(r'\.part\.\d+$', '', title)
    words = {author.replace('_', ' ').upper()}
    if title:
        t = title.replace('_', ' ').upper()
        words.add(t)
        words.add('THE ' + t)
    if author == 'anthologia_graeca':
        words = {'GREEK ANTHOLOGY', 'THE GREEK ANTHOLOGY'}
    if author == 'vergil_pseudo':
        words.add('VERGIL')
    names = '|'.join(re.escape(w).replace('\\ ', r'\s+')
                     for w in sorted(words, key=len, reverse=True))
    mark = r'[>:,.;)\]|]?'
    num = r'\d{1,4}\)?'
    return re.compile(
        r'(?<![A-Za-z0-9])(?:' + num + r'\s*(?:' + names + r')\b' + mark +
        r'|(?:' + names + r')\s*' + num + r'(?![A-Za-z0-9]))')


# ------------------------------------------------------------------ the core

class Cleaner:
    def __init__(self, vocab, names=(), tess_work='', math_labels=False):
        self.vocab = vocab
        self.names = set(names)
        self.header = header_regex(tess_work) if tess_work else None
        self.math_labels = math_labels

    def _in_vocab(self, w):
        v = self.vocab
        if w in v:
            return True
        if w.endswith('s') and w[:-1] in v:
            return True
        return False

    def english_like(self, tok):
        core = tok.strip(''.join(c for c in set(tok)
                                 if not c.isalnum() and c not in "'’"))
        if not core:
            return len(tok) <= 3 and all(c in _PUNCT_OK for c in tok)
        if core.isdigit():
            return True
        if _ROMAN.match(core):
            return True
        if self.math_labels and re.fullmatch(r'[A-Z]{1,4}', core):
            return True
        parts = [p for p in _SEP.split(core) if p]
        if not parts:
            return True
        return all(self._part_ok(p) for p in parts)

    def _part_ok(self, p):
        if not _WORD.fullmatch(p):
            return False
        lower = norm_word(p)
        if p.islower():
            return self._in_vocab(lower) or lower in self.names
        if p[0].isupper() and p[1:].islower():
            return (self._in_vocab(lower) or lower in self.names)
        if p.isupper():
            if len(p) < 3:
                return p in ('A', 'I', 'O')
            return self._in_vocab(lower) or lower in self.names
        return False

    def strong(self, tok):
        """A content word: 4 or more letters, all letters, in the vocabulary.
        Noise rarely produces one, so the guard counts these."""
        core = tok.strip(''.join(c for c in set(tok) if not c.isalpha()))
        if len(core) < 4 or not core.isalpha() or _ROMAN.match(core):
            return False
        return self._in_vocab(norm_word(core))

    def runs(self, toks):
        """[(start, end)) of the runs to remove, from the English flags."""
        n = len(toks)
        if n < MIN_RUN:
            return []
        eng = [self.english_like(t) for t in toks]
        w = min(WINDOW, n)
        pre = [0]
        for e in eng:
            pre.append(pre[-1] + (1 if e else 0))
        bad = [False] * n
        for s in range(0, n - w + 1):
            if pre[s + w] - pre[s] < MIN_ENGLISH_IN_WINDOW:
                for k in range(s, s + w):
                    bad[k] = True
        out = []
        i = 0
        while i < n:
            if not bad[i]:
                i += 1
                continue
            j = i
            while j < n and bad[j]:
                j += 1
            a, b = i, j
            while a < b and eng[a]:
                a += 1
            while b > a and eng[b - 1]:
                b -= 1
            while a > 0 and not eng[a - 1]:
                a -= 1
            while b < n and not eng[b]:
                b += 1
            if b - a >= MIN_RUN and a < b:
                out.append((a, b))
            i = j
        merged = []
        for a, b in out:
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
            else:
                merged.append((a, b))
        return merged

    def clean_unit(self, unit):
        """Return (new_unit, info). info lists removed runs and header hits."""
        info = {'runs': [], 'headers': 0, 'collateral': 0, 'strong': 0}
        text = unit
        if self.header is not None:
            text, k = self.header.subn(' ', text)
            info['headers'] = k
        toks = text.split()
        runs = self.runs(toks)
        if not runs and not info['headers']:
            return unit, info
        keep = []
        last = 0
        for a, b in runs:
            keep.extend(toks[last:a])
            removed = toks[a:b]
            ctx_l = toks[max(0, a - 10):a]
            ctx_r = toks[b:b + 10]
            info['runs'].append({'tokens': removed, 'left': ctx_l, 'right': ctx_r})
            info['collateral'] += sum(1 for t in removed if self.english_like(t))
            info['strong'] += sum(1 for t in removed if self.strong(t))
            last = b
        keep.extend(toks[last:])
        out = ' '.join(keep)
        out = re.sub(r'\s+([,.;:?!])', r'\1', out)
        out = re.sub(r'\s{2,}', ' ', out).strip()
        return out, info


def count_tokens(units, cleaner):
    n = e = st = 0
    for u in units:
        for t in u.split():
            if not any(c.isalnum() for c in t):
                continue    # a detached mark merges into its neighbour on re-joining
            n += 1
            if cleaner.english_like(t):
                e += 1
            if cleaner.strong(t):
                st += 1
    return n, e, st


def process(data, vocab, tess_dir=None, name=''):
    """Clean one parsed translation file. Returns (new_data, result dict)."""
    tess_work = data.get('tess_work', '') if isinstance(data, dict) else ''
    units = list(data['units'])
    names = tess_names(tess_dir, tess_work) | local_names(units)
    cleaner = Cleaner(vocab, names, tess_work, math_labels='euclid' in tess_work)
    ja, jb = junk_stats(units)
    tok0, eng0, str0 = count_tokens(units, cleaner)
    # The guard compares like with like: headers are removed on purpose, so
    # their words are taken out of the baseline.
    if cleaner.header is not None:
        base = [cleaner.header.sub(' ', u) if isinstance(u, str) else u for u in units]
        _, eng_b, str_b = count_tokens(base, cleaner)
    else:
        eng_b, str_b = eng0, str0
    new_units, runs, headers, collateral, emptied, changed = [], [], 0, 0, 0, 0
    strong_lost = 0
    for i, u in enumerate(units):
        if not isinstance(u, str):
            new_units.append(u)
            continue
        nu, info = cleaner.clean_unit(u)
        if nu != u:
            changed += 1
        if u.strip() and not nu.strip():
            emptied += 1
            nu = ''
        collateral += info['collateral']
        strong_lost += info['strong']
        headers += info['headers']
        for r in info['runs']:
            r['unit'] = i
            runs.append(r)
        new_units.append(nu)
    tok1, eng1, str1 = count_tokens(new_units, cleaner)
    na, jb2 = junk_stats(new_units)
    res = {
        'name': name, 'units': len(units), 'changed_units': changed,
        'emptied_units': emptied,
        'junk_before': jb / ja if ja else 0.0,
        'junk_after': jb2 / na if na else 0.0,
        'tokens_before': tok0, 'tokens_after': tok1,
        'english_before': eng0, 'english_after': eng1,
        'runs': len(runs), 'headers': headers, 'strong_collateral': strong_lost, 'collateral': collateral,
        'residue': jb2, 'runs_detail': runs, 'names': len(names),
        'new_units': new_units,
    }
    res['english_drop'] = (eng_b - eng1) / eng_b if eng_b else 0.0
    res['strong_before'] = str0
    res['strong_after'] = str1
    res['strong_drop'] = (str_b - str1) / str_b if str_b else 0.0
    # Guard on content words. Counting every English-like token (numbers,
    # "a", Roman numerals) would refuse the Aristophanes files, because the
    # Greek-OCR runs are full of tokens that pass those tests by accident.
    res['guard_failed'] = res['strong_drop'] > GUARD_DROP
    out = dict(data)
    out['units'] = new_units
    return out, res


# -------------------------------------------------------------------- output

def _fmt(toks):
    return ' '.join(toks)


def residue_stretches(units, k=3, width=30):
    best = []
    for i, u in enumerate(units):
        toks = u.split()
        flags = [any(is_junk_word(w) for w in ascii_tokens(t)) for t in toks]
        if not toks:
            continue
        w = min(width, len(toks))
        score = sum(flags[:w])
        cur = score
        top = (score, 0)
        for s in range(1, len(toks) - w + 1):
            cur += flags[s + w - 1] - flags[s - 1]
            if cur > top[0]:
                top = (cur, s)
        if top[0]:
            best.append((top[0], i, ' '.join(toks[top[1]:top[1] + w])))
    best.sort(key=lambda x: -x[0])
    chosen, used = [], set()
    for sc, i, txt in best:
        if i in used:
            continue
        used.add(i)
        chosen.append((sc, i, txt))
        if len(chosen) == k:
            break
    return chosen


def write_reports(results, vocab_stats, report_path, dry_run):
    outdir = os.path.dirname(os.path.abspath(report_path))
    os.makedirs(outdir, exist_ok=True)
    L = ['# OCR noise stripped from translations', '',
         'Vocabulary: %d words (%d from %d clean files at three or more files each, '
         '%d more from noisy-file tokens seen in five or more clean units).' % (
             vocab_stats['size'], vocab_stats['from_files'],
             vocab_stats['clean_files'], vocab_stats['from_units_extra']),
         'Mode: %s.' % ('dry run, nothing written' if dry_run else 'files written'),
         '',
         '| File | Junk before | Junk after | Tokens before | Tokens after | '
         'Runs | Headers | Collateral | Residue | Emptied units | English-like drop | Content-word drop | Written |',
         '|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    tot = defaultdict(float)
    for r in results:
        L.append('| %s | %.2f%% | %.2f%% | %d | %d | %d | %d | %d | %d | %d | %.2f%% | %.2f%% | %s |' % (
            r['name'], 100 * r['junk_before'], 100 * r['junk_after'],
            r['tokens_before'], r['tokens_after'], r['runs'], r['headers'],
            r['collateral'], r['residue'], r['emptied_units'],
            100 * r['english_drop'], 100 * r['strong_drop'],
            'REFUSED (guard)' if r['guard_failed'] else r.get('written', 'no')))
        for k in ('tokens_before', 'tokens_after', 'runs', 'headers',
                  'collateral', 'residue', 'emptied_units'):
            tot[k] += r[k]
    L.append('| **Total** | | | %d | %d | %d | %d | %d | %d | %d | | | |' % (
        tot['tokens_before'], tot['tokens_after'], tot['runs'], tot['headers'],
        tot['collateral'], tot['residue'], tot['emptied_units']))
    L += ['', 'Junk = share of alphabetic tokens with no vowel, a lower-case letter '
          'followed by a capital, or a capital run followed by lower case. '
          'Collateral = English-like tokens inside removed runs. Residue = '
          'tokens still failing the junk test after cleaning.']
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')
    S = ['# Samples of removed and retained stretches', '']
    for r in results:
        S.append('## ' + r['name'])
        runs = r['runs_detail']
        longest = sorted(runs, key=lambda x: -len(x['tokens']))[:3]
        edge = [x for x in runs if 8 <= len(x['tokens']) <= 12][:3]
        for title, lst in (('Longest removed runs', longest),
                           ('Removed runs of 8 to 12 tokens', edge)):
            S.append('')
            S.append('### ' + title)
            if not lst:
                S.append('(none)')
            for x in lst:
                S.append('- unit %d, %d tokens: ...%s **[%s]** %s...' % (
                    x['unit'], len(x['tokens']), _fmt(x['left']),
                    _fmt(x['tokens']), _fmt(x['right'])))
        S.append('')
        S.append('### Retained stretches with the most residue')
        rs = residue_stretches(r['new_units'])
        if not rs:
            S.append('(none)')
        for sc, i, txt in rs:
            S.append('- unit %d, %d failing: %s' % (i, sc, txt))
        S.append('')
    with open(os.path.join(outdir, 'samples.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(S) + '\n')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--src', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--report', required=True)
    ap.add_argument('--files', nargs='*')
    ap.add_argument('--tess', default='/var/www/tesseraev6_flask/texts')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    files = a.files or NOISY_FILES
    vocab, vstats = build_vocab(a.src, NOISY_FILES)
    print('vocabulary: %d words' % vstats['size'], flush=True)
    results = []
    if not a.dry_run:
        os.makedirs(a.out, exist_ok=True)
    for fn in files:
        data = _load(os.path.join(a.src, fn))
        if not isinstance(data, dict) or 'units' not in data:
            print('skip (not a dict file): ' + fn)
            continue
        new, res = process(data, vocab, a.tess, fn)
        res['written'] = 'dry run' if a.dry_run else 'yes'
        if res['guard_failed']:
            res['written'] = 'no'
            print('GUARD: %s English-like tokens fell %.2f%%, not written' % (
                fn, 100 * res['english_drop']))
        elif not a.dry_run:
            with open(os.path.join(a.out, fn), 'w', encoding='utf-8') as f:
                json.dump(new, f, ensure_ascii=False)
        print('%s junk %.2f%% -> %.2f%%, runs %d, headers %d, collateral %d, '
              'residue %d, emptied %d' % (
                  fn, 100 * res['junk_before'], 100 * res['junk_after'],
                  res['runs'], res['headers'], res['collateral'],
                  res['residue'], res['emptied_units']), flush=True)
        results.append(res)
    write_reports(results, vstats, a.report, a.dry_run)
    return 0


if __name__ == '__main__':
    sys.exit(main())
