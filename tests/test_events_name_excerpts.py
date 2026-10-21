"""Each name found in an event passage is shown in an excerpt of the line that holds it.

2026-10-21, the Battle of Actium: the card listed Agrippa as found in Suetonius but showed
only the first 150 characters of the window, cut inside a word.
"""
import os
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'events'))

from backend.blueprints import events as E  # noqa: E402
import check_participant_names as C  # noqa: E402

LINES = [
    {'ref': 'suet. vit. aug. 17.2', 'text': 'remisit tamen hosti iudicato necessitudines amicosque omnes atque '
                                          'inter alios C. Sosium et T. Domitium tunc adhuc consules.'},
    {'ref': 'suet. vit. aug. 19.2', 'text': 'Audasius atque Epicadus Iuliam filiam et Agrippam nepotem ex insulis rapere.'},
]
NAMES = ['Gaius Sosius [participant] = Sosium', 'Marcus Vipsanius Agrippa [participant] = Agrippam']


def test_every_name_gets_an_excerpt_from_its_own_line_in_text_order():
    ex = E.name_excerpts('w', 'a', 'b', NAMES, lines=LINES)
    assert [e['ref'] for e in ex] == ['suet. vit. aug. 17.2', 'suet. vit. aug. 19.2']
    assert ex[0]['names'] == ['Gaius Sosius'] and 'Sosium' in ex[0]['text']
    assert ex[1]['names'] == ['Marcus Vipsanius Agrippa'] and 'Agrippam nepotem' in ex[1]['text']


def test_an_excerpt_is_cut_at_word_boundaries_and_marked():
    text = ' '.join(['verbum%d' % i for i in range(60)])
    i = text.index('verbum30')
    out = E._excerpt(text, i, i + len('verbum30'), width=40)
    assert out.startswith('… ') and out.endswith(' …')
    inner = out[2:-2]
    assert inner.split()[0].startswith('verbum') and inner.split()[-1].startswith('verbum')
    assert all(w in text.split() for w in inner.split())


def test_greek_with_separate_accent_marks_is_matched():
    nfd = unicodedata.normalize('NFD', 'ἀναπαυομένων δ᾽ αὐτῶν ὁ Γύλιππος καὶ οἱ Συρακόσιοι')
    ex = E.name_excerpts('w', 'a', 'b', ['Gylippus [participant] = Γύλιππος'],
                         lines=[{'ref': 'thuc. 7.79.4', 'text': nfd}])
    assert ex and ex[0]['names'] == ['Gylippus']


def test_names_are_split_by_whether_the_text_holds_them(monkeypatch):
    monkeypatch.setattr(E, '_passage_lines', lambda *a: LINES)
    out = E._names_split('w', 'a', 'b', NAMES + ['Ilipa [place] = Ἰλίπας'], 'la')
    assert [n.split(' [')[0] for n in out['names_in_text']] == ['Gaius Sosius', 'Marcus Vipsanius Agrippa']
    assert out['names_from_description'] == ['Ilipa [place] = Ἰλίπας']


def test_without_the_text_nothing_is_said_about_where_a_name_is(monkeypatch):
    monkeypatch.setattr(E, '_passage_lines', lambda *a: [])
    out = E._names_split('w', 'a', 'b', NAMES, 'la')
    assert out['names_in_text'] is None and out['names_from_description'] == []


def test_the_corpus_file_fallback_reads_the_range(tmp_path, monkeypatch):
    d = tmp_path / 'la'
    d.mkdir()
    (d / 'velleius.hist.tess').write_text('<vell. 2.83.1> alpha\n<vell. 2.84.1> per M. Agrippam\n<vell. 2.85.1> omega\n',
                                         encoding='utf-8')
    monkeypatch.setattr(E, 'TEXTS_ROOT', str(tmp_path))
    lines = E._tess_lines('velleius.hist', 'la', 'vell. 2.84.1', 'vell. 2.85.1')
    assert [x['ref'] for x in lines] == ['vell. 2.84.1', 'vell. 2.85.1']


def test_the_checker_reads_the_answer_line():
    assert C.parse('Some thought.\nANSWER: NO - nepotem marks the grandson') == ('NO', 'nepotem marks the grandson')
    assert C.parse('ANSWER: YES') == ('YES', '')
    assert C.parse('no answer here') == (None, '')
    assert C.parse('ANSWER: maybe') == (None, '')
