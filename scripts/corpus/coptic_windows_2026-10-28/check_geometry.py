#!/usr/bin/env python3
"""Regenerate the windows of existing Coptic works with build_batch_windows and compare with the live store."""
import sqlite3, sys
sys.path.insert(0, '/home/ncoffee/wt-copticwin/scripts/corpus')
import build_batch_windows as BW
con = sqlite3.connect('file:/var/www/tesseraev6_flask/data/passage_index/window_texts.db?mode=ro', uri=True)
for work in sys.argv[1:]:
    new = BW.windows_for(f'/var/www/tesseraev6_flask/texts/cop/{work}.tess', 'cop', {}, {}, 0)
    old = {r[0]: r[1:] for r in con.execute('select id,ref_start,ref_end,text from window_texts where work=?', (work,))}
    ids = {w['id'] for w in new}
    same = sum(1 for w in new if w['id'] in old and old[w['id']] == (w['ref_start'], w['ref_end'], w['text']))
    print(work, 'new', len(new), 'live', len(old), 'ids equal', ids == set(old), 'rows identical', same)
