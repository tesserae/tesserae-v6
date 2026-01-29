# Tesserae V6 Search Reference Tests

This document contains reference test cases to verify search functionality is working correctly.
Run these tests manually after any changes to search or indexing code.

## Line Search (Lemma Mode)

### Test 1: "arma virum" (Latin)
**Query**: `arma virum`
**Language**: Latin
**Search Type**: Lemma

**Expected Results**:
- Total matches should be approximately 250+ results
- Must include:
  - **Ovid**: ~26 matches (Amores, Fasti, Metamorphoses, etc.)
  - **Vergil**: ~2 matches (Aeneid)
  - **Livy**: ~72 matches
  - **Cicero**: ~8 matches
  - **Curtius Rufus**: ~10 matches

**Red Flags** (indicates broken search):
- Ovid missing entirely
- Less than 50 total results
- Only showing Vergil

### Test 2: Verify diverse authors appear
For any corpus-wide lemma search, results should span multiple eras and authors, not just the most famous texts.

---

## String Search (Exact Mode)

### Test 1: "arma virum" (Latin)
**Query**: `arma virum`
**Language**: Latin
**Search Type**: Exact

**Expected Results**:
- Total matches should be approximately 35-40 results
- Must include:
  - **Ovid**: 2+ matches
  - **Quintilian**: 2+ matches
  - **Seneca**: 1+ match
  - **Vergil**: 8+ matches (including Aeneid 1.1.1 "arma virumque cano")
  - **Statius**: 2+ matches
  - **Persius**: 1+ match

**Red Flags** (indicates broken search):
- Ovid, Quintilian, or Seneca missing
- Less than 20 total results

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
