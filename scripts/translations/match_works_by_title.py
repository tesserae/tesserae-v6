"""Match our .tess works to Perseus works by author AND title, one to one.

Three rules, each of which alone would have caught the failure in the first run:

1. The author must agree. Title similarity on its own paired Catullus' Carmina
   with Aethelwulf's Carmen de abbatibus.
2. The title must agree well, and it must beat the runner-up by a clear margin.
   Plutarch's essays have similar titles, and a near-tie means we do not know.
3. A Perseus work may serve at most one of our works. One Perseus text answering
   for thirty-seven different works is the signature of a broken match, so the
   pipeline is not allowed to express it at all.
"""
import json
import re
import unicodedata

import os
_W = os.environ.get('TESSERAE_PERSEUS_WORK', '/home/ncoffee/perseus_trans/work')
CATALOGUE = f'{_W}/perseus_catalogue.json'
TESS_INDEX = f'{_W}/tess_index.json'
OUT = f'{_W}/work_map.json'

# Words that carry no identifying force in a classical title, in either language.
TITLE_STOP = {
    'de', 'in', 'ad', 'ex', 'cum', 'pro', 'contra', 'adversus', 'super',
    'liber', 'libri', 'librorum', 'lib', 'the', 'of', 'on', 'a', 'an', 'to',
    'and', 'or', 'against', 'for', 'from', 'with', 'his', 'her', 'their',
    'peri', 'pros', 'kata', 'eis', 'epi', 'tou', 'tes', 'ton', 'twn',
    'fragmenta', 'fragments', 'fragment', 'opera', 'works', 'work',
}
# Author-name stopwords: praenomina, honorifics, and the parts of a Roman name
# that identify a family rather than a writer.
AUTHOR_STOP = {
    'm', 'p', 'l', 'c', 'q', 'a', 't', 'g', 'd', 'n', 'sex', 'ti', 'cn', 'sp',
    'st', 'aur', 'iunior', 'junior', 'maior', 'major', 'minor', 'the', 'of',
    'saint', 'st', 'sanctus', 'pseudo', 'ps', 'flavius', 'aurelius', 'valerius',
    'claudius', 'publius', 'marcus', 'lucius', 'gaius', 'caius', 'quintus',
    'titus', 'sextus', 'aulus', 'gnaeus', 'decimus', 'servius', 'maccius',
}


def _fold(s):
    s = unicodedata.normalize('NFKD', str(s or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()


def _tokens(s, stop):
    return {t for t in _fold(s).split() if t and t not in stop and len(t) > 1}


def _stem(tok):
    """Crude Latin/English stem so vergil matches vergilius, ovid matches ovidius."""
    for suf in ('ius', 'us', 'is', 'es', 'ae', 'um', 'os', 'on', 'a', 'e', 'i', 's'):
        if len(tok) - len(suf) >= 4 and tok.endswith(suf):
            return tok[:-len(suf)]
    return tok


def _author_agrees(tess_author, perseus_authors):
    """True when a name part of ours matches a name part of theirs."""
    ours = {_stem(t) for t in _tokens(tess_author, AUTHOR_STOP)}
    if not ours:
        return False
    for pa in perseus_authors:
        theirs = {_stem(t) for t in _tokens(pa, AUTHOR_STOP)}
        for o in ours:
            for t in theirs:
                if o == t:
                    return True
                # vergil / vergili, cicero / ciceron: allow a prefix of length 5+.
                if len(o) >= 5 and len(t) >= 5 and (o.startswith(t) or t.startswith(o)):
                    return True
    return False


# Book and part numbers are the whole difference between Alcibiades 1 and
# Alcibiades 2, or Philippic 1 and Philippic 3, and they are exactly what a
# token-overlap score throws away. Any title carrying one must match on it.
_ROMAN = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5, 'vi': 6, 'vii': 7,
          'viii': 8, 'ix': 9, 'x': 10, 'xi': 11, 'xii': 12}
_ORDINAL = {'minor': 1, 'maior': 2, 'major': 2, 'prior': 1, 'posterior': 2,
            'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5}


def _numerals(title):
    out = set()
    for tok in _fold(title).split():
        if tok.isdigit():
            out.add(int(tok))
        elif tok in _ROMAN:
            out.add(_ROMAN[tok])
        elif tok in _ORDINAL:
            out.add(_ORDINAL[tok])
    return out


def _title_score(tess_title, perseus_titles):
    """Best containment score over every title Perseus records for the work."""
    ours = {_stem(t) for t in _tokens(tess_title, TITLE_STOP)}
    our_nums = _numerals(tess_title)
    if not ours:
        return 0.0, ''
    best, best_t = 0.0, ''
    for t in perseus_titles:
        their_nums = _numerals(t)
        if (our_nums or their_nums) and our_nums != their_nums:
            continue
        theirs = {_stem(x) for x in _tokens(t, TITLE_STOP)}
        if not theirs:
            continue
        shared = ours & theirs
        # Containment in both directions, so a short title inside a long one
        # still scores, but a one-word overlap in two long titles does not.
        score = len(shared) / max(1, min(len(ours), len(theirs)))
        score *= (len(shared) / max(len(ours), len(theirs))) ** 0.5
        if score > best:
            best, best_t = score, t
    return round(best, 3), best_t


MIN_TITLE = 0.60      # below this we do not claim to know the work
MIN_MARGIN = 0.15     # and the winner must be this far clear of the runner-up


def main():
    cat = json.load(open(CATALOGUE, encoding='utf-8'))
    tess = json.load(open(TESS_INDEX, encoding='utf-8'))

    # Candidate pairs, author-gated.
    scored = []
    for key, meta in tess.items():
        lang = meta.get('lang')
        if lang not in ('la', 'grc'):
            continue
        work = meta.get('work') or key.split('/', 1)[-1]
        author_slug, _, title_slug = work.partition('.')
        if not title_slug:
            continue
        cands = []
        for urn, pw in cat.items():
            if pw['repo_lang'] != lang:
                continue
            if not _author_agrees(author_slug, pw['authors']):
                continue
            titles = [t for group in pw['titles'].values() for t in group]
            titles += [tr['label'] for tr in pw['translations'] if tr['label']]
            s, matched = _title_score(title_slug, titles)
            if s > 0:
                cands.append((s, urn, matched))
        if not cands:
            continue
        cands.sort(reverse=True)
        top = cands[0]
        runner = cands[1][0] if len(cands) > 1 else 0.0
        scored.append({
            'tess': key, 'lang': lang, 'urn': top[1], 'title_score': top[0],
            'runner_up': runner, 'margin': round(top[0] - runner, 3),
            'perseus_title': top[2], 'perseus_author': cat[top[1]]['authors'][0],
        })

    accepted, rejected = [], []
    for m in scored:
        if m['title_score'] < MIN_TITLE:
            m['reason'] = f"title score {m['title_score']} below {MIN_TITLE}"
            rejected.append(m)
        elif m['margin'] < MIN_MARGIN and m['title_score'] < 0.999:
            m['reason'] = f"ambiguous: runner-up at {m['runner_up']}"
            rejected.append(m)
        else:
            accepted.append(m)

    # One Perseus work may serve at most one of ours. Best score wins the tie;
    # everyone else is dropped rather than silently duplicated.
    by_urn = {}
    for m in sorted(accepted, key=lambda x: (-x['title_score'], -x['margin'])):
        if m['urn'] in by_urn:
            m['reason'] = f"urn already claimed by {by_urn[m['urn']]['tess']}"
            rejected.append(m)
        else:
            by_urn[m['urn']] = m

    final = sorted(by_urn.values(), key=lambda m: m['tess'])
    for m in final:
        m['translations'] = cat[m['urn']]['translations']

    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump(final, fh, ensure_ascii=False, indent=1)

    print(f'tess works considered: {len(tess)}')
    print(f'author-gated candidates: {len(scored)}')
    print(f'ACCEPTED (1:1, author+title): {len(final)}')
    by_lang = {}
    for m in final:
        by_lang[m['lang']] = by_lang.get(m['lang'], 0) + 1
    print(f'  by language: {by_lang}')
    print(f'rejected: {len(rejected)}')
    reasons = {}
    for m in rejected:
        k = m['reason'].split(':')[0].split(' below')[0]
        reasons[k] = reasons.get(k, 0) + 1
    print(f'  reasons: {reasons}')
    print('\nspot check, multi-work authors:')
    for m in final:
        if any(a in m['tess'] for a in ('plutarch.', 'cicero.', 'plato.')):
            print(f"  {m['tess']:52s} -> {m['urn']:18s} {m['perseus_title'][:44]}")


if __name__ == '__main__':
    main()
