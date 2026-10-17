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
import json
import os
import time
import unicodedata

from backend import entity_index as ei

SENT_END = '.;?!·'
MAJORITY = 0.5
OVERRIDES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'entity_lemma_overrides.json')


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
    types = {lg: {} for lg in ei.LANGS}
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
        + ', '.join(f'{lg} {len(d)}' for lg, d in types.items()))
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
    out = {lg: [] for lg in ei.LANGS}
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


def prepare_lemmas(entities, types, resolver, log=print):
    """The slow, threshold-free part of the matcher: the lemma of every token type, each
    lemma's capitalization counts, and the lemma of every form each entity is looked up on.
    Returns a dict that assemble_matcher() turns into a token table for any threshold."""
    t0 = time.time()
    type_lemma = {lg: {} for lg in ei.LANGS}
    for lang in ei.LANGS:
        d = types[lang]
        inp = {f: lemma_input(lang, f, v[4]) for f, v in d.items()}
        res = resolver.lemmas(lang, inp.values())
        type_lemma[lang] = {f: res[i] for f, i in inp.items() if i in res}
        log(f'  lemmatized {lang}: {len(type_lemma[lang])} of {len(d)} types, {time.time() - t0:.0f}s')
    stats = {lg: collections.defaultdict(lambda: [0, 0, 0, 0]) for lg in ei.LANGS}
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
    forms = entity_forms(entities)
    form_lemma = []          # (lang, eidx, folded form, lemma or None)
    for lang in ei.LANGS:
        inp = {}
        for idx, f in forms[lang]:
            rep = types[lang].get(f)
            inp[f] = lemma_input(lang, f, rep[4] if rep else f)
        res = resolver.lemmas(lang, inp.values())
        for idx, f in forms[lang]:
            form_lemma.append((lang, idx, f, res.get(inp[f])))
    return {'type_lemma': type_lemma, 'stats': stats, 'form_lemma': form_lemma,
            'form_source': dict(resolver.source)}


def cap_share_of(stats, lang, lem):
    s = stats[lang].get(lem)
    if not s or s[0] == 0:
        return None
    return (s[3] / s[2]) if s[2] else (s[1] / s[0])


def load_overrides(entities, path=None):
    """{lang: {folded token: set of entity indexes}} from the per-entity override file."""
    path = path or OVERRIDES_PATH
    out = {lg: collections.defaultdict(set) for lg in ei.LANGS}
    if not path or not os.path.exists(path):
        return out
    by_id = {e['entity_id']: i for i, e in enumerate(entities)}
    for o in json.load(open(path, encoding='utf-8'))['overrides']:
        idx = by_id.get(o['entity_id'])
        if idx is None:
            continue
        for form in o['forms']:
            out[o['lang']][ei._fold_tok(form)].add(idx)
    return out


def assemble_matcher(entities, types, prep, threshold=MAJORITY, audit_fixes=True, overrides=True, log=print,
                     decisions=None):
    """Return (tok2ents, info). tok2ents[lang][folded token] = tuple of entity indexes,
    for every token type that is written with a capital at least once and whose lemma is
    in the entity's lemma set. With audit_fixes the lemmas that entity_lemma_audit proposes
    to drop are removed first, and with overrides the surface forms of the override file
    are added. info holds the diagnostics the report needs.

    decisions (stage 1d) maps (lang, entity_id, lemma) to the model's judgment of that lemma:
    'drop' (a demonym or a common word), 'keep' (a name of the entity) or 'other' (the name
    of a different entity: the lemma stays and its tokens are listed in info['amb_tokens'] so
    that the mention scan asks the window). A decision replaces the audit's proposal for its
    pair. Pairs without a decision follow the audit."""
    t0 = time.time()
    by_id = {e['entity_id']: i for i, e in enumerate(entities)}
    dec = {(lang, by_id[eid], lem): v for (lang, eid, lem), v in (decisions or {}).items() if eid in by_id}
    type_lemma, stats = prep['type_lemma'], prep['stats']
    ent_lemmas = {lg: collections.defaultdict(set) for lg in ei.LANGS}
    diag = collections.Counter()
    tried = collections.defaultdict(set)
    reasons = collections.defaultdict(dict)
    for lang, idx, f, lem in prep['form_lemma']:
        tried[lang].add(idx)
        if lem is None:
            diag[f'{lang}_form_without_lemma'] += 1
            reasons[(lang, idx)].setdefault('why', []).append(f'{f}: no lemma')
            continue
        share = cap_share_of(stats, lang, lem)
        if share is None:
            diag[f'{lang}_lemma_not_in_corpus'] += 1
            reasons[(lang, idx)].setdefault('why', []).append(f'{f}->{lem}: lemma not in corpus')
            continue
        if share < threshold:
            diag[f'{lang}_lemma_mostly_lower_case'] += 1
            reasons[(lang, idx)].setdefault('why', []).append(
                f'{f}->{lem}: capitalized {share:.2f} of inner occurrences')
            continue
        ent_lemmas[lang][idx].add(lem)
        diag[f'{lang}_form_kept'] += 1
    candidate = {lg: {i: set(v) for i, v in ent_lemmas[lg].items()} for lg in ei.LANGS}
    proposals = {}
    if audit_fixes:
        from backend import entity_lemma_audit as ela
        proposals = ela.propose(entities, ent_lemmas, stats)
        for (lang, idx, lem), (action, why) in proposals.items():
            if action == 'drop' and dec.get((lang, idx, lem)) not in ('keep', 'other'):
                ent_lemmas[lang][idx].discard(lem)
                diag[f'{lang}_dropped_{why}'] += 1
    amb_lemmas = {lg: set() for lg in ei.LANGS}
    for (lang, idx, lem), v in dec.items():
        if v == 'drop':
            if lem in ent_lemmas[lang].get(idx, ()):
                ent_lemmas[lang][idx].discard(lem)
                diag[f'{lang}_dropped_by_model'] += 1
        elif v == 'other':
            amb_lemmas[lang].add(lem)
            diag[f'{lang}_lemma_judged_other'] += 1
    amb_tokens = {lg: set() for lg in ei.LANGS}
    for lang in ei.LANGS:
        if amb_lemmas[lang]:
            for f, lem in type_lemma[lang].items():
                if lem in amb_lemmas[lang]:
                    amb_tokens[lang].add(f)
    lemma_ents = {lg: collections.defaultdict(set) for lg in ei.LANGS}
    for lang in ei.LANGS:
        for idx, lems in ent_lemmas[lang].items():
            for lem in lems:
                lemma_ents[lang][lem].add(idx)
    no_lemma = collections.defaultdict(set)
    for lang in ei.LANGS:
        for idx in tried[lang]:
            if not ent_lemmas[lang].get(idx):
                no_lemma[lang].add(idx)
    tok2ents = {lg: {} for lg in ei.LANGS}
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
    n_over = 0
    if overrides:
        for lang, m in load_overrides(entities).items():
            for tok, es in m.items():
                cur = set(tok2ents[lang].get(tok, ()))
                new = cur | es
                if new != cur:
                    n_over += 1
                    tok2ents[lang][tok] = tuple(sorted(new))
    diag['override_tokens_added'] = n_over
    info = {'diag': dict(diag), 'no_lemma': no_lemma, 'tried': tried, 'ent_lemmas': ent_lemmas,
            'candidate_lemmas': candidate, 'proposals': proposals,
            'reasons': reasons, 'type_lemma': type_lemma, 'stats': stats,
            'cap_share': lambda lang, lem: cap_share_of(stats, lang, lem),
            'form_source': prep['form_source'], 'amb_tokens': amb_tokens}
    log('  lemma matcher: ' + ', '.join(f'{lg} {len(tok2ents[lg])} token types' for lg in ei.LANGS)
        + f', {time.time() - t0:.0f}s')
    return tok2ents, info


def build_lemma_matcher(entities, types, resolver, log=print, threshold=MAJORITY, audit_fixes=True,
                        overrides=True, decisions=None):
    prep = prepare_lemmas(entities, types, resolver, log=log)
    return assemble_matcher(entities, types, prep, threshold, audit_fixes, overrides, log=log,
                            decisions=decisions)


def window_triggers(text, t2e):
    """{eidx: [(raw token, folded token, candidate entity indexes)]}: every capitalized
    token of the window that the matcher assigns to the entity, in reading order."""
    out = {}
    for m in ei.WORD.finditer(text):
        raw = m.group(0)
        es = t2e.get(ei._fold_tok(raw))
        if not es or not is_cap(raw):
            continue
        f = ei._fold_tok(raw)
        for i in es:
            out.setdefault(i, []).append((raw, f, es))
    return out


def answers_by_index(entities, answers):
    """{(window id, sorted candidate indexes): chosen index, or -1 for none} from
    {(window id, candidate entity ids): chosen entity id or None}."""
    by_id = {e['entity_id']: i for i, e in enumerate(entities)}
    out = {}
    for (wid, cands), chosen in (answers or {}).items():
        if not all(c in by_id for c in cands):
            continue
        key = (wid, tuple(sorted(by_id[c] for c in cands)))
        out[key] = -1 if chosen is None else by_id.get(chosen, -1)
    return out


def trigger_state(wid, i, es, f, lang, amb_tokens, answers):
    """For one token of entity i: (survives, ambiguous, resolved). A token is ambiguous when
    two or more entities hold it or its lemma was judged to be another entity's name. An
    ambiguous token survives for the entity the window's answer names, and for every
    entity when the window has no answer."""
    ambiguous = amb_tokens is not None and (len(es) > 1 or f in amb_tokens.get(lang, ()))
    if not ambiguous:
        return True, False, False
    ans = answers.get((wid, es)) if answers else None
    if ans is None:
        return True, True, False
    return ans == i, True, True


def scan_windows_lemma(texts_conn, unit, tok2ents, log=print, amb_tokens=None, answers=None, collect=None):
    """Return (rows, wmeta, tally). rows: dict(eidx, wid, form, tok, homonym, lang) for the
    first surviving capitalized token of each (entity, window).

    With amb_tokens (stage 1d) a token shared by two entities, or one whose lemma the model
    judged to be another entity's name, is ambiguous. answers (from answers_by_index) says
    which candidate the window names, or -1 for none, and ambiguous tokens survive only for
    that candidate. collect, a dict, receives {(window id, candidates): (raw, lang, text)}
    for every ambiguous token that has no answer yet. Without amb_tokens the scan is the
    stage 1b one: every capitalized token counts and a shared lemma sets the homonym flag."""
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
        for i, trs in window_triggers(text, t2e).items():
            first = None
            for raw, f, es in trs:
                ok, amb, resolved = trigger_state(wid, i, es, f, lang, amb_tokens, answers)
                if amb and not resolved and collect is not None:
                    collect.setdefault((wid, es), (raw, lang, text))
                if ok and first is None:
                    first = (raw, f, (len(es) > 1) and not resolved)
            if first is None:
                tally['mentions_removed_by_answer'] += 1
                continue
            raw, f, hom = first
            if ei.COMB.match(raw[:1]):
                tally['mentions_first_char_is_mark'] += 1
            rows.append({'eidx': i, 'wid': wid, 'form': raw, 'tok': f,
                         'homonym': hom, 'lang': lang, 'nb': False, 'ds': False, 'conf': 'lemma',
                         'stem': 0, 'stopped': False, 'distinctive': False})
    tally['scan_seconds'] = round(time.time() - t0)
    return rows, wmeta, tally
