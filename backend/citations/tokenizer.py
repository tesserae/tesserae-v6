"""
Tokenizer for canonical-citation recognition, reimplementing the token
vocabulary of CitationParser's ANTLR lexer (cp_lexer.g: INT, PUNTO, VIRGOLA,
HYPHEN, SEMICOL, WS(hidden), BRACKETS(skipped), LITERAL = CHAR+ PUNCT* CHAR*)
in plain Python/regex, plus two extensions the original grammar did not need:
en/em dashes as range hyphens (running prose uses them; the original grammar,
built for edited citation lists, only saw ASCII '-'), and treating adjacent
whitespace between two locus-shaped tokens as an implicit level separator
(needed for "I 1" / "i. 1" Roman-numeral-book citations).

A LITERAL token here corresponds to one CitationParser.LITERAL: a run of
letters optionally capped with a trailing period, with no internal spaces
('Verg.', 'Aen', 'ff.', 'OT'). Two LITERALs separated only by whitespace stay
separate tokens (as in the original grammar, where WS is hidden but does not
merge LITERALs); the parser layer decides how many consecutive LITERALs make
up a work-abbreviation prefix.
"""
import re
from dataclasses import dataclass

_RAW_RE = re.compile(r"""
    (?P<NUM>\d+)
  | (?P<HYPH>[-‐‑‒–—])
  | (?P<SEMI>;)
  | (?P<COMMA>,)
  | (?P<COLON>:)
  | (?P<DOT>\.)
  | (?P<PAREN>[()\[\]])
  | (?P<WS>\s+)
  | (?P<WORD>[^\W\d_]+)
""", re.VERBOSE | re.UNICODE)


@dataclass
class Token:
    type: str      # NUM, LIT, DOT, COMMA, HYPH, SEMI, PAREN, OTHER
    text: str
    start: int
    end: int


def raw_scan(text):
    """First pass: yield (type, text, start, end) for every char run,
    including a synthetic OTHER token for anything the grammar above does not
    match (so offsets stay contiguous and unknown characters act as citation
    boundaries rather than being silently skipped)."""
    pos = 0
    n = len(text)
    for m in _RAW_RE.finditer(text):
        if m.start() > pos:
            yield Token("OTHER", text[pos:m.start()], pos, m.start())
        kind = m.lastgroup
        yield Token(kind, m.group(), m.start(), m.end())
        pos = m.end()
    if pos < n:
        yield Token("OTHER", text[pos:n], pos, n)


def tokenize(text):
    """Second pass: merge WORD (+ immediately-adjacent DOT, no gap) into a
    single LIT token; drop WS and PAREN (skipped, like the original grammar's
    BRACKETS rule which calls self.skip()); keep everything else."""
    raw = list(raw_scan(text))
    out = []
    i = 0
    n = len(raw)
    while i < n:
        t = raw[i]
        if t.type == "WS" or t.type == "PAREN":
            i += 1
            continue
        if t.type == "WORD":
            start = t.start
            end = t.end
            txt = t.text
            # absorb an immediately-adjacent DOT (no whitespace between)
            if i + 1 < n and raw[i + 1].type == "DOT" and raw[i + 1].start == end:
                txt += "."
                end = raw[i + 1].end
                i += 1
            out.append(Token("LIT", txt, start, end))
            i += 1
            continue
        if t.type == "NUM":
            out.append(Token("NUM", t.text, t.start, t.end))
            i += 1
            continue
        if t.type == "DOT":
            out.append(Token("DOT", t.text, t.start, t.end))
            i += 1
            continue
        if t.type == "COMMA":
            out.append(Token("COMMA", t.text, t.start, t.end))
            i += 1
            continue
        if t.type == "COLON":
            out.append(Token("COLON", t.text, t.start, t.end))
            i += 1
            continue
        if t.type == "HYPH":
            out.append(Token("HYPH", t.text, t.start, t.end))
            i += 1
            continue
        if t.type == "SEMI":
            out.append(Token("SEMI", t.text, t.start, t.end))
            i += 1
            continue
        # OTHER: boundary marker, kept so the parser can stop a scan at it
        out.append(Token("OTHER", t.text, t.start, t.end))
        i += 1
    return out
