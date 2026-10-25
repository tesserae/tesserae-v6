#!/usr/bin/env python3
"""Lay the Van Hook file of align_isocrates_vanhook.py over the installed Norlin file of
isocrates.speeches (Part G, 2026-10-25), keeping every installed unit.

The installed file's one source has no `license` field (it has `pd_reason`), so a copy of it is made
here with the file-level license copied into the source, and merge_translation_files.py then writes
the merged file with `unit_sources` (0 = Norlin, 1 = Van Hook) and two sources, each with its own license.

    merge_isocrates_norlin_vanhook.py INSTALLED_FILE VANHOOK_FILE OUT_FILE
"""
import json
import os
import subprocess
import sys
import tempfile

installed, vanhook, out = sys.argv[1:4]
d = json.load(open(installed))
for s in d['sources']:
    s.setdefault('license', d['license'])
with tempfile.TemporaryDirectory() as tmp:
    prim = os.path.join(tmp, 'primary.json')
    json.dump(d, open(prim, 'w'), ensure_ascii=False)
    subprocess.run([sys.executable, '-I', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'merge_translation_files.py'),
                    prim, vanhook, out], check=True)
m = json.load(open(out))
assert len(m['unit_sources']) == len(m['units']) and set(m['unit_sources']) <= {0, 1}
assert all('license' in s for s in m['sources'])
print('sources:', [(s['translator'], s['year'], s['license'][:60]) for s in m['sources']])
print('units from Norlin', m['unit_sources'].count(0), 'from Van Hook', m['unit_sources'].count(1))
