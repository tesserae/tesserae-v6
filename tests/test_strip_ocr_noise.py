"""Tests for scripts/translations/strip_ocr_noise.py, on invented rows only."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'translations'))
import strip_ocr_noise as M  # noqa: E402

FIX = os.path.join(HERE, 'fixtures', 'ocr_noise')
TESS = os.path.join(FIX, 'texts')

VOCAB = set((
    'the old man walked slowly to market and bought some bread for children '
    'he said nothing at all today then left room note reads line ends here '
    'with a full stop theois fakeplay'
).split()) - {'theois'}
VOCAB |= {'and', 'then', 'he', 'and'}


def _data():
    with open(os.path.join(FIX, 'translations', 'grc__fakeplay.dummy.json')) as f:
        return json.load(f)


def test_run_header_quotation_name_and_indexes():
    data = _data()
    new, res = M.process(data, VOCAB, TESS, 'fixture')
    u = new['units']
    assert len(u) == len(data['units'])
    assert new['ref_to_unit'] == data['ref_to_unit']
    assert u[0] == data['units'][0]                       # clean unit untouched
    assert 'dwvi' not in u[1] and 'Kak@s' not in u[1]     # the 20-token run goes
    assert '143' not in u[1] and 'FAKEPLAY' not in u[1]   # the running header goes
    assert u[1].startswith('He said nothing at all today.')
    assert u[1].endswith('And then he left the room.')
    assert 'kata tois theois ap' in u[2]                  # the short quotation stays
    assert u[2] == data['units'][2]
    assert u[3].count('Dercylus') == 8                    # the name in the references stays
    assert res['runs'] == 1 and res['headers'] == 1
    assert not res['guard_failed']


def test_short_run_is_kept():
    cl = M.Cleaner(VOCAB)
    toks = 'the old man qq zx wv kj hm bread'.split()
    assert cl.runs(toks) == []
    toks = ('the old man ' + ' '.join(['qq', 'zx', 'wv', 'kj', 'hm', 'tr', 'bx', 'cz', 'dy']) + ' bread').split()
    assert cl.runs(toks) == [(3, 12)]


def test_empty_unit_keeps_its_index():
    data = {'tess_work': 'grc/fakeplay.dummy', 'language': 'grc',
            'units': ['the old man', 'qq zx wv kj hm tr bx cz dy fq', 'the room'],
            'ref_to_unit': {'a': 0, 'b': 1, 'c': 2}}
    new, res = M.process(data, VOCAB, TESS, 'x')
    assert new['units'] == ['the old man', '', 'the room']
    assert res['emptied_units'] == 1
    assert new['ref_to_unit'] == data['ref_to_unit']


def test_guard_fires_on_crafted_case():
    # One content word in every window of eight: the runs are removed, and
    # with them every content word of the file.
    unit = ' '.join((['bread'] + ['qq', 'zx', 'wv', 'kj', 'hm', 'tr', 'bx']) * 5)
    data = {'tess_work': 'grc/fakeplay.dummy', 'language': 'grc',
            'units': [unit], 'ref_to_unit': {'a': 0}}
    new, res = M.process(data, VOCAB, TESS, 'x')
    assert res['strong_drop'] > M.GUARD_DROP
    assert res['guard_failed']


def test_main_writes_clean_file_and_refuses_guarded(tmp_path):
    src = tmp_path / 'src'
    src.mkdir()
    out = tmp_path / 'out'
    good = _data()
    (src / 'grc__fakeplay.dummy.json').write_text(json.dumps(good))
    bad = dict(good, tess_work='grc/fakeplay.bad')
    bad['units'] = [' '.join((['bread'] + ['qq', 'zx', 'wv', 'kj', 'hm', 'tr', 'bx']) * 5)]
    bad['ref_to_unit'] = {'a': 0}
    (src / 'grc__fakeplay.bad.json').write_text(json.dumps(bad))
    # Enough clean files for the vocabulary: three copies of plain English.
    for i in range(3):
        (src / ('en__c%d.json' % i)).write_text(json.dumps(
            {'units': ['the old man walked slowly to the market and bought bread for the children']}))
    rc = M.main(['--src', str(src), '--out', str(out), '--report', str(tmp_path / 'report.md'),
                 '--files', 'grc__fakeplay.dummy.json', 'grc__fakeplay.bad.json',
                 '--tess', TESS])
    assert rc == 0
    assert (out / 'grc__fakeplay.dummy.json').exists()
    assert not (out / 'grc__fakeplay.bad.json').exists()
    assert 'REFUSED' in (tmp_path / 'report.md').read_text()
    assert (tmp_path / 'samples.md').exists()


def test_vocab_rules(tmp_path):
    for i in range(3):
        (tmp_path / ('c%d.json' % i)).write_text(json.dumps({'units': ['Bread, and wine. don\'t']}))
    (tmp_path / 'c3.json').write_text(json.dumps({'units': ['rareword']}))
    vocab, st = M.build_vocab(str(tmp_path), [])
    assert 'bread' in vocab and 'dont' in vocab and 'rareword' not in vocab
