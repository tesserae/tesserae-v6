"""Deterministic answers for the questions users actually ask most.

A search assistant's traffic is dominated by a short list of recurring
questions, and a canned answer to those is faster, cheaper, and more accurate
than any generated one. The model is for the rest. This also means the assistant
still helps when the model is not running.

Matching is keyword-based on purpose: it is inspectable, it never drifts, and a
wrong match is a wrong FAQ rather than an invented fact. Anything not confidently
matched falls through to the model.
"""
import re

# Each rule: a set of keyword groups that must all appear, and the answer.
# Written as answers a scholar can act on, not definitions.
_RULES = [
    {
        'all': [('difference', 'differ', 'versus', 'vs', 'which'), ('lemma', 'exact')],
        'answer': ("An exact search matches the letters as you typed them, so it finds only that form. "
                   "A lemma search matches every inflected form of the same dictionary word, so a search "
                   "for arma also finds armis and armorum. Start with lemma for most literary questions, "
                   "and use exact when the specific form is the point."),
    },
    {
        'all': [('rare_pairs', 'rare pairs', 'rare word', 'rare_words', 'rare words'), ('what', 'how', 'when', 'why', 'difference')],
        'answer': ("Rare words finds single uncommon words two texts share; rare pairs finds uncommon "
                   "two-word combinations. Pairs are the stronger evidence, since two rare words together "
                   "by coincidence is far less likely than one. Both run in seconds, so they are a good "
                   "first pass before a full comparison."),
    },
    {
        'all': [('cross', 'different language', 'greek and latin', 'hebrew and greek', 'translation'), ('search', 'compare', 'find', 'parallel')],
        'answer': ("Use cross_language for texts in different languages. It works through a bilingual "
                   "dictionary and a phonetic channel rather than shared spelling, so it finds a Latin "
                   "line reworking a Greek one. Supported pairs include Greek with Latin, Hebrew with "
                   "Greek, Hebrew with Latin, and Latin with English."),
    },
    {
        'all': [('theme', 'topic', 'about', 'subject', 'scene'), ('search', 'find', 'how')],
        'answer': ("Theme search finds passages by what they contain rather than by their words, so you "
                   "can describe a scene (a city surrenders and hands over hostages) and get matches in "
                   "every language at once, including texts that share no vocabulary with your description. "
                   "Similar passages does the same from a passage you are already reading."),
    },
    {
        'all': [('score', 'ranking', 'ranked', 'number'), ('mean', 'means', 'what', 'how', 'interpret')],
        'answer': ("The score combines several independent measures: shared dictionary words, shared exact "
                   "forms, sound and spelling similarity, rare vocabulary, grammar, and meaning. A result "
                   "scores highly when several of those agree and when the shared words are rare in the "
                   "corpus as a whole. Read the channel labels on a result to see which evidence produced it."),
    },
    {
        'all': [('slow', 'long', 'taking', 'wait', 'time'),],
        'answer': ("A first comparison of two large works can take a few minutes, because every line of one "
                   "text is compared against every line of the other across all channels. The result is "
                   "cached, so the same comparison returns immediately afterwards. Rare words and rare pairs "
                   "are much faster if you want a quick look first."),
    },
    {
        'all': [('language', 'languages'), ('support', 'available', 'which', 'what')],
        'answer': ("Tesserae searches Latin, Greek, Hebrew, English and Coptic, and it can search across "
                   "those languages for texts that are related in different tongues. The corpus holds "
                   "roughly 2,100 works, most of them Latin and Greek."),
    },
]


def _norm(text):
    return re.sub(r'[^a-z0-9 ]', ' ', str(text or '').lower())


# Questions ABOUT the state of a feature, as opposed to what it does. A canned
# definition is the wrong answer to "is theme search working yet", and worse, the
# keyword rules cannot tell the two apart: "is theme search working" matches the
# theme rule on `theme` + `search` and returns the definition. A user who pushes
# back gets the identical answer, because the second question matches too. Seen
# in production 2026-08-25.
# Requests for ADVICE, as opposed to requests for a definition. "Recommend
# interesting searches across Hebrew and Greek" is a request for specific
# suggestions about this corpus; answering it with the definition of
# cross_language is useless, and that is what happened in production.
#
# The rules below match on topic keywords plus almost any question verb, so a
# question that merely MENTIONS a topic gets its definition. That is right for
# "what is theme search" and wrong for everything else. These markers say the
# user wants judgement, which only the model can give.
_ADVICE = (
    'recommend', 'suggest', 'interesting', 'should i', 'help me', 'best way',
    'where do i start', 'where should i', 'i want to', 'i am trying',
    "i'm trying", 'give me', 'show me', 'any ideas', 'what could', 'worth',
    'good place', 'starting point', 'investigate', 'explore',
)

_META = (
    'working', 'work yet', 'broken', 'available', 'deployed', 'live',
    'enabled', 'turned on', 'exist', 'ready yet', 'why is', 'why does',
    "why doesn't", 'why not', 'not answering', 'answer my question',
    'is it on', 'does it work', 'status',
)


def route(question):
    """Return a canned answer when the question clearly matches one, else None.

    Meta-questions fall through to the model, which can say what it does and
    does not know, rather than repeating a definition nobody asked for.
    """
    q = _norm(question)
    if not q.strip():
        return None
    if any(m in q for m in _META):
        return None
    if any(a in q for a in _ADVICE):
        return None
    for rule in _RULES:
        if all(any(term in q for term in group) for group in rule['all']):
            return rule['answer']
    return None
