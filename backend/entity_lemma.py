"""Lemma matcher for the entity mention index (stage 1b, 2026-10-17).

The stem matcher in backend/entity_index.py compares a window token with a stem of the
entity's name plus a closed set of case endings. This module compares lemmas instead.

For each list entity, in each language:
    1. Take the forms the entity carries (Latin forms, the Greek form, the English label)
       and look up the lemma of each with the lemmatizer the site uses (lookup table first,
       then the CLTK backoff for Latin, the Stanza fallback for Greek, WordNet for English).
    2. Keep a lemma only when it is name-like: its table entry begins with a capital, or
       the tokens that carry it are written with a capital initial in most of their
       occurrences in the counted windows. Occurrences at the start of a line, a window or
       a sentence are left out of that count, because verse lines and sentences open with a
       capital whatever the word is.
A mention is a window token whose lemma is in the entity's lemma set AND whose first
letter (marks that combine with it ignored) is a capital. A lemma shared by two entities
gives a mention for both, flagged homonym.

Lemmas are computed once per distinct token (the lemmatizers look at one token at a
time, except the Greek Stanza fallback, which is given a batch of isolated tokens here).
"""
import collections
import re
import sqlite3
import time
import unicodedata

from backend import entity_index as ei

SENT_END = '.;?!·'
MAJORITY = 0.5


def first_letter(raw):
    for ch in raw:
        if not unicodedata.combining(ch):
            return ch
    return ''


def is_cap(raw):
    return first_letter(raw).isupper()


def tokens_of(text):
    """Yield (raw, folded, initial) for each word of a window. `initial` is true for the
    first word of the window, the first word of a line and a word after sentence-ending
    punctuation."""
    prev_end = 0
    first = True
    for m in ei.WORD.finditer(text):
        gap = text[prev_end:m.start()]
        initial = first or '\n' in gap
        if not initial:
            g = gap.rstrip()
            if g and g[-1] in SENT_END:
                initial = True
        first = False
        prev_end = m.end()
        raw = m.group(0)
        yield raw, ei._fold_tok(raw), initial


def count_types(texts_conn, unit, log=print):
    """types[lang][folded] = [n_all, cap_all, n_inner, cap_inner, representative]. `inner`
    leaves out the words that open a line, a window or a sentence."""
    types = {l: {} for l in ei.LANGS}
    t0 = time.time()
    done = 0
    for wid, lang, text in texts_conn.execute('select id, language, text from window_texts'):
        if wid not in unit or lang not in types:
            continue
        d = types[lang]
        done += 1
        if done % 100000 == 0:
            log(f'  counted {done} windows {time.time() - t0:.0f}s')
        for raw, f, initial in tokens_of(text):
            cap = 1 if is_cap(raw) else 0
            e = d.get(f)
            if e is None:
                e = d[f] = [0, 0, 0, 0, raw.lower()]
            e[0] += 1
            e[1] += cap
            if not initial:
                e[2] += 1
                e[3] += cap
    log(f'  type counts: {done} windows, {time.time() - t0:.0f}s, '
        + ', '.join(f'{l} {len(d)}' for l, d in types.items()))
    return types


class Resolver:
    """Token to lemma, with the site's own lemmatizers."""

    def __init__(self, log=print):
        from backend import text_processor as tp
        self.tp = tp
        self.P = tp.TextProcessor()
        self.P._ensure_models_loaded()
        self.latin_table = tp.get_latin_lemma_table()
        self.greek_table = tp.get_greek_lemma_table()
        self.log = log
        self.source = {}      # (lang, form) -> 'table' or 'backoff'

    @staticmethod
    def usable(tok):
        bare = ''.join(c for c in tok if not unicodedata.combining(c))
        return bool(bare) and bare.isalpha()

    def lemmas(self, lang, forms):
        """forms: iterable of tokens as the lemmatizer takes them (Latin and English
        folded, Greek lower-cased with its accents). Returns {form: lemma} for the forms
        that have a usable shape."""
        forms = [f for f in dict.fromkeys(forms) if self.usable(f)]
        out = {}
        if lang == 'la':
            for f in forms:
                self.source[(lang, f)] = 'table' if f in self.latin_table else 'backoff'
            for i in range(0, len(forms), 5000):
                chunk = forms[i:i + 5000]
                out.update(zip(chunk, self.P._latin_lemmatize(chunk)))
        elif lang == 'grc':
            need = []
            for f in forms:
                n = self.P._normalize_greek_token(f)
                if n in self.greek_table:
                    out[f] = self.greek_table[n]
                    self.source[(lang, f)] = 'table'
                else:
                    need.append(f)
                    self.source[(lang, f)] = 'backoff'
            for i in range(0, len(need), 200):
                chunk = need[i:i + 200]
                try:
                    res = self.P._stanza_greek_lemmatize_batch(chunk)
                except Exception:  # noqa: BLE001
                    res = [self.P._normalize_greek_token(x) for x in chunk]
                for f, lem in zip(chunk, res):
                    out[f] = lem
        else:
            for i in range(0, len(forms), 5000):
                chunk = forms[i:i + 5000]
                out.update(zip(chunk, self.P._nltk_english_lemmatize(chunk)))
                for f in chunk:
                    self.source[(lang, f)] = 'backoff'
        return out


def lemma_input(lang, folded, rep):
    """The token as the lemmatizer expects it."""
    return rep if lang == 'grc' else folded


def entity_forms(entities):
    """{lang: [(eidx, folded form)]}: the forms each entity is looked up on, per window
    language. Latin forms are used for Latin and for English windows, as in the stem
    matcher."""
    out = {l: [] for l in ei.LANGS}
    for idx, e in enumerate(entities):
        seen = set()
        for k in e['keys']:
            for lf in k['latin']:
                f = ei.fold(lf)
                if f and ('la', f) not in seen:
                    seen.add(('la', f))
                    out['la'].append((idx, f))
                if f and ('en', f) not in seen:
                    seen.add(('en', f))
                    out['en'].append((idx, f))
            g = ei.fold(k['greek'])
            if g and ('grc', g) not in seen:
                seen.add(('grc', g))
                out['grc'].append((idx, g))
            for ef in ei._english_forms(k.get('english')):
                f = ei.fold(ef)
                if f and ('en', f) not in seen:
                    seen.add(('en', f))
                    out['en'].append((idx, f))
    return out


def build_lemma_matcher(entities, types, resolver, log=print):
    """Return (tok2ents, info). tok2ents[lang][folded token] = tuple of entity indexes,
    for every token type that is written with a capital at least once and whose lemma is
    in the entity's lemma set. info holds the diagnostics the report needs."""
    t0 = time.time()
    # lemma of every token type
    type_lemma = {l: {} for l in ei.LANGS}
    for lang in ei.LANGS:
        d = types[lang]
        inp = {f: lemma_input(lang, f, v[4]) for f, v in d.items()}
        res = resolver.lemmas(lang, inp.values())
        type_lemma[lang] = {f: res[i] for f, i in inp.items() if i in res}
        log(f'  lemmatized {lang}: {len(type_lemma[lang])} of {len(d)} types, {time.time() - t0:.0f}s')
    # capitalization of each lemma
    stats = {l: collections.defaultdict(lambda: [0, 0, 0, 0]) for l in ei.LANGS}
    for lang in ei.LANGS:
        for f, v in types[lang].items():
            lem = type_lemma[lang].get(f)
            if lem is None:
                continue
            s = stats[lang][lem]
            s[0] += v[0]
            s[1] += v[1]
            s[2] += v[2]
            s[3] += v[3]

    def cap_share(lang, lem):
        s = stats[lang].get(lem)
        if not s or s[0] == 0:
            return None
        return (s[3] / s[2]) if s[2] else (s[1] / s[0])

    forms = entity_forms(entities)
    form_types = {}
    for lang in ei.LANGS:
        inp = {}
        for idx, f in forms[lang]:
            rep = types[lang].get(f)
            inp[f] = lemma_input(lang, f, rep[4] if rep else f)
        form_types[lang] = resolver.lemmas(lang, inp.values()), inp
    ent_lemmas = {l: collections.defaultdict(set) for l in ei.LANGS}
    lemma_ents = {l: collections.defaultdict(set) for l in ei.LANGS}
    diag = collections.Counter()
    no_lemma = collections.defaultdict(set)    # lang -> entity indexes with no kept lemma
    tried = collections.defaultdict(set)
    reasons = collections.defaultdict(dict)    # (lang, eidx) -> list of why a form was dropped
    for lang in ei.LANGS:
        res, inp = form_types[lang]
        for idx, f in forms[lang]:
            tried[lang].add(idx)
            lem = res.get(inp[f])
            if lem is None:
                diag[f'{lang}_form_without_lemma'] += 1
                reasons[(lang, idx)].setdefault('why', []).append(f'{f}: no lemma')
                continue
            share = cap_share(lang, lem)
            if share is None:
                diag[f'{lang}_lemma_not_in_corpus'] += 1
                reasons[(lang, idx)].setdefault('why', []).append(f'{f}->{lem}: lemma not in corpus')
                continue
            if share < MAJORITY:
                diag[f'{lang}_lemma_mostly_lower_case'] += 1
                reasons[(lang, idx)].setdefault('why', []).append(
                    f'{f}->{lem}: capitalized {share:.2f} of inner occurrences')
                continue
            ent_lemmas[lang][idx].add(lem)
            lemma_ents[lang][lem].add(idx)
            diag[f'{lang}_form_kept'] += 1
        for idx in tried[lang]:
            if not ent_lemmas[lang].get(idx):
                no_lemma[lang].add(idx)
    tok2ents = {l: {} for l in ei.LANGS}
    for lang in ei.LANGS:
        for f, v in types[lang].items():
            if not v[1]:
                continue
            lem = type_lemma[lang].get(f)
            if lem is None:
                continue
            es = lemma_ents[lang].get(lem)
            if es:
                tok2ents[lang][f] = tuple(sorted(es))
    info = {'diag': dict(diag), 'no_lemma': no_lemma, 'tried': tried, 'ent_lemmas': ent_lemmas,
            'reasons': reasons, 'type_lemma': type_lemma, 'stats': stats, 'cap_share': cap_share,
            'form_source': {k: v for k, v in resolver.source.items()}}
    log(f'  lemma matcher: ' + ', '.join(f'{l} {len(tok2ents[l])} token types' for l in ei.LANGS)
        + f', {time.time() - t0:.0f}s')
    return tok2ents, info


def scan_windows_lemma(texts_conn, unit, tok2ents, log=print):
    """Return (rows, wmeta, tally). rows: dict(eidx, wid, form, tok, homonym, lang) for the
    first capitalized token of each (entity, window)."""
    rows, wmeta = [], {}
    tally = collections.Counter()
    t0 = time.time()
    done = 0
    q = 'select id, language, work, ref_start, ref_end, text from window_texts'
    for wid, lang, work, rs, re_, text in texts_conn.execute(q):
        if wid not in unit:
            continue
        wmeta[wid] = (lang, work, rs, re_)
        if lang not in ei.LANGS:
            continue
        tally['windows_' + lang] += 1
        done += 1
        if done % 100000 == 0:
            log(f'  scanned {done} windows {time.time() - t0:.0f}s')
        t2e = tok2ents[lang]
        found = {}
        for m in ei.WORD.finditer(text):
            raw = m.group(0)
            es = t2e.get(ei._fold_tok(raw))
            if not es or not is_cap(raw):
                continue
            for i in es:
                if i not in found:
                    found[i] = (raw, len(es) > 1)
        for i, (raw, hom) in found.items():
            if ei.COMB.match(raw[:1]):
                tally['mentions_first_char_is_mark'] += 1
            rows.append({'eidx': i, 'wid': wid, 'form': raw, 'tok': ei._fold_tok(raw),
                         'homonym': hom, 'lang': lang, 'nb': False, 'ds': False, 'conf': 'lemma',
                         'stem': 0, 'stopped': False, 'distinctive': False})
    tally['scan_seconds'] = round(time.time() - t0)
    return rows, wmeta, tally
