# Scripts

## Corpus-wide reuse table

`scripts/reuse/build_reuse_table.py --language <lang>` builds the corpus-wide
verbatim/near-verbatim line-reuse table behind the Reader's "quoted in N
works" mark and Reuse tab (`GET /api/reuse/line`, `GET /api/reuse/marks`,
`backend/reuse_table.py`). It reads the live corpus from `texts/<lang>/` (so a
retired file, simply absent there, is never included even if a stale lemma
cache for it lingers), surface tokens from each work's plain
`cache/lemmas/<lang>/<text_id>.json`, and writes
`cache/reuse_pairs/<lang>.db`. Latin only as of 2026-09-19. Run it once per
language under a memory-capped scope
(`systemd-run --user --scope -p MemoryMax=12G venv/bin/python3
scripts/reuse/build_reuse_table.py --language la`; Latin took about 7
minutes) and rebuild after any corpus change to that language -- see
docs/DATA_OPERATIONS.md for the run history and
`research/reuse_table/REPORT_2026-09-18.md` for the scoring design (the
n-gram/Jaccard/containment thresholds and why they are set where they are).
