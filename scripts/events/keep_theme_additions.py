"""Keep only the hand-read Theme Search additions from a store written by add_theme_passages.py --apply.

A sample of 40 additions across all events (2026-10-21) read 17 right, 7 partly right and 11 wrong:
obscure events collect passages that share a name (Phintias under Issus) or tell a neighboring story.
So the additions are installed only for events read by hand, listed in a keep file:

    KEEP Q31900 Q131969 ...          events whose additions are kept
    DROP Q179670 arr. an. 3.22.2     one addition read as wrong (event id, then ref_start)

Every other row with found_by FOUND_BY that the starting store does not already hold is removed.

    python scripts/events/keep_theme_additions.py START_STORE APPLIED_STORE KEEP_FILE OUTPUT
"""
import shutil
import sqlite3
import sys

FOUND_BY = 'theme search 2026-10-21'


def read_keep(path):
    keep, drop = set(), set()
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if line.startswith('KEEP '):
            keep |= set(line.split()[1:])
        elif line.startswith('DROP '):
            _, eid, ref = line.split(' ', 2)
            drop.add((eid, ref))
    return keep, drop


def main(start, applied, keep_file, out):
    keep, drop = read_keep(keep_file)
    shutil.copyfile(applied, out)
    s = sqlite3.connect(f'file:{start}?mode=ro', uri=True)
    before = {r for r in s.execute('select event_id, work, ref_start from passages where found_by = ?', (FOUND_BY,))}
    db = sqlite3.connect(out)
    rows = db.execute('select rowid, event_id, work, ref_start from passages where found_by = ?', (FOUND_BY,)).fetchall()
    gone = [(rowid,) for rowid, eid, work, ref in rows
            if (eid, work, ref) not in before and (eid not in keep or (eid, ref) in drop)]
    missing = drop - {(eid, ref) for _r, eid, _w, ref in rows}
    if missing:
        sys.exit(f'REFUSING: {len(missing)} DROP lines match no row, first {sorted(missing)[:3]}')
    db.executemany('delete from passages where rowid = ?', gone)
    db.commit()
    kept = db.execute('select count(*) from passages where found_by = ?', (FOUND_BY,)).fetchone()[0]
    print({'theme_rows_written': len(rows), 'removed': len(gone), 'kept': kept, 'kept_before': len(before),
           'integrity': db.execute('pragma integrity_check').fetchone()[0]})
    db.close()


if __name__ == '__main__':
    main(*sys.argv[1:5])
