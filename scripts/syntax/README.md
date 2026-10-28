# Syntax parses for Latin and Greek: filling the gap after an import

The syntax channel reads one parse per line from `data/inverted_index/syntax_latin.db` and
`syntax_greek.db`. These scripts bring those databases up to date with the texts on disk and
build NEW database files. They never write over the live ones. The swap into production is a
separate, deliberate step.

## The ref rule

A line of a `.tess` file is read from a syntax database only when the row's `ref` is exactly the
text inside the angle brackets of that line, so `<lucr. 6.1189>` is read from the row whose `ref` is
`lucr. 6.1189`. `backend/fusion.py` (`find_syntax_matches`) and `backend/syntax_parser.py`
(`get_syntax_score_by_ref`) compare the two strings directly and nothing maps one form to the other.
The file is found by its exact file name in the `texts` table. A row stored under any other ref
(the early builds stored `adamnan.de_locis_santis urn:cts:latinLit:...1.1`) is never read.

## Scripts

| Script | What it does |
|---|---|
| `syntax_gap_lib.py` | The ref rule, `norm_key` (the comparison form of a line), `align` (matches lines to stored rows by text, never by position alone) |
| `gap_plan.py` | Reads the live database and the texts. Decides per file: rekey (give rows stored under another ref the line's tag), copy (a part file takes the rows of its whole work, a whole work the rows of its parts, a renamed work the rows stored under its old name), parse (lines still without a row), exclude (restricted texts and texts whose source bars online copies are not parsed). Writes `plan_<lang>.json` and `todo_<lang>.jsonl` |
| `parse_latinpipe.py` | Parses the todo lines with a local LatinPipe (`latin-evalatin24-240520`), in resumable chunks |
| `parse_greek_stanza.py` | Parses the todo lines with Stanza's default Ancient Greek models, in resumable chunks |
| `gap_build.py` | Copies the live database, applies the plan and the parses, rewrites `syntax_source`, runs `PRAGMA integrity_check` |
| `gap_check.py` | `coverage` (the table of files with a parse), `refs` (every line of ten new files resolves), `fusion` (the syntax channel returns results on the new file and none on the live one) |
| `agreement.py` | Parses lines already in a database and compares with the stored rows (token, lemma, part of speech, head, relation) |

## After an import, to rerun

1. `df -h /` first (each database copy is 1 to 2 GB, plus the parse files). Run every job through `~/bin/tess-job`.
2. Plan, once per language (about two minutes):
   `python scripts/syntax/gap_plan.py --lang la --db data/inverted_index/syntax_latin.db --texts texts/la --out-dir WORKDIR`
   and the same with `--lang grc --db .../syntax_greek.db --texts texts/grc`. The plan prints how many lines it will copy and parse.
3. Parse, one command per shard, each call under ten minutes, repeated until it prints `0 lines still to do`:
   - Latin needs a LatinPipe checkout with the model unpacked in it and a Python environment with
     `torch keras transformers ufal.chu-liu-edmonds ufal.udpipe numpy`. Clone `https://github.com/ufal/evalatin2024-latinpipe`,
     unpack `latinpipe-evalatin24-240520.tar.gz` from `https://hdl.handle.net/11234/1-5671` into it, and run
     `KERAS_BACKEND=torch python -s scripts/syntax/parse_latinpipe.py --repo CHECKOUT --todo WORKDIR/todo_la.jsonl --out WORKDIR/out_la_0.jsonl --budget 540 --threads 6 --shard 0/3`
     (then `--shard 1/3` and `2/3`, each with its own `--out`). A line the model cannot take (a sentence over
     the model's 512 subword positions, or over 1000 words) goes to `<out>.failed` with the reason and stays unparsed.
   - Greek needs `stanza==1.11.0` and the models in `~/stanza_resources` (`stanza.download('grc')`):
     `python -s scripts/syntax/parse_greek_stanza.py --resources ~/stanza_resources --todo WORKDIR/todo_grc.jsonl --out WORKDIR/out_grc_0.jsonl --budget 540 --threads 4 --shard 0/4`
     (shards 1/4 to 3/4 likewise).
   - Measured 2026-10-28 on the server's CPU: Latin about 1,400 words a second over three jobs, Greek about 65 lines a second per job.
4. Build, once per language:
   `python scripts/syntax/gap_build.py --lang la --live-db LIVE.db --texts texts/la --plan WORKDIR/plan_la.json --todo WORKDIR/todo_la.jsonl --parsed WORKDIR/out_la_*.jsonl --out WORKDIR/syntax_latin.db`
5. Check: `gap_check.py coverage`, `refs` and `fusion` on the new file, and `agreement.py` on a few works already in the database.
6. Swap by the usual route for index files (see `docs/DATA_OPERATIONS.md`), then clear the search caches that include the syntax channel.

## Decisions kept from the earlier builds

- Heads stay sentence-local. When the tokenizer splits one line into several sentences the rows hold
  each sentence's own head numbers, as the February (Latin) and March (Greek) builds did, so about one
  stored row in four has more than one root. `--shift-heads` on either parser makes heads line-wide.
  Changing it only for new rows would make old and new rows differ, so it is a decision for all rows.
- Greek: the March build called `stanza.Pipeline("grc", ...)` with no package, so Stanza used its default,
  `perseus`, while `syntax_source` says `grc_proiel`. The new parser does the same so that new rows match
  the old ones (agreement on lemma, part of speech, head and relation is 99.99 percent). The label was not
  changed.
