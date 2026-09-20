# Scripts

Most of what lives here is one-off or scheduled batch work: corpus imports,
index and cache builds, benchmark runs. See `docs/DATA_OPERATIONS.md` for the
production history of running any of these against the live site, and
`CLAUDE.md` for the general rule (Sonnet for mechanical batch work, cap
memory with `systemd-run --user --scope -p MemoryMax=<n>G`, one heavy job at
a time).

## build_connections_map.py

Builds the corpus connections map cache behind the Theme Search "Map" view
(`backend/connections_map.py`, `backend/blueprints/passages.py`'s
`/api/passages/map*` routes). For every Latin, Greek, English, Coptic and
Hebrew passage window at the fine scale, it finds the top 10 nearest windows
in OTHER works by cosine similarity over the passage index's own description
embeddings -- the same signal Theme Search and Similar Passages already use,
not a new computation -- excluding the same work, its part files, and other
versions of the same scripture passage. It writes both the window-level
edges and aggregates by work, author, century and genre to a SQLite file at
`cache/connections_map/<index_fingerprint>.db`, keyed by
`backend.passage_index.index_fingerprint()` so a rebuilt passage index
invalidates the cache the same way the density cache does. Translation pairs
are flagged two ways -- a curated list at `data/translation_pairs.json`, and
a heuristic (coverage + rank correlation of window position) whose
candidates are written to `cache/connections_map/aligned_candidates.txt` for
review -- so the map can hide them by default without hiding real allusion.

Run under a memory cap (peak observed on the full index: about 6 GB, 35-45
minutes; a first-chunk estimate is logged before the main pass commits to
the full run, and `CONN_MAP_ESTIMATE_ONLY=1` stops right after it):

```
systemd-run --user --scope -p MemoryMax=10G \
    venv/bin/python3 scripts/build_connections_map.py
```

Re-run it whenever the passage index is rebuilt (new texts added to the
content index, or a re-describe). On production, this should be run once
now and then again after every passage-index rebuild, the same rhythm the
density cache already follows.
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
