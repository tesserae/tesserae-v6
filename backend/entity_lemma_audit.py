"""Audit of the entity lemma sets (stage 1c, 2026-10-17).

Each (entity, lemma) pair the lemma matcher keeps gets one proposed action.

    drop    a demonym or an adjective made from a place name (the lemma ends in one of the
            endings in entity_lemma_suffixes.json, the entity is a place, and the entity
            keeps another lemma in the same language without such an ending), or a common
            word (more than half of the lemma's inner occurrences are lower case).
    review  a lemma shared by two or more entities (homonym), a person's name that is also
            a place, or a place whose every lemma carries an ending (the ending may be part
            of its own name, as in Peneius).
    keep    anything else.

Only drop changes the table. Homonyms keep their mentions and their flag.
"""
import json
import os
import unicodedata

SUFFIX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'entity_lemma_suffixes.json')
_SUFFIXES = None
_EXEMPT = None


def suffixes():
    global _SUFFIXES
    if _SUFFIXES is None:
        _SUFFIXES = json.load(open(SUFFIX_PATH, encoding='utf-8'))
    return _SUFFIXES


def exempt(entity_id, lang, lemma):
    global _EXEMPT
    if _EXEMPT is None:
        _EXEMPT = {(x['entity_id'], x['lang'], x['lemma']) for x in suffixes().get('exempt', [])}
    return (entity_id, lang, lemma) in _EXEMPT


def bare(s):
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    return s.replace('ς', 'σ')


def suffix_of(lang, lemma):
    """The longest listed ending the lemma carries, or ''. A lemma that is only the ending
    (shorter than ending plus two letters) carries none."""
    w = bare(lemma) if lang == 'grc' else lemma.lower()
    best = ''
    for suf in suffixes().get(lang, []):
        cmp = bare(suf) if lang == 'grc' else suf
        if w.endswith(cmp) and len(w) >= len(cmp) + 2 and len(cmp) > len(bare(best) if lang == 'grc' else best):
            best = suf
    return best


def lower_share(stats, lang, lemma):
    s = stats[lang].get(lemma)
    if not s or s[0] == 0:
        return None
    if s[2]:
        return 1 - s[3] / s[2]
    return 1 - s[1] / s[0]


def propose(entities, ent_lemmas, stats):
    """{(lang, eidx, lemma): (action, reason)} for every kept (entity, lemma) pair."""
    holders = {}
    for lang, per in ent_lemmas.items():
        for idx, lems in per.items():
            for lem in lems:
                holders.setdefault((lang, lem), set()).add(idx)
    out = {}
    for lang, per in ent_lemmas.items():
        for idx, lems in per.items():
            etype = entities[idx]['type']
            has_plain = {lem for lem in lems if not (etype == 'place' and suffix_of(lang, lem)
                                                     and not exempt(entities[idx]['entity_id'], lang, lem))}
            for lem in lems:
                suf = suffix_of(lang, lem) if etype == 'place' and not exempt(entities[idx]['entity_id'], lang, lem) else ''
                ls = lower_share(stats, lang, lem)
                others = holders[(lang, lem)] - {idx}
                if suf and has_plain:
                    out[(lang, idx, lem)] = ('drop', 'demonym_or_adjective')
                elif ls is not None and ls > 0.5:
                    out[(lang, idx, lem)] = ('drop', 'common_word')
                elif others:
                    kinds = {entities[j]['type'] for j in others} | {etype}
                    why = 'person_also_place' if {'person', 'place'} <= kinds else 'homonym'
                    out[(lang, idx, lem)] = ('review', why)
                elif suf:
                    out[(lang, idx, lem)] = ('review', 'place_with_only_suffixed_lemmas')
                else:
                    out[(lang, idx, lem)] = ('keep', '')
    return out
