"""What did the reader actually ask? One judgment, made once, by the model.

WHY THIS EXISTS

NC: "We discussed earlier that the idea was that the AI would do at least a
little bit of thinking, but it seems now we're having to hardcode every rule.
What's the deal?"

The deal, measured: agent.py had grown to 1,748 lines holding 130 literal
phrases across 9 lists, and it decided what a question meant by substring
match. Adding "site" to one of those lists was the fix for the bug that
prompted the question, and it would not have been the last.

The router does two different jobs and gave them the same tool:

  1. "A quoted phrase needs which search?" Mechanical. A lookup is right, it
     costs nothing, and it is kept exactly as it was.
  2. "Is this about the site or the corpus? Is it a follow-up? What is its
     subject?" These are JUDGMENTS. Substring matching cannot do judgment, and
     the list is never finished.

This module does the second job, in one call, because all three questions are
decided at the same moment about the same sentence and there is no reason to
ask three times.

WHAT MADE THE OLD BEHAVIOUR HARMFUL RATHER THAN MERELY INCOMPLETE

A list that failed to match did not fall through to something that could think.
It fell into a *different* branch that assumed the question was a follow-up. So
a miss was not a shrug, it was a confident wrong answer: NC asked about the
site's search capabilities and watched Tessa search the corpus for "arma
virumque", inherited from the previous turn.

Hence `UNSURE`. When the model is unavailable or answers with nonsense, this
says so rather than guessing, and the caller keeps the old heuristics. A
classifier that fails closed is the whole point.

MEASUREMENT, not argument: evaluation/scripts/routing_probe.py holds 43
labelled questions and scores both this and the heuristics it replaces.
"""
import json
import os
import re
import threading
import time

from backend.logging_config import get_logger
from backend.assistant import model

logger = get_logger('assistant.classify')

# Kinds. Deliberately few: every one of these routes somewhere different, and a
# taxonomy the model cannot hold in its head is a taxonomy it will guess at.
KINDS = ('site', 'corpus', 'theme', 'holdings', 'read')
UNSURE = 'unsure'

_ENABLED = os.environ.get('TESSERAE_MODEL_ROUTING', '1') not in ('0', 'false', 'no')
_TIMEOUT = float(os.environ.get('TESSERAE_ROUTING_TIMEOUT', '6'))

SYSTEM = """You classify a question typed into Tesserae, a search tool for
finding textual parallels in classical literature (Latin, Greek, English,
Coptic, Hebrew).

Reply with JSON only. No prose, no explanation.

  kind      one of:
    site      asks about Tesserae itself: what a feature is, how to use it,
              what the search types are, how to export or cite, why a search
              behaved a certain way. The documentation answers it.
    corpus    asks where words or phrases occur in the texts.
    theme     describes a SUBJECT or scene in the reader's own words rather
              than naming words to look for ("a storm at sea", "a warrior
              arming"). The words themselves need not appear anywhere.
    holdings  asks what the corpus CONTAINS: which authors, works, how many.
    read      wants to open a work and read it continuously ("let me read
              Aeneid 6"). Asking to SEE THE LINES a search found is not this:
              that is still "corpus".

  carries_subject   true if the question does not say what it is about and
                    only makes sense as a follow-up to the previous exchange
                    ("what about Ovid?", "and in Greek?", "any earlier ones?").
                    false if it names its own subject, and ALWAYS false when
                    kind is "site".

                    Naming the texts or authors TO WORK ON is not the same as
                    naming a subject to carry. "compare Statius Thebaid 12 with
                    Vergil Aeneid 1" is a complete instruction and carries
                    nothing, even straight after a search for something else.

  subject   if carries_subject is true, the phrase or topic from the PREVIOUS
            exchange, copied exactly. Otherwise null.

            It is never a new name introduced by this question. An author or
            work named here narrows WHERE to look; the subject is still what
            the previous exchange was about. "Can you give the Eobanus
            instances?", after an exchange about "arma virumque", carries
            "arma virumque" and not "Eobanus": the reader wants that phrase in
            that author, and searching for the author's name finds only lines
            that mention him.

  scope     the author or work the question restricts the search to, if it
            names one, copied as written ("Eobanus", "Ovid", "the Aeneid").
            null if it names none. This is WHERE to look, never WHAT to look
            for.

Judge what the reader MEANT. A question naming a feature of the site is about
the site even though it contains words that also appear in the texts."""

EXAMPLES = [
    ("tell me about the site's search capabilities", None,
     {'kind': 'site', 'carries_subject': False, 'subject': None, 'scope': None}),
    ('what is fusion search?', None,
     {'kind': 'site', 'carries_subject': False, 'subject': None, 'scope': None}),
    ('where does furor appear?', None,
     {'kind': 'corpus', 'carries_subject': False, 'subject': None, 'scope': None}),
    ('what about Ovid?', 'I found "arma virumque" at Vergil, Aeneid 1.1.',
     {'kind': 'corpus', 'carries_subject': True, 'subject': 'arma virumque',
      'scope': 'Ovid'}),
    ('are there any passages about a storm at sea?', None,
     {'kind': 'theme', 'carries_subject': False, 'subject': None, 'scope': None}),
    ('what texts do you have by Ovid?', None,
     {'kind': 'holdings', 'carries_subject': False, 'subject': None, 'scope': None}),
    ('let me read Aeneid 6', None,
     {'kind': 'read', 'carries_subject': False, 'subject': None, 'scope': 'Aeneid 6'}),
    # The two the first version got wrong, kept as examples so a later prompt
    # change cannot quietly lose them again.
    ('show me the actual lines', 'I found 12 occurrences of "arma virumque".',
     {'kind': 'corpus', 'carries_subject': True, 'subject': 'arma virumque',
      'scope': None}),
    ('compare Statius Thebaid 12 with Vergil Aeneid 1',
     'I found "arma virumque" at Vergil, Aeneid 1.1.',
     {'kind': 'corpus', 'carries_subject': False, 'subject': None, 'scope': None}),
    # The author here is the SCOPE, not the subject. Taking "Eobanus" as the
    # subject searched for lines mentioning his name instead of the phrase in
    # his work, and the answer then had nothing genuine to quote.
    ('Can you give the Eobanus instances?',
     'The phrase "arma virumque" appears at Vergil, Aeneid 1.1 and in later poets.',
     {'kind': 'corpus', 'carries_subject': True, 'subject': 'arma virumque',
      'scope': 'Eobanus'}),
]


class Decision:
    __slots__ = ('kind', 'carries', 'subject', 'scope', 'source', 'seconds')

    def __init__(self, kind, carries, subject, source, seconds=0.0, scope=None):
        self.kind = kind
        self.carries = bool(carries)
        self.subject = subject or None
        # WHERE to look, as opposed to what for. Added after the subject fix
        # moved the failure rather than closing it: the classifier correctly
        # carried "arma virumque" out of "Can you give the Eobanus instances?"
        # and then nothing carried "Eobanus", so the answer listed every author
        # in the corpus and none of the reader's.
        self.scope = scope or None
        self.source = source            # 'model' | 'unsure'
        self.seconds = seconds

    @property
    def usable(self):
        return self.kind in KINDS

    def as_probe(self):
        return {'kind': self.kind, 'carries': self.carries,
                'subject': self.subject}

    def __repr__(self):
        return (f'<Decision {self.kind} carries={self.carries} '
                f'subject={self.subject!r} via {self.source} '
                f'{self.seconds:.2f}s>')


# One question asked twice in a session should not be paid for twice. Small and
# bounded: this is a latency cache, not a store.
_CACHE = {}
_CACHE_MAX = 512
_lock = threading.Lock()


def _last_assistant(history):
    for turn in reversed(history or []):
        if (turn or {}).get('role') == 'assistant' and (turn.get('text') or '').strip():
            return turn['text'].strip()
    return None


def _prompt(question, previous):
    lines = []
    for q, prev, ans in EXAMPLES:
        if prev:
            lines.append(f'Previous answer: {prev}')
        lines.append(f'Question: {q}')
        lines.append(json.dumps(ans))
        lines.append('')
    if previous:
        # Truncated: the classifier needs the SUBJECT of the last answer, not
        # the whole of it, and a long answer would crowd out the question.
        lines.append(f'Previous answer: {previous[:400]}')
    lines.append(f'Question: {question}')
    return '\n'.join(lines)


def _parse(raw):
    m = re.search(r'\{.*?\}', raw or '', re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    kind = str(d.get('kind') or '').strip().lower()
    if kind not in KINDS:
        return None
    carries = bool(d.get('carries_subject'))
    subject = d.get('subject')
    subject = str(subject).strip() if subject else None
    # A site question carries nothing, whatever the model says. This is the
    # exact failure being fixed, so it is enforced rather than requested.
    if kind == 'site':
        carries, subject = False, None
    if carries and not subject:
        carries = False
    scope = d.get('scope')
    scope = str(scope).strip() if scope else None
    return kind, carries, subject, scope


def classify(question, history=None):
    """One judgment about one question. Never raises."""
    question = (question or '').strip()
    if not question or not _ENABLED:
        return Decision(UNSURE, False, None, 'unsure')

    previous = _last_assistant(history)
    key = (question.lower(), (previous or '')[:200].lower())
    with _lock:
        hit = _CACHE.get(key)
    if hit:
        return hit

    started = time.time()
    try:
        raw = model.complete(SYSTEM, _prompt(question, previous),
                             max_tokens=90, temperature=0.0)
    except Exception as e:                                   # noqa: BLE001
        # The model server is single-slot and shared with the answer path, so
        # "busy" is a normal outcome, not an exception worth shouting about.
        logger.info('[CLASSIFY] model unavailable: %s', e)
        return Decision(UNSURE, False, None, 'unsure', time.time() - started)

    parsed = _parse(raw)
    took = time.time() - started
    if not parsed:
        logger.info('[CLASSIFY] unparseable: %r', (raw or '')[:120])
        return Decision(UNSURE, False, None, 'unsure', took)

    kind, carries, subject, scope = parsed
    out = Decision(kind, carries, subject, 'model', took, scope=scope)
    with _lock:
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.clear()
        _CACHE[key] = out
    return out
