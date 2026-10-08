#!/usr/bin/env python3
"""Drop specific reference lines out of one work, everywhere a line is
self-describing enough for a surgical removal to be safe, and name what is
not.

WHY THIS EXISTS

An import sometimes carries lines that are not the author's: a later
editor's introduction, a footnote, a signed essay, bundled into the same
.tess file as the poem it prefaces. (First case, 2026-10-08: a signed,
dated 20th-century introduction to a critical edition, bundled whole into
a diwan file as a contiguous block of over a hundred lines, with page
citations and a signature and date at its close.) The fix is not a full
reimport -- the surrounding lines are fine -- it is dropping exactly those
lines, everywhere a copy of them (or something keyed to their position)
survives.

Remaining lines keep their ORIGINAL ref labels. Nothing is renumbered. A
gap in the sequence (line .712 followed by .855) is the intended result:
it says plainly that something was removed, rather than quietly closing
over it, and it means every other store that names a line by its ref
string (not by its position) needs no renumbering at all.

WHAT THIS SCRIPT DOES, AND WHAT IT DELIBERATELY DOES NOT

Three stores are self-describing enough per line (or per row) that this
script can edit them directly and safely, the same copy-modify-verify-swap
pattern as remove_restricted_text.py and drop_stale_index_entries.py:

  text      texts/<lang>/<file>.tess            -- drop the matching lines
  index     data/inverted_index/<lang>_index.db -- delete the matching rows
            from `lines` and `postings` (keyed by ref, not position),
            lower `texts.line_count`, and rebuild `lemma_doc_freq` with the
            canonical per-WORK rule (scripts/build_inverted_index's own
            build_lemma_doc_freq -- the same function drop_stale_index_
            entries.py calls, for the same reason: a plain recount after a
            delete is wrong for any partitioned work)
  vectors   backend/embeddings/<lang>/<work>.npy + its .meta.json -- each
            row's ref is carried in meta.json's own `line_refs` list, so
            the matching rows can be dropped by ref and every remaining
            row's embedding is untouched (the text it embeds did not
            change; nothing needs recomputing)
  windows   data/passage_index/window_texts.db -- the `window_texts` rows
            whose ref_start..ref_end range (by file ORDER, not by parsing
            the numbers in the ref, since Urdu's refs are
            work.ghazal.N.M and do not sort numerically) overlaps a
            CONTIGUOUS RUN of dropped refs are removed outright, along
            with their matching rows in ids.json, embeddings.npy and
            descriptions.jsonl -- the three stores the running passage
            index loads together and refuses to load at all if they
            disagree (backend/passage_index.py's `_ensure_loaded`) -- and
            their own cached line text in window_texts.db's `lines`
            table. ids.json, embeddings.npy and descriptions.jsonl are
            kept in lockstep deliberately (2026-10-08: a run of this
            script dropped 37 windows from ids.json and descriptions.jsonl
            but left embeddings.npy untouched, so the two counts fell out
            of step by 37 rows and the passage index would not load
            site-wide -- Similar Passages and Theme Search both down --
            until the extra rows were removed by hand); apply_drop
            computes all three together and asserts they still agree,
            in row count, before any of the four files is swapped into
            place, restoring every backup and refusing to finish if they
            do not. Runs, not the first-to-last span of everything asked
            for, is deliberate too: two scattered refs (say, two footnotes
            many lines apart) must drop only the windows actually
            touching each one, never everything between them.
            There is no replacement text to re-window with, so the gap
            left by a dropped window is left for the overlap of
            neighbouring windows to cover, not patched.

What this script does NOT do, because the data it would need is not
self-describing by ref and a full recompute is the only honest fix -- it
reports what is affected and prints the follow-up commands, for the main
session to run, in the order that must hold:

  lemmas    cache/lemmas/<lang>/ cache files are named by content hash;
            editing the .tess file already orphans the old one (the next
            request lemmatizes the new content under a new hash). This
            script deletes the now-stale file so an orphan does not sit on
            disk, and names the eager-rebuild command.
  bigrams   cache/bigrams/<lang>_bigrams.json counts rare bigrams across
            the whole language; a delete does not know what to subtract.
            Full rebuild: scripts/corpus/rebuild_bigrams.py.
  freq      cache/frequencies/<lang>.json self-heals (checksum mismatch;
            see verify_text_coverage.py) -- no action needed.
  names     data/passage_index/window_names.db is built FROM window_texts.db
            (scripts/corpus/build_window_names.py); once windows are
            dropped it is stale and must be rebuilt, whole-corpus.
  connmap   cache/connections_map/*.db is fingerprinted to the passage
            index's own state (scripts/build_connections_map.py's
            docstring); once windows are dropped the live cache's
            fingerprint no longer matches and a fresh one must be built,
            whole-corpus.

Dry run by default, like every script under scripts/corpus/ that writes to
data/ (docs/DATA_OPERATIONS.md; implemented in corpus_safety.py). PLANNING
is separated from APPLYING on purpose: plan_drop only reads, so it can run
against a toy fixture in a test with no risk, and is what apply_drop then
acts on.

    venv/bin/python scripts/corpus/drop_lines_from_work.py fa khayyam.diwan \\
        --ref-range khayyam.diwan.713:khayyam.diwan.854
    venv/bin/python scripts/corpus/drop_lines_from_work.py fa khayyam.diwan \\
        --ref-range khayyam.diwan.713:khayyam.diwan.854 --apply --root /var/www/tesseraev6_flask

    venv/bin/python scripts/corpus/drop_lines_from_work.py ur ghalib.diwan_wikisource \\
        --refs ghalib.diwan_wikisource.ghazal.62.9,ghalib.diwan_wikisource.ghazal.131.22 --apply
"""
import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from scripts.corpus.corpus_safety import (  # noqa: E402
    add_apply_argument, atomic_write, backup, read_lines_preserving_eol,
)

REF_LINE = re.compile(r'^<([^>]+)>\t(.*)$')


class LockstepError(RuntimeError):
    """Raised by apply_drop when ids.json, embeddings.npy and
    descriptions.jsonl would not (or already do not) agree in row count.
    Every backup taken so far is restored before this is raised, so the
    live files are left exactly as they were when apply_drop was called."""


# ---------------------------------------------------------------------------
# PLANNING -- read-only, safe against a fixture or the real server alike.
# ---------------------------------------------------------------------------
def _tess_path(root, lang, filename):
    return os.path.join(root, 'texts', lang, filename)


def read_tess_lines(path):
    """[(ref, raw_line)] in file order. raw_line keeps its own line ending
    (see corpus_safety.read_lines_preserving_eol) so a rewrite changes
    nothing about the lines it keeps."""
    out = []
    for raw in read_lines_preserving_eol(path):
        m = REF_LINE.match(raw.rstrip('\r\n'))
        if m:
            out.append((m.group(1), raw))
    return out


def plan_drop(lang, filename, refs_to_drop, root='.'):
    """Everything dropping `refs_to_drop` from texts/<lang>/<filename> would
    touch. Read-only. Raises ValueError if a requested ref is not in the
    file (the caller asked to drop something that is not there -- almost
    always a typo in the range, never safe to silently ignore)."""
    refs_to_drop = set(refs_to_drop)
    path = _tess_path(root, lang, filename)
    if not os.path.exists(path):
        raise ValueError(f'no such text: {path}')
    tess_lines = read_tess_lines(path)
    present = {ref for ref, _ in tess_lines}
    missing = sorted(refs_to_drop - present)
    if missing:
        raise ValueError(f'{len(missing)} requested ref(s) not found in {filename}: '
                          + ', '.join(missing[:5]) + (' ...' if len(missing) > 5 else ''))

    order = {ref: i for i, (ref, _) in enumerate(tess_lines)}
    drop_positions = sorted(order[ref] for ref in refs_to_drop)
    lo, hi = min(drop_positions), max(drop_positions)

    plan = {
        'lang': lang, 'filename': filename, 'root': root,
        'tess_path': path,
        'refs_to_drop': sorted(refs_to_drop, key=lambda r: order[r]),
        'total_lines': len(tess_lines),
        'remaining_lines': len(tess_lines) - len(refs_to_drop),
        'drop_span': (tess_lines[lo][0], tess_lines[hi][0]),
    }
    plan['index'] = _plan_index(root, lang, filename, refs_to_drop)
    plan['vectors'] = _plan_vectors(root, lang, filename, refs_to_drop)
    plan['lemma_cache'] = _plan_lemma_cache(root, lang, filename)
    plan['windows'] = _plan_windows(root, lang, filename, order, drop_positions)
    return plan


def _plan_index(root, lang, filename, refs_to_drop):
    db_path = os.path.join(root, 'data', 'inverted_index', f'{lang}_index.db')
    if not os.path.exists(db_path):
        return {'present': False, 'db_path': db_path}
    con = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    try:
        row = con.execute('select text_id, line_count from texts where filename=?',
                           (filename,)).fetchone()
        if row is None:
            return {'present': True, 'db_path': db_path, 'in_index': False}
        text_id, line_count = row
        marks = ','.join('?' * len(refs_to_drop))
        n_lines = con.execute(
            f'select count(*) from lines where text_id=? and ref in ({marks})',  # nosec B608
            [text_id, *refs_to_drop]).fetchone()[0]
        n_post = con.execute(
            f'select count(*) from postings where text_id=? and ref in ({marks})',  # nosec B608
            [text_id, *refs_to_drop]).fetchone()[0]
    finally:
        con.close()
    return {'present': True, 'db_path': db_path, 'in_index': True, 'text_id': text_id,
            'old_line_count': line_count, 'matching_line_rows': n_lines,
            'matching_posting_rows': n_post}


def _plan_vectors(root, lang, filename, refs_to_drop):
    base = filename[:-len('.tess')] if filename.endswith('.tess') else filename
    npy = os.path.join(root, 'backend', 'embeddings', lang, f'{base}.npy')
    meta = os.path.join(root, 'backend', 'embeddings', lang, f'{base}.meta.json')
    if not (os.path.exists(npy) and os.path.exists(meta)):
        return {'present': False, 'npy_path': npy, 'meta_path': meta}
    m = json.load(open(meta, encoding='utf-8'))
    refs = m.get('line_refs') or []
    hit = [i for i, r in enumerate(refs) if r in refs_to_drop]
    return {'present': True, 'npy_path': npy, 'meta_path': meta,
            'old_rows': len(refs), 'matching_rows': len(hit), 'row_indices': hit}


def _CACHE_HASH_strip(name):
    return re.sub(r'-[0-9a-f]{32}$', '', name)


def _plan_lemma_cache(root, lang, filename):
    base = filename[:-len('.tess')] if filename.endswith('.tess') else filename
    lang_dir = os.path.join(root, 'cache', 'lemmas', lang)
    if not os.path.isdir(lang_dir):
        return {'present': False, 'files': []}
    files = [fn for fn in sorted(os.listdir(lang_dir))
             if fn.endswith('.json') and _CACHE_HASH_strip(fn[:-len('.json')]) == base]
    return {'present': True, 'files': files, 'dir': lang_dir}


def _contiguous_runs(positions):
    """Group sorted, deduplicated file-order position ints into (lo, hi)
    runs of CONSECUTIVE integers. Two dropped refs 69 lines apart are two
    one-line runs, not one 70-line run -- the distinction a scattered
    `--refs` (two unrelated footnotes) needs and a single `--ref-range`
    (one contiguous block) never notices, since it is one run already."""
    runs = []
    start = prev = None
    for p in positions:
        if start is None:
            start = prev = p
        elif p == prev + 1:
            prev = p
        else:
            runs.append((start, prev))
            start = prev = p
    if start is not None:
        runs.append((start, prev))
    return runs


def _plan_windows(root, lang, filename, order, drop_positions):
    """Windows (and their ids.json/embeddings.npy/descriptions.jsonl/
    cached-text rows) whose ref_start..ref_end span, read back by FILE
    ORDER (not by parsing the ref string -- Urdu's ghazal.N.M refs do not
    sort numerically), overlaps ANY contiguous run of `drop_positions`.

    Deliberately NOT "overlaps the span from the first dropped position to
    the last": two scattered refs (e.g. two footnotes many lines apart)
    must only take the windows that touch one of them, not the ~193
    windows for everything printed between the two footnotes that this
    script would otherwise have planned to drop (production, 2026-10-08,
    caught before --apply)."""
    wdb = os.path.join(root, 'data', 'passage_index', 'window_texts.db')
    desc_path = os.path.join(root, 'data', 'passage_index', 'descriptions.jsonl')
    ids_path = os.path.join(root, 'data', 'passage_index', 'ids.json')
    emb_path = os.path.join(root, 'data', 'passage_index', 'embeddings.npy')
    base = filename[:-len('.tess')] if filename.endswith('.tess') else filename
    if not os.path.exists(wdb):
        return {'present': False, 'wdb_path': wdb}
    con = sqlite3.connect(f'file:{wdb}?mode=ro', uri=True)
    try:
        rows = con.execute(
            'select id, ref_start, ref_end from window_texts where language=? and work=?',
            (lang, base)).fetchall()
    finally:
        con.close()
    runs = _contiguous_runs(drop_positions)
    hit_ids = []
    for wid, rs, re_ in rows:
        o1, o2 = order.get(rs), order.get(re_)
        if o1 is None or o2 is None:
            continue  # a ref outside this edit's view of the file; not our concern
        if any(o1 <= hi and o2 >= lo for lo, hi in runs):
            hit_ids.append(wid)
    hit_ids_set = set(hit_ids)
    desc_hits = ids_hits = 0
    emb_old_rows = None
    if os.path.exists(desc_path):
        with open(desc_path, encoding='utf-8') as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get('id') in hit_ids_set:
                    desc_hits += 1
    if os.path.exists(ids_path):
        ids_hits = sum(1 for wid in json.load(open(ids_path, encoding='utf-8')) if wid in hit_ids_set)
    if os.path.exists(emb_path):
        import numpy as np
        emb_old_rows = int(np.load(emb_path, mmap_mode='r').shape[0])
    return {'present': True, 'wdb_path': wdb, 'desc_path': desc_path, 'ids_path': ids_path,
            'emb_path': emb_path, 'emb_present': emb_old_rows is not None,
            'emb_old_rows': emb_old_rows,
            'window_ids': hit_ids, 'total_windows': len(rows),
            'description_rows': desc_hits, 'winvec_rows': ids_hits}


def format_plan(plan):
    lines = [f"Drop plan: {plan['filename']} ({plan['lang']}), root {plan['root']}", '']
    lines.append(f"  dropping {len(plan['refs_to_drop'])} of {plan['total_lines']} lines "
                 f"(span {plan['drop_span'][0]} .. {plan['drop_span'][1]}); "
                 f"{plan['remaining_lines']} remain")
    idx = plan['index']
    if not idx.get('present'):
        lines.append(f"  index: not present on this checkout ({idx['db_path']})")
    elif not idx.get('in_index'):
        lines.append('  index: file not present in this index (nothing to touch there)')
    else:
        lines.append(f"  index: {idx['matching_line_rows']} line row(s), "
                     f"{idx['matching_posting_rows']} posting row(s); "
                     f"line_count {idx['old_line_count']} -> "
                     f"{idx['old_line_count'] - len(plan['refs_to_drop'])}")
    vec = plan['vectors']
    if not vec.get('present'):
        lines.append(f"  vectors: not present ({vec.get('npy_path')})")
    else:
        lines.append(f"  vectors: {vec['matching_rows']} of {vec['old_rows']} row(s) to drop")
    lc = plan['lemma_cache']
    lines.append(f"  lemma cache: {len(lc.get('files', []))} file(s) to remove (orphaned by the edit)")
    win = plan['windows']
    if not win.get('present'):
        lines.append(f"  windows: not present ({win.get('wdb_path')})")
    else:
        emb_note = (f"{win['winvec_rows']} embeddings.npy row(s) of {win['emb_old_rows']}"
                    if win.get('emb_present') else 'embeddings.npy not present')
        lines.append(f"  windows: {len(win['window_ids'])} of {win['total_windows']} window(s) overlap; "
                     f"{win['description_rows']} description row(s), {win['winvec_rows']} ids.json row(s), "
                     f"{emb_note}")
    lines.append('')
    lines.append('  NOT done by this script (whole-language/whole-corpus; run after --apply):')
    lines.append(f"    venv/bin/python scripts/batch_lemma_cache.py {plan['lang']} --force")
    lines.append(f"    venv/bin/python scripts/corpus/rebuild_bigrams.py {plan['lang']}")
    if win.get('present') and win['window_ids']:
        lines.append('    venv/bin/python scripts/corpus/build_window_names.py <out.db>   '
                     '# then swap in as data/passage_index/window_names.db')
        lines.append('    systemd-run --user --scope -p MemoryMax=10G '
                     'venv/bin/python3 scripts/build_connections_map.py')
    return '\n'.join(lines)


def _restore_backups(backups):
    """backups: {live_path: backup_path_or_None}. Copies each backup back
    over its live path -- an abort must leave every file exactly as it was
    before apply_drop touched it. A None value means the file did not
    exist before this call and is left alone, never invented."""
    for live_path, b in backups.items():
        if b and os.path.exists(b):
            shutil.copy2(b, live_path)


# ---------------------------------------------------------------------------
# APPLYING -- writes, only with --apply.
# ---------------------------------------------------------------------------
def apply_drop(plan, tag=None):
    tag = tag or time.strftime('dropped-%Y%m%d')
    report = []

    # 1. text -- rebuild from the raw file (not read_tess_lines' filtered
    # view) so a stray non-ref line (there should be none in a well-formed
    # .tess, but one must not be silently eaten) is kept untouched.
    drop = set(plan['refs_to_drop'])
    b = backup(plan['tess_path'], tag=tag)
    new_lines = []
    for raw in read_lines_preserving_eol(plan['tess_path']):
        m = REF_LINE.match(raw.rstrip('\r\n'))
        if m and m.group(1) in drop:
            continue
        new_lines.append(raw)
    atomic_write(plan['tess_path'], new_lines)
    report.append(f"text: rewrote {plan['tess_path']} (backup: {b}), "
                  f"{len(plan['refs_to_drop'])} line(s) dropped")

    # 2. index
    idx = plan['index']
    if idx.get('present') and idx.get('in_index'):
        db_path = idx['db_path']
        bdb = backup(db_path, tag=tag)
        new_path = db_path + '.new'
        shutil.copy2(db_path, new_path)
        con = sqlite3.connect(new_path)
        try:
            marks = ','.join('?' * len(drop))
            text_id = idx['text_id']
            con.execute(f'delete from lines where text_id=? and ref in ({marks})',  # nosec B608
                        [text_id, *drop])
            con.execute(f'delete from postings where text_id=? and ref in ({marks})',  # nosec B608
                        [text_id, *drop])
            con.execute('update texts set line_count = line_count - ? where text_id=?',
                        (len(drop), text_id))
            sys.path.insert(0, plan['root'])
            try:
                from scripts.build_inverted_index import build_lemma_doc_freq
                build_lemma_doc_freq(con, verbose=False)
            except ImportError:
                pass  # fixture/test dbs without a lemma_doc_freq table
            con.commit()
            assert con.execute('pragma integrity_check').fetchone()[0] == 'ok'
            con.execute('VACUUM')
        finally:
            con.close()
        os.replace(db_path, f'{db_path}.bak-swap-{tag}')
        os.replace(new_path, db_path)
        report.append(f"index: swapped {db_path} (backup: {bdb}, pre-swap copy "
                      f"{db_path}.bak-swap-{tag})")
    else:
        report.append('index: nothing to do')

    # 3. vectors
    vec = plan['vectors']
    if vec.get('present') and vec['matching_rows']:
        import numpy as np
        bnpy = backup(vec['npy_path'], tag=tag)
        bmeta = backup(vec['meta_path'], tag=tag)
        arr = np.load(vec['npy_path'])
        keep_mask = [i not in set(vec['row_indices']) for i in range(arr.shape[0])]
        new_arr = arr[keep_mask]
        np_tmp_base = vec['npy_path'][:-len('.npy')] + f'.tmp-{os.getpid()}'
        np.save(np_tmp_base, new_arr)  # np.save appends .npy itself
        os.replace(np_tmp_base + '.npy', vec['npy_path'])
        m = json.load(open(vec['meta_path'], encoding='utf-8'))
        m['line_refs'] = [r for i, r in enumerate(m.get('line_refs') or []) if keep_mask[i]]
        m['n_lines'] = len(m['line_refs'])
        atomic_write(vec['meta_path'], json.dumps(m, ensure_ascii=False, indent=1))
        report.append(f"vectors: dropped {vec['matching_rows']} row(s) from "
                      f"{vec['npy_path']} (backups: {bnpy}, {bmeta})")
    else:
        report.append('vectors: nothing to do')

    # 4. lemma cache -- delete the now-stale file(s); a correct one is
    # rebuilt lazily on next search, or eagerly by batch_lemma_cache.py.
    lc = plan['lemma_cache']
    for fn in lc.get('files', []):
        path = os.path.join(lc['dir'], fn)
        b = backup(path, tag=tag)
        os.remove(path)
        report.append(f"lemma cache: removed {path} (backup: {b}; stale, orphaned by the content change)")

    # 5. windows -- ids.json, embeddings.npy and descriptions.jsonl are kept
    # in lockstep (module docstring, 2026-10-08): all three are prepared
    # here and their row counts compared BEFORE any of the four window
    # stores is swapped into place; every backup taken is restored, and
    # LockstepError raised, rather than leaving the index able to load with
    # the wrong passage behind an id or (worse) refusing to load at all.
    win = plan['windows']
    if win.get('present') and win['window_ids']:
        hit = set(win['window_ids'])
        backups = {win['wdb_path']: backup(win['wdb_path'], tag=tag)}

        # window_texts.db -- deletions prepared in a copy; not swapped in yet.
        new_wdb_path = win['wdb_path'] + '.new'
        shutil.copy2(win['wdb_path'], new_wdb_path)
        con = sqlite3.connect(new_wdb_path)
        try:
            marks = ','.join('?' * len(hit))
            con.execute(f'delete from window_texts where id in ({marks})', list(hit))  # nosec B608
            base = plan['filename'][:-len('.tess')] if plan['filename'].endswith('.tess') else plan['filename']
            con.execute('delete from lines where work=? and ref in ({})'.format(  # nosec B608
                ','.join('?' * len(drop))), [base, *drop])
            con.commit()
            assert con.execute('pragma integrity_check').fetchone()[0] == 'ok'
            con.execute('VACUUM')
        finally:
            con.close()

        def _abort(msg):
            _restore_backups(backups)
            if os.path.exists(new_wdb_path):
                os.remove(new_wdb_path)
            raise LockstepError(msg + ' Every backup has been restored; nothing was left changed.')

        orig_ids, new_ids = None, None
        if os.path.exists(win['ids_path']):
            backups[win['ids_path']] = backup(win['ids_path'], tag=tag)
            orig_ids = json.load(open(win['ids_path'], encoding='utf-8'))
            new_ids = [wid for wid in orig_ids if wid not in hit]

        new_desc_lines, n_desc_dropped, desc_row_count = None, 0, None
        if os.path.exists(win['desc_path']):
            backups[win['desc_path']] = backup(win['desc_path'], tag=tag)
            kept, valid = [], 0
            with open(win['desc_path'], encoding='utf-8') as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        kept.append(line)
                        continue
                    if r.get('id') in hit:
                        n_desc_dropped += 1
                        continue
                    kept.append(line)
                    if isinstance(r, dict) and 'id' in r:
                        valid += 1
            new_desc_lines, desc_row_count = kept, valid

        new_emb = None
        emb_path = win.get('emb_path')
        if orig_ids is not None and emb_path and os.path.exists(emb_path):
            import numpy as np
            backups[emb_path] = backup(emb_path, tag=tag)
            arr = np.load(emb_path, mmap_mode='r')
            if arr.shape[0] != len(orig_ids):
                _abort(f"embeddings.npy ({arr.shape[0]} rows) and ids.json ({len(orig_ids)} ids) "
                       f"were already out of lockstep before this run touched anything.")
            keep_mask = [wid not in hit for wid in orig_ids]
            new_emb = np.ascontiguousarray(arr[keep_mask])
            del arr

        # Validate the three stay in lockstep BEFORE anything live changes.
        counts = {}
        if new_ids is not None:
            counts['ids.json'] = len(new_ids)
        if new_emb is not None:
            counts['embeddings.npy'] = int(new_emb.shape[0])
        if desc_row_count is not None:
            counts['descriptions.jsonl'] = desc_row_count
        if len(set(counts.values())) > 1:
            _abort(f"ids/embeddings/descriptions would not agree after the drop ({counts}).")

        # Validated; swap all four window stores in together. A failure
        # partway restores every backup rather than leaving some new and
        # some old.
        try:
            if new_emb is not None:
                import numpy as np
                tmp_base = emb_path[:-len('.npy')] + f'.tmp-{os.getpid()}'
                np.save(tmp_base, new_emb)  # np.save appends .npy itself
                os.replace(tmp_base + '.npy', emb_path)
            if new_desc_lines is not None:
                atomic_write(win['desc_path'], new_desc_lines)
            if new_ids is not None:
                atomic_write(win['ids_path'], json.dumps(new_ids, ensure_ascii=False))
            os.replace(win['wdb_path'], f"{win['wdb_path']}.bak-swap-{tag}")
            os.replace(new_wdb_path, win['wdb_path'])
        except BaseException:
            _restore_backups(backups)
            raise

        # Post-write check against what is now actually on disk: belt and
        # suspenders against a mistake in the counting above, not only in
        # the swap. Still refuses (and restores) rather than finishing.
        final = {}
        if new_ids is not None:
            final['ids.json'] = len(json.load(open(win['ids_path'], encoding='utf-8')))
        if new_emb is not None:
            import numpy as np
            final['embeddings.npy'] = int(np.load(emb_path, mmap_mode='r').shape[0])
        if desc_row_count is not None:
            n = 0
            with open(win['desc_path'], encoding='utf-8') as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(r, dict) and 'id' in r:
                        n += 1
            final['descriptions.jsonl'] = n
        if len(set(final.values())) > 1:
            _restore_backups(backups)
            raise LockstepError(
                f"post-write check found ids/embeddings/descriptions out of lockstep "
                f"({final}) after the swap. Every backup has been restored.")

        report.append(f"windows: removed {len(hit)} window(s) from {win['wdb_path']} "
                      f"(backup: {backups[win['wdb_path']]}, pre-swap copy "
                      f"{win['wdb_path']}.bak-swap-{tag})")
        if new_desc_lines is not None:
            report.append(f"windows: dropped {n_desc_dropped} row(s) from {win['desc_path']} "
                          f"(backup: {backups[win['desc_path']]})")
        if new_ids is not None:
            report.append(f"windows: dropped {len(orig_ids) - len(new_ids)} id(s) from "
                          f"{win['ids_path']} (backup: {backups[win['ids_path']]})")
        if new_emb is not None:
            report.append(f"windows: dropped {len(orig_ids) - len(new_ids)} row(s) from "
                          f"{emb_path} (backup: {backups[emb_path]})")
    else:
        report.append('windows: nothing to do')

    report.append('')
    report.append('STILL NEEDED (whole-language/whole-corpus, not done by this script):')
    report.append(f"  venv/bin/python scripts/batch_lemma_cache.py {plan['lang']} --force")
    report.append(f"  venv/bin/python scripts/corpus/rebuild_bigrams.py {plan['lang']}")
    if win.get('present') and win['window_ids']:
        report.append('  scripts/corpus/build_window_names.py, then swap in as window_names.db')
        report.append('  systemd-run --user --scope -p MemoryMax=10G venv/bin/python3 scripts/build_connections_map.py')
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('lang')
    ap.add_argument('work', help='filename without .tess, e.g. khayyam.diwan')
    ap.add_argument('--refs', help='comma-separated ref labels to drop')
    ap.add_argument('--ref-range', help='two ref labels (first:last), everything between '
                                        'them in FILE ORDER is dropped, both ends included')
    ap.add_argument('--root', default='.')
    add_apply_argument(ap)
    a = ap.parse_args()

    filename = a.work if a.work.endswith('.tess') else a.work + '.tess'
    refs = {r.strip() for r in (a.refs or '').split(',') if r.strip()}
    if a.ref_range:
        start, end = (p.strip() for p in a.ref_range.split(':', 1))
        tess_lines = read_tess_lines(_tess_path(a.root, a.lang, filename))
        order = [ref for ref, _ in tess_lines]
        if start not in order or end not in order:
            sys.exit(f'--ref-range endpoint not found in {filename}: {start!r} or {end!r}')
        i0, i1 = order.index(start), order.index(end)
        if i0 > i1:
            i0, i1 = i1, i0
        refs |= set(order[i0:i1 + 1])
    if not refs:
        sys.exit('nothing to drop: pass --refs and/or --ref-range')

    try:
        plan = plan_drop(a.lang, filename, refs, root=a.root)
    except ValueError as e:
        sys.exit(str(e))
    print(format_plan(plan))
    if not a.apply:
        print('\n(dry run; pass --apply to write)')
        return
    print()
    try:
        for line in apply_drop(plan):
            print(line)
    except LockstepError as e:
        sys.exit(f'REFUSED: {e}')


if __name__ == '__main__':
    main()
