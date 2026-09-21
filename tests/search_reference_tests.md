# Tesserae V6 Search Reference Tests

Two of these now run themselves, and the third is still for a person.

    python scripts/reference_search_check.py        # the real corpus, a running site
    pytest tests/test_search_reference.py           # the machinery, on a fixture index

`scripts/reference_search_check.py` asks a running site the reference query
and exits non-zero if an author is missing or the count collapses. Run it at
the end of any deploy that touches search, indexing or text processing.
`tests/test_search_reference.py` builds a miniature index in the real schema
and runs the lookup code over it, so continuous integration can check the
wiring without a 2 GB index; it cannot see the corpus and says nothing about
recall.

THE RESULT CAP MATTERS, and it caught us out on 2026-09-21. A lemma search
deduplicates across a whole work and its book files AFTER applying the cap,
so the same query answers 323 at `max_results` 500 and 367 at 1,000. Every
figure below is at 1,000.

This document remains the record of what the numbers mean and when they
changed.

## Line Search (Lemma Mode)

### Test 1: "arma virum" (Latin)
**Query**: `arma virum`
**Language**: Latin
**Search Type**: Lemma

**Expected Results** (as of 2026-08-14; `total` == `distinct_loci`, deduplicated across whole-work and per-book/poem copies of the same line):
- Total ~320 results (grew from the older ~250 as the corpus expanded to include medieval and Neo-Latin texts)
- Must include (a search that drops these is broken):
  - **Vergil**: ~24 (Aeneid and others)
  - **Ovid**: ~14 (Amores, Fasti, Metamorphoses, etc.)
  - **Livy**: ~42
  - a broad span of eras and authors — e.g. Silius Italicus, Statius, Tacitus, and later Latin (William of Tyre, Eobanus)

**Red Flags** (indicates broken search):
- Ovid or Vergil missing entirely
- Fewer than ~150 total results
- Only one author/era represented

### Test 2: Verify diverse authors appear
For any corpus-wide lemma search, results should span multiple eras and authors, not just the most famous texts.

---

## String Search (Exact Mode)

### Test 1: "arma virum" (Latin)
**Query**: `arma virum`
**Language**: Latin
**Search Type**: Exact

**Expected Results** (as of 2026-08-14; `total` == `distinct_loci`, deduplicated across whole-work and per-book/poem copies. The older "8+/2+" figures counted the same line twice under a whole work and its part; the whole/part dedup now reports true distinct loci, roughly halving the raw counts. Exact search matches whole words — a trailing enclitic is allowed, so "arma virum" still hits Aeneid 1.1 "arma virumque cano"):
- Total ~21 results
- Must include:
  - **Vergil**: 4 (including Aeneid 1.1 "arma virumque cano")
  - **Ovid**: 1+
  - **Quintilian**: 1+
  - **Seneca**: 1+ (Epistulae 113.25)
  - **Statius**: 1+
  - **Martial**: 2

**Red Flags** (indicates broken search):
- Ovid, Quintilian, or Seneca missing
- Fewer than ~15 total results
- "aliquot annis"-style substring hits appearing for a two-word exact query (whole-word matching broken)
- The same line appearing twice under both a whole work and its part (whole/part dedup broken)

---

## Quick API Test Commands

### Line Search (Lemma)
```bash
curl -s -X POST "http://localhost:5000/api/line-search" \
  -H "Content-Type: application/json" \
  -d '{"query": "arma virum", "language": "la", "search_type": "lemma", "max_results": 500}' | python3 -c "
import sys, json
data = json.load(sys.stdin)
results = data.get('results', [])
authors = {}
for r in results:
    author = r.get('author', 'Unknown')
    authors[author] = authors.get(author, 0) + 1
print(f'Total: {len(results)}')
for a, c in sorted(authors.items(), key=lambda x: -x[1])[:10]:
    print(f'  {a}: {c}')
"
```

### String Search (Exact)
```bash
curl -s -X POST "http://localhost:5000/api/line-search" \
  -H "Content-Type: application/json" \
  -d '{"query": "arma virum", "language": "la", "search_type": "exact", "max_results": 200}' | python3 -c "
import sys, json
data = json.load(sys.stdin)
results = data.get('results', [])
authors = {}
for r in results:
    author = r.get('author', 'Unknown')
    authors[author] = authors.get(author, 0) + 1
print(f'Total: {len(results)}')
for a, c in sorted(authors.items(), key=lambda x: -x[1])[:10]:
    print(f'  {a}: {c}')
"
```

---

## Index Health Check

### Verify lines table is populated
```bash
python3 -c "
import sqlite3
for lang in ['la', 'grc', 'en']:
    db = f'data/inverted_index/{lang}_index.db'
    conn = sqlite3.connect(db)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM lines')
    count = c.fetchone()[0]
    print(f'{lang}: {count:,} lines')
    conn.close()
"
```

**Expected**:
- Latin: ~528,000 lines
- Greek: ~201,000 lines
- English: ~62,000 lines

**Red Flag**: If `lines` table doesn't exist or has 0 rows, run:
```bash
python backend/populate_lines_index.py all
```

---

## Common Issues and Fixes

### Issue: Search missing many expected results
**Cause**: `lines` table in inverted index is missing or empty
**Fix**: Run `python backend/populate_lines_index.py all`

### Issue: Ref format mismatch errors
**Cause**: Index refs don't match file refs
**Fix**: Repopulate lines table (stores text directly, avoiding ref lookup)

### Issue: CLTK warnings during indexing
**Status**: Expected/harmless - fallback tokenizer is used
