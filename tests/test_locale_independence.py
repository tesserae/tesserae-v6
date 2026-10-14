"""File operations must give the same answer under an ASCII and a UTF-8 server.

Apache starts the web process with LANG set to C, so Python's file system
encoding is ASCII and a str path holding Greek letters cannot be encoded. The
tests below run the file helpers in a subprocess forced into that state
(LC_ALL=C, PYTHONUTF8=0, locale coercion off), on a Greek-named temporary file,
so they exercise the ASCII encoding wherever the test suite itself runs.
"""
import hashlib
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GREEK = 'aristotle.περί_χρωμάτων.tess'
PROSE_LINE = ('Λόγος ἐστὶ φωνὴ σημαντικὴ κατὰ συνθήκην ἣς τῶν μερῶν τι σημαντικόν ἐστι κεχωρισμένον '
              'ὡς φάσις ἀλλ᾽ οὐχ ὡς κατάφασις ἢ ἀπόφασις καὶ ἄλλα πολλὰ τοιαῦτα λέγεται.')


def _ascii_env():
    env = dict(os.environ)
    for k in ('LANG', 'LC_ALL', 'LC_CTYPE', 'PYTHONUTF8', 'PYTHONIOENCODING'):
        env.pop(k, None)
    env.update({'LC_ALL': 'C', 'LANG': 'C', 'PYTHONUTF8': '0',
                'PYTHONCOERCECLOCALE': '0', 'PYTHONIOENCODING': 'utf-8'})
    return env


def _run_ascii(code, *args):
    out = subprocess.run([sys.executable, '-c', code, *args], cwd=ROOT, env=_ascii_env(),
                         capture_output=True, text=True, encoding='utf-8', timeout=120)
    assert out.returncode == 0, out.stderr
    return out.stdout


@pytest.fixture
def greek_corpus(tmp_path):
    lang = tmp_path / 'texts' / 'grc'
    lang.mkdir(parents=True)
    body = ''.join('<aristotle.chr 1.%d>\t%s\n' % (i, PROSE_LINE) for i in range(1, 6))
    (lang / GREEK).write_bytes(body.encode('utf-8'))
    (lang / 'plain.ascii.tess').write_bytes(b'<plain.ascii 1.1>\tarma virum\n')
    return tmp_path / 'texts'


def test_subprocess_really_is_ascii():
    out = _run_ascii('import sys; print(sys.getfilesystemencoding())')
    assert out.strip() == 'ascii'


def test_helpers_read_a_greek_name_under_ascii(greek_corpus):
    code = r'''
import json, os, sys
from backend import fspaths
d = sys.argv[1]
name = sys.argv[2]
path = os.path.join(d, name)
res = {}
res['exists'] = fspaths.exists(path)
res['isfile'] = fspaths.isfile(path)
res['size'] = fspaths.getsize(path)
res['listdir'] = sorted(fspaths.listdir_text(d))
res['scandir'] = sorted(fspaths.scandir_text(d))
res['walk'] = sorted(f for _, _, fs in fspaths.walk(d) for f in fs)
res['glob'] = sorted(os.path.basename(p) for p in fspaths.glob(os.path.join(d, 'aristotle.*.tess')))
with fspaths.open_text(path) as fh:
    res['first'] = fh.readline()[:12]
res['native_roundtrip'] = fspaths.exists(fspaths.native_path(path))
print(json.dumps(res, ensure_ascii=False))
'''
    d = str(greek_corpus / 'grc')
    res = json.loads(_run_ascii(code, d, GREEK))
    assert res['exists'] and res['isfile'] and res['native_roundtrip']
    assert res['size'] > 100
    assert res['listdir'] == sorted([GREEK, 'plain.ascii.tess'])
    assert res['walk'] == sorted([GREEK, 'plain.ascii.tess'])
    assert res['glob'] == [GREEK]
    assert res['first'].startswith('<aristotle')


def test_detect_text_type_and_resolve_under_ascii(greek_corpus):
    code = r'''
import json, os, sys
from backend.utils import detect_text_type, resolve_text_path, safe_listdir
texts, name = sys.argv[1], sys.argv[2]
d = os.path.join(texts, 'grc')
resolved = resolve_text_path(texts, 'grc', name)
res = {
  'resolved': resolved is not None,
  'type_by_path': detect_text_type(name, filepath=os.path.join(d, name), language='grc'),
  'listing': sorted(safe_listdir(d)),
}
print(json.dumps(res, ensure_ascii=False))
'''
    res = json.loads(_run_ascii(code, str(greek_corpus), GREEK))
    assert res['resolved']
    assert res['type_by_path'] == 'prose'
    assert GREEK in res['listing']


def test_same_answers_under_utf8_in_process(greek_corpus):
    from backend import fspaths
    from backend.utils import detect_text_type
    d = str(greek_corpus / 'grc')
    assert sorted(fspaths.listdir_text(d)) == sorted([GREEK, 'plain.ascii.tess'])
    assert detect_text_type(GREEK, filepath=os.path.join(d, GREEK), language='grc') == 'prose'


def _expected_checksum(directory):
    info = []
    for n in sorted(os.listdir(directory)):
        if n.endswith('.tess'):
            st = os.stat(os.path.join(directory, n))
            info.append(f'{n}:{st.st_size}:{st.st_mtime}')
    return hashlib.md5('\n'.join(info).encode('utf-8')).hexdigest()  # nosec B324


def test_corpus_checksum_unchanged_for_ascii_names(tmp_path, monkeypatch):
    from backend import frequency_cache
    lang = tmp_path / 'la'
    lang.mkdir()
    (lang / 'vergil.aeneid.tess').write_bytes(b'<a 1.1>\tarma virumque cano\n')
    (lang / 'ovid.amores.tess').write_bytes(b'<b 1.1>\tarma gravi numero\n')
    monkeypatch.setattr(frequency_cache, 'TEXTS_DIR', str(tmp_path))
    assert frequency_cache.get_corpus_checksum('la') == _expected_checksum(str(lang))


def test_corpus_checksum_same_under_ascii_and_utf8(greek_corpus):
    code = r'''
import sys
from backend import frequency_cache
frequency_cache.TEXTS_DIR = sys.argv[1]
print(frequency_cache.get_corpus_checksum('grc'))
'''
    ascii_sum = _run_ascii(code, str(greek_corpus)).strip()
    assert ascii_sum == _expected_checksum(str(greek_corpus / 'grc'))


def test_texts_zip_lists_greek_names_under_ascii(greek_corpus):
    code = r'''
import sys, zipfile, json
from backend.blueprints.downloads import create_zip_from_directory
buf = create_zip_from_directory(sys.argv[1], 'texts_grc')
print(json.dumps(sorted(zipfile.ZipFile(buf).namelist()), ensure_ascii=False))
'''
    names = json.loads(_run_ascii(code, str(greek_corpus / 'grc')))
    assert 'texts_grc/' + GREEK in names
    assert 'texts_grc/plain.ascii.tess' in names
