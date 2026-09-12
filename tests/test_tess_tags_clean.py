"""Every .tess line tag is well formed: no double space, no doubled period.

Fifty-four files carried tags like "<sal.  Cat..58.15>" until 2026-09-12
(repaired by scripts/corpus/repair_ref_tags.py). A new text with such tags
would leak the raw form into the index, the passage index, the translations
and the connector, so the corpus is linted here."""
import glob
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_no_malformed_tags():
    bad = []
    for path in glob.glob(os.path.join(ROOT, 'texts', '*', '*.tess')):
        with open(path, encoding='utf-8', errors='replace') as fh:
            for line in fh:
                if line.startswith('<'):
                    e = line.find('>')
                    tag = line[1:e] if e > 0 else ''
                    if '  ' in tag or '..' in tag:
                        bad.append((os.path.relpath(path, ROOT), tag))
                        break
    assert not bad, f'{len(bad)} files with malformed tags, e.g. {bad[:3]}'
