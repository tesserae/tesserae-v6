#!/usr/bin/env python3
"""Check prose against NC's writing rules before he has to.

NC has corrected the same handful of habits in draft after draft: em dashes,
semicolons, "surface" used as a verb, sentences with the subject dropped,
and clauses whose only job is to announce the next sentence. Each correction
was written down. Writing them down did not stop them recurring: on
2026-09-22 he cut "and it is worth explaining why, because it shapes what I
should ask for instead" from an email draft, and the rule against exactly
that had been recorded days earlier and not applied.

A rule that depends on remembering is not a rule. This makes them
mechanical, so a draft fails here instead of in front of him.

    python3 scripts/review/prose_check.py draft.md
    python3 scripts/review/prose_check.py --stdin < draft.txt
    python3 scripts/review/prose_check.py --list

Exit status is 1 when anything is found, so a hook or a script can stop on
it. `--warn-only` reports and exits 0.

WHAT THIS IS NOT. It does not judge whether the writing is any good, whether
a claim is true, or whether the argument holds. It catches the mechanical
tells NC has already told us about, which is the part of his reading time
worth giving back to him. See scripts/review/README.md for the wider plan.

Every rule here traces to a specific correction. Add one only when NC has
actually made it, and put his words in the rule's `why`.
"""
import argparse
import re
import sys

# Fenced code blocks, inline code and URLs are skipped: a semicolon in a
# shell command is not a writing problem, and an em dash inside a quoted
# error message is the error's, not ours.
_FENCE = re.compile(r'```.*?```', re.S)
_INLINE = re.compile(r'`[^`]*`')
_URL = re.compile(r'https?://\S+')


class Rule:
    # Case-insensitive by default: NC's prose starts sentences with capitals,
    # so a case-sensitive rule quietly misses every hit that opens a sentence.
    # The dropped-subject rule opts out, because a capital is exactly what it
    # keys on.
    def __init__(self, key, pattern, message, why, flags=re.I):
        self.key = key
        self.pattern = re.compile(pattern, flags)
        self.message = message
        self.why = why


RULES = [
    Rule('em-dash', r'—|--(?=\s)|(?<=\s)--',
         'em dash',
         'NC: no em dashes. Use a comma, a parenthesis, or two sentences. '
         'A known machine-writing tell.'),

    Rule('semicolon', r';',
         'semicolon',
         'NC: no semicolons, except inside an inline list whose items carry '
         'their own commas, or in a citation like (Smith 2020; Jones 2021).'),

    Rule('surface-verb',
         r'\b(surfaces|surfaced|surfacing)\b|\b(to|can|could|will|would|may|'
         r'might|should)\s+surface\b',
         '"surface" as a verb',
         'NC 2026-06-13, permanent: the noun is fine, the verb is banned. '
         'Use identify, rank, return, find, detect, capture, produce.'),

    Rule('meta-framing',
         r'\b(it is|it\'s) worth (explaining|noting|saying|checking|'
         r'mentioning)\b'
         r'|\bwhich (is worth|shapes what)\b'
         r'|\bthere (is|are) one thing\b'
         r'|\b(before I|let me) (explain|say|note) why\b'
         r'|\bwhat this (means|shapes) is\b'
         r'|\b(in summary|to summarize|to sum up)\b'
         r'|\bI want to address\b',
         'a clause announcing the next sentence',
         'NC 2026-09-22: "Don\'t give me the AI, \'and it is worth '
         'explaining, because it shapes . . .\' filler." Cut to the claim.'),

    Rule('not-x-but-y',
         r'\b(is|are|was|were|does|do)\s+not\s+\w[\w\s,]{0,40}?,?\s+(but|it is|'
         r'it\'s|they are)\b',
         'defining by negation ("not X but Y")',
         'NC: state what a thing is. Defining by negation smuggles in a '
         'straw man. A narrow contrast correcting a likely misreading is '
         'the one exception, so read the hit before cutting.'),

    # `[ \t]*`, not `\s*`. Code and URLs are blanked to spaces to keep line
    # numbers honest, and `\s` matches a newline, so `^\s*` walked from the
    # start of a blanked line across the break and matched the next line's
    # text while reporting the blanked line's number. A rule that points at
    # the wrong line is worse than no rule.
    Rule('subjectless',
         r'(?m)^[ \t]*(Hope|Hoping|Looking forward|Just checking|Wanted to|'
         r'Wondering|Thinking|Glad to|Happy to|Sorry for|Thanks for reaching)'
         r'\b',
         'a sentence with the subject dropped',
         'NC: keep the subject. "I hope", not "Hope". The dropped subject '
         'reads as undercooked in correspondence.',
         flags=re.M),

    Rule('hedge',
         r'\b(to be clear|as a matter of fact|in practice|essentially|'
         r'fundamentally|really very|quite a bit|fairly substantial|'
         r'extremely important|at the end of the day)\b',
         'a hedge that adds nothing',
         'NC: cut hedges that do not narrow the meaning.'),

    Rule('engineering-register',
         r'\b(memory footprint|cold[- ]start latency|throughput|regression '
         r'suite|failure[- ]prone|performant|leverage(?!s? the)|utilize)\b',
         'engineering-blog register',
         'NC 2026-06-15: plain phrasing for a reader who is not a sysadmin. '
         '"uses less memory", not "tighter memory footprint".'),

    Rule('colon-joining-clauses',
         r'(?m)^[^:\n]{25,}?[a-z,]\s*:\s+[a-z][^\n]{25,}$',
         'a colon joining two clauses',
         'NC: colons introduce lists. A colon joining clauses avoids '
         'committing to the logical relationship. Use two sentences.'),
]


def strip_uncheckable(text):
    """Blank out code and URLs, keeping offsets so line numbers stay true."""
    def blank(m):
        return re.sub(r'\S', ' ', m.group(0))
    text = _FENCE.sub(blank, text)
    text = _INLINE.sub(blank, text)
    text = _URL.sub(blank, text)
    return text


def check(text, only=None, skip=None):
    """[(line number, column, rule, the matched text), ...]"""
    cleaned = strip_uncheckable(text)
    starts = []
    pos = 0
    for line in cleaned.splitlines(keepends=True):
        starts.append(pos)
        pos += len(line)
    lines = cleaned.splitlines()

    def locate(idx):
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= idx:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1, idx - starts[lo] + 1

    found = []
    for rule in RULES:
        if only and rule.key not in only:
            continue
        if skip and rule.key in skip:
            continue
        for m in rule.pattern.finditer(cleaned):
            n, col = locate(m.start())
            snippet = lines[n - 1].strip() if n - 1 < len(lines) else ''
            found.append((n, col, rule, snippet))
    found.sort(key=lambda f: (f[0], f[1]))
    return found


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('paths', nargs='*', help='files to check')
    p.add_argument('--stdin', action='store_true', help='read from stdin')
    p.add_argument('--list', action='store_true', help='list the rules and exit')
    p.add_argument('--only', help='comma-separated rule keys to run')
    p.add_argument('--skip', help='comma-separated rule keys to ignore')
    p.add_argument('--warn-only', action='store_true',
                   help='report but exit 0')
    args = p.parse_args(argv)

    if args.list:
        for rule in RULES:
            print(f'{rule.key:22} {rule.message}')
            print(f'{"":22} {rule.why}')
        return 0

    only = set(args.only.split(',')) if args.only else None
    skip = set(args.skip.split(',')) if args.skip else None

    sources = []
    if args.stdin or not args.paths:
        sources.append(('(stdin)', sys.stdin.read()))
    for path in args.paths:
        with open(path, encoding='utf-8') as fh:
            sources.append((path, fh.read()))

    total = 0
    for name, text in sources:
        hits = check(text, only=only, skip=skip)
        total += len(hits)
        for n, col, rule, snippet in hits:
            print(f'{name}:{n}:{col}: {rule.message}')
            print(f'    {snippet[:100]}')
            print(f'    {rule.why}')
    if total:
        print(f'\n{total} to look at. Each rule traces to something NC said; '
              f'`--list` shows which.')
    return 0 if (args.warn_only or not total) else 1


if __name__ == '__main__':
    raise SystemExit(main())
