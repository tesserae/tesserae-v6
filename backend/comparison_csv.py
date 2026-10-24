"""The CSV of a comparison, with the columns of the page's CSV export.

client/src/components/search/exportHandlers.js (exportSearchCSV) is the model:
Rank, Source Locus, Source Text, Target Locus, Target Text, Score, Matched
Words, Channels; rows by fused score, high to low; tags stripped from the text;
matched surface words wrapped as **word** (client/src/utils/highlight.js
markMatchedWords); a UTF-8 byte order mark first so Excel reads Greek and
Coptic as Unicode.
"""
import csv
import re

HEADERS = ['Rank', 'Source Locus', 'Source Text', 'Target Locus', 'Target Text',
           'Score', 'Matched Words', 'Channels']

_TAG_RE = re.compile(r'<[^>]*>')
# The same edge punctuation highlight.js strips: . , ; : ! ? ' " ( ) em dash, en dash, hyphen.
_EDGE_LEAD = re.compile(r"^[.,;:!?'\"()—–-]+")
_EDGE_TRAIL = re.compile(r"[.,;:!?'\"()—–-]+$")


def _strip_edges(word):
    return _EDGE_TRAIL.sub('', _EDGE_LEAD.sub('', word))


def mark_matched_words(text, matched_words, side):
    """Wrap the matched surface words of one side in ** **, as the page's export does."""
    if not text or not matched_words:
        return text
    key = 'source_word' if side == 'source' else 'target_word'
    words = {m[key].lower() for m in matched_words
             if isinstance(m, dict) and m.get(key)}
    if not words:
        return text

    def mark(match):
        token = match.group(0)
        low = token.lower()
        stripped = _strip_edges(low)
        if stripped and stripped in words:
            start = low.index(stripped)
            return (token[:start] + '**' + token[start:start + len(stripped)] + '**'
                    + token[start + len(stripped):])
        return token

    return re.sub(r'\S+', mark, text)


def _score(r):
    for k in ('fused_score', 'score', 'overall_score'):
        if r.get(k) is not None:
            return r[k]
    return 0


def _side_text(r, side):
    node = r.get(side) or {}
    text = r.get(f'{side}_text') or r.get(f'{side}_snippet') or node.get('text') or ''
    return _TAG_RE.sub('', text)


def result_rows(results):
    """The CSV rows (lists of strings) for a list of result dicts, best score first."""
    rows = []
    for idx, r in enumerate(sorted(results, key=_score, reverse=True)):
        mw = r.get('matched_words') or []
        words = '; '.join(
            (w.get('lemma') or w.get('word') or '') if isinstance(w, dict) else str(w)
            for w in mw)
        rows.append([
            str(idx + 1),
            r.get('source_locus') or (r.get('source') or {}).get('ref') or '',
            mark_matched_words(_side_text(r, 'source'), mw, 'source'),
            r.get('target_locus') or (r.get('target') or {}).get('ref') or '',
            mark_matched_words(_side_text(r, 'target'), mw, 'target'),
            f'{_score(r):.3f}',
            words,
            '; '.join(r.get('channels') or []),
        ])
    return rows


def write_csv(path, results):
    """Write the file; return the number of result rows."""
    rows = result_rows(results)
    with open(path, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL, lineterminator='\n')
        w.writerow(HEADERS)
        w.writerows(rows)
    return len(rows)
