"""Prompts, answer parsing and decision tables for the entity model pass (stage 1d,
2026-10-17). The gateway client is backend/entity_gateway.py, the matcher hooks are in
backend/entity_lemma.py. Nothing here reads a private file.

Pass one asks, for one (entity, lemma) pair, whether the lemma is a name of the entity.
Pass two asks, for one window and the entities that share a token in it, which of them the
window names.
"""
import re
import unicodedata

PASS1_ANSWERS = ('yes', 'demonym', 'other', 'common')
MAX_WINDOW_WORDS = 400

PASS1_SYSTEM = (
    'A list of ancient names is being checked. You see one entity, one lemma (a dictionary form, written without '
    'accents), the capitalized forms in which the lemma occurs, and example lines from the corpus. Say how the lemma '
    'relates to the entity. Compare the lemma with the entity\'s label and the other names listed for it first. If the '
    'lemma is the label, another name of the entity, or an ordinary inflection or spelling of one of them, the answer '
    'is yes. An entity whose label is a patronymic such as \'son of Atreus\' has the patronymic (Atrides, Atridae) as '
    'its name, so that is yes.\n'
    'yes: the lemma is a name of this entity. Examples: Atreus for Atreus, Medea for Medea, Mutina for Mutina, Colchis '
    'for Colchis, Atrides for \'son of Atreus\', Menapii for the Menapii.\n'
    'demonym: the lemma is an adjective, or a word for the inhabitants, descendants or followers, made from the '
    'entity\'s name, or a person\'s name taken from a place. Examples: Romanus for Rome, Achaeus (adjective) for '
    'Achaea, Elysius for Elysium, Coriolanus for Corioli, Latius for Latium.\n'
    'other: the lemma is the name of a different person, place, ship, festival or group that happens to share the '
    'spelling. Examples: Argo (the ship) for Argos, Daedala (the festival) for Daedalus.\n'
    'common: the lemma is an ordinary word and not a name.\n'
    'Reply with one word only: yes, demonym, other or common.')

PASS2_SYSTEM = (
    'You help read Latin, Greek and English passages. You are given a passage, a capitalized word in it, '
    'and a numbered list of candidate entities (people, places or gods) that the word could name. '
    'Decide which candidate the passage names at that word, using the surrounding text. Reply with the '
    'number of the candidate only. Reply 0 when none of the candidates is named there, for example when '
    'the word is another person or place, an adjective, a people, or an ordinary word.')


def parse_pass1(text):
    """One of PASS1_ANSWERS, or None when the reply starts with none of them."""
    if not text:
        return None
    w = re.sub(r'[^a-z]', '', text.strip().lower().split()[0]) if text.strip() else ''
    for a in PASS1_ANSWERS:
        if w == a:
            return a
    for a in PASS1_ANSWERS:
        if w.startswith(a):
            return a
    return None


def parse_pass2(text, n_candidates):
    """The chosen number (0 for none, 1..n for a candidate), or None for an unusable reply."""
    if not text:
        return None
    m = re.search(r'\d+', text)
    if not m:
        return None
    v = int(m.group(0))
    return v if 0 <= v <= n_candidates else None


def entity_names(entity, limit=8):
    names = sorted({x for k in entity['keys'] for x in k['latin']} |
                   {x.strip() for k in entity['keys'] for x in (k.get('english') or '').split('/') if x.strip()})
    return names[:limit]


def pass1_prompt(entity, lemma, lang, forms, snippets):
    ids = ', '.join(entity.get('pleiades') or []) or 'none'
    ident = f"Pleiades {ids}" if entity.get('pleiades') else 'no Pleiades identifier'
    lines = [f"Entity: {entity['label']} ({entity['type']}; {ident}; id {entity['entity_id']})",
             'Other names listed for it: ' + (', '.join(entity_names(entity)) or '(none)'),
             f"Language of the texts: {lang}",
             f"Lemma: {lemma}",
             'Most frequent capitalized forms: ' + (', '.join(forms) if forms else '(none)'),
             'Example lines:']
    for i, s in enumerate(snippets, 1):
        lines.append(f'{i}. {s}')
    if not snippets:
        lines.append('(none)')
    return '\n'.join(lines)


def line_snippet(text, raw, width=100):
    """The line of the window that holds `raw`, cut to about 2*width characters around it."""
    for line in text.split('\n'):
        k = line.find(raw)
        if k >= 0:
            line = re.sub(r'\s+', ' ', line).strip()
            k = line.find(raw)
            a = max(0, k - width)
            return line[a:k + len(raw) + width]
    return re.sub(r'\s+', ' ', text)[:2 * width]


def clip_words(text, raw, limit=MAX_WINDOW_WORDS):
    """The window text, or the `limit` words around the first occurrence of `raw`."""
    words = text.split()
    if len(words) <= limit:
        return text.strip()
    at = next((i for i, w in enumerate(words) if raw in w), 0)
    a = max(0, min(at - limit // 2, len(words) - limit))
    return ' '.join(words[a:a + limit])


def pass2_prompt(window_text, raw, candidates):
    """candidates: list of dicts with label, type, description."""
    lines = ['Passage:', window_text, '', f'Capitalized word: {raw}', 'Candidates:']
    for i, c in enumerate(candidates, 1):
        lines.append(f"{i}. {c['label']} ({c['type']}). {c['description']}")
    lines.append('0. none of these')
    return '\n'.join(lines)


ABBREVIATIONS = ('ca', 'c', 'cf', 'ch', 'st', 'mt', 'b.c', 'a.d', 'e.g', 'i.e', 'vs', 'no', 'ft', 'km', 'sp')


def first_sentence(s, limit=160):
    """The first sentence of a description, not breaking after an abbreviation such as 'ca.'
    or 'B.C.'."""
    s = re.sub(r'\s+', ' ', s or '').strip()
    for m in re.finditer(r'([A-Za-z.]+)[.!?]\s+(?=[A-Z])', s):
        if m.group(1).lower().rstrip('.') in ABBREVIATIONS or len(m.group(1)) == 1:
            continue
        return s[:m.end()].strip()[:limit]
    return s[:limit]


def author_of(work):
    return unicodedata.normalize('NFC', (work or '').split('.')[0].replace('_', ' '))
