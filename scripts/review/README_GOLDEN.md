# The golden check: did anything change?

`golden_api.py` sends a fixed list of requests (`golden_requests.json`, about
seventy, covering every blueprint's main read paths) to a server and compares
the answers with a recording made earlier. A change that is meant to leave the
site's behaviour alone (a refactor, a split of a large module, new tests, a
dependency bump) must leave every answer the same. If one is different, the
change did something.

The answers are compared after removing keys that change from run to run
without the answer changing (timings, cache flags, build names: the list is
`GLOBAL_IGNORE` in the script, plus an `ignore` list on a request). Key order
is normalised. The order of lists is not, because the order of results is part
of the answer.

The check calls only routes that give the same answer twice. It leaves out
everything a language model writes (the summary and scholarship paragraphs in
Search One Text, Tessa, description writers, translation of commentary) and
everything that reaches a live outside service (Recent articles, Google Books,
CORE, GitHub). The Theme Search requests need the encoder service on port 8090
to be running.

## Two kinds of request that are not compared exactly

- `unordered`: a few answers are built from a Python set or dictionary, so the
  same items come back in a different order from one server process to the
  next (Python randomises string hashing at start). The request lists the keys
  whose lists are sorted before comparing (`rare_pairs`, `reader_reuse_marks`).
  The content is still compared in full; only the position of the items is not.
- `loose`: the fusion search (`fusion_la_pair`, `fusion_grc_pair`) and the
  cross-language search give a slightly different full answer in each server
  process (the number of candidates, the lowest-ranked results, a channel
  count on borderline pairs), also on the live site between its three
  workers. For these the check compares the identity of the top thirty results
  (source and target line) and passes when at least 80 percent are shared. To
  compare them exactly, start the recording server and the checked server with
  the same `PYTHONHASHSEED` (for example 0) and add `--strict`.

## Record

Record from the live site, or from a server you trust to be right:

    python3 scripts/review/golden_api.py record \
        --base https://tesserae.caset.buffalo.edu --out ~/golden/2026-10-12

This takes about five minutes. It writes one `NAME.json` per request and a
`manifest.json` (base address, the server's version answer, the time). Keep the
folder outside the repository. It is large (about 12 MB).

## Check a preview of a branch

Make a worktree of the branch, give it the production data (see "The preview
server" below), start it, and run:

    python3 scripts/review/golden_api.py check \
        --base http://127.0.0.1:5077 --against ~/golden/2026-10-12 --preview

The strictest check of a pure refactor needs no live recording: start a preview
of `main` and a preview of the branch both with `PYTHONHASHSEED=0`, record from
the first, check the second with `--strict`. Every request must be `same`.

It prints one line per request, `same` or `DIFFERENT` with the first lines of
a unified diff, and exits 1 if anything is different. `--only NAME` runs one
request. `--preview` skips the requests marked `skip_on_preview` in the list
(the ones a preview cannot answer the way the live site does: `texts_grc`,
because the live site cannot read the 17 Greek-named prose files in its
locale and lists them as poetry, which a preview with a UTF-8 locale does not).

## Check the live site after a deploy

    python3 scripts/review/golden_api.py check \
        --base https://tesserae.caset.buffalo.edu --against ~/golden/2026-10-12

Do this after every deploy of a structural change, with the recording made
before it. Data changes that were made on purpose (an import, an index
rebuild) show up as differences in the requests they touch. Re-record those
after the data change, and say so in the CHANGELOG.

## When a difference is meant

A change that is supposed to alter an answer (a fix, a new field) re-records
that request with the same pull request:

    python3 scripts/review/golden_api.py check --base ... --against DIR --update NAME

The CHANGELOG entry for the pull request says which requests were re-recorded
and why. A difference nobody can explain is a bug in the change.

## Finding unstable requests

    python3 scripts/review/golden_api.py stability --base http://127.0.0.1:5077

sends each request twice to the same server and lists any whose two answers
differ. Add the changing key to the request's `ignore` list, or drop the
request. Do this whenever a request is added.

## The preview server

A preview from a worktree needs the production data, read-only where it is
large and copied where the server writes:

- `data/` (copy, except `inverted_index` and `passage_index`, which are
  symlinks to the production folders; leave `usage` and `job_uploads` empty).
- `texts/<language>` copied from production, so the text set equals the live
  one. A symlinked text folder is rejected by `resolve_text_path`.
- `cache/lemmas` and `cache/bigrams` symlinked to production (30 GB and
  2.6 GB). The smaller caches (`frequencies`, `rare_words`, `lexical_density`,
  `passage_density`, `reuse_pairs`, `connections_map`, `scholarship`, charts)
  copied. Do not copy the top-level `cache/*.json` result caches, so fusion
  and search results are computed, not replayed.
- `backend/embeddings` symlinked to production.
- Python: the production venv by path, `/var/www/tesseraev6_flask/venv/bin/python`
  (read only; it matches what the live site runs).
- Start it under the job launcher with a cap of 12 GB (8 GB was killed by the
  kernel during a long run of Line Search, wildcard and Theme Search requests):

      ~/bin/tess-job preview-golden 12 bash -c "cd WORKTREE || exit 1; \
        export $(grep -E '^(THEME_READER_URL|THEME_READER_MODEL)=' /var/www/tesseraev6_flask/.env | xargs); \
        export PORT=5077 TESSERAE_MAX_WORKERS=1 TESSERAE_DOCUMENTS=1 \
        DEPLOYMENT_ENV=marvin SESSION_SECRET=anything-throwaway \
        DATABASE_URL=sqlite:////tmp/golden.db \
        TESSERAE_LANGUAGES=la,grc,en,cop,he,fa,ur,it,gmh,fro; \
        exec /var/www/tesseraev6_flask/venv/bin/python main.py"

  The first `export` gives the preview the address and name of the Theme
  Search re-ranking service (port 8091). Without it the preview does not
  re-rank, and every Theme Search request differs from the live recording
  (the recorded answers carry `reader` and `reader_score`). It prints
  no key: those two settings are an address and a model name.

  The database is not used by any request in the list. `DATABASE_URL` only has
  to be set so that the app starts, and the server logs a harmless "Failed to
  log search" line for the requests that record usage.
- Stop it when done: `systemctl --user stop tess-job-preview-golden-*.scope`
  for the scope you started.
