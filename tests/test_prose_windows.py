"""The prose window cutter: whole sentences, about the target length, no split
inside a word, sub numbering, references kept."""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                'scripts', 'corpus'))
import prose_windows as pw  # noqa: E402

SHORT = 'Vrbem Romam a principio reges habuere. libertatem et consulatum Brutus instituit.'

MIXED = ' '.join(
    ('Gallia est omnis divisa in partes tres' + (';' if i % 3 == 0 else '.')
     + ' Quarum unam incolunt Belgae, aliam Aquitani, tertiam qui ipsorum lingua Celtae'
     + ('?' if i % 5 == 0 else '.') + f' Hi omnes lingua institutis legibus inter se differunt{i}!')
    .replace('Gallia', 'Gallia' if i % 2 else 'Galliae')
    for i in range(40))

GREEK = ' '.join(
    f'ὁ δὲ Θουκυδίδης ξυνέγραψε τὸν πόλεμον τῶν Πελοποννησίων καὶ Ἀθηναίων{i}. '
    f'Ἤρξατο εὐθὺς καθισταμένου καὶ ἐλπίσας μέγαν τε ἔσεσθαι· καὶ ἀξιολογώτατον τῶν προγεγενημένων; Οἱ δὲ ἄλλοι ἔλεγον{i}.'
    for i in range(12))


def _write(tmp_path, units):
    d = tmp_path / 'texts' / 'la'
    d.mkdir(parents=True)
    path = d / 'fixture.work.part.1.tess'
    path.write_text('\n'.join(f'<{ref}> {text}' for ref, text in units) + '\n', encoding='utf-8')
    return str(path)


def test_short_unit_is_one_window():
    assert pw.cut_unit(SHORT, 1200) == [(0, len(SHORT))]


def test_long_unit_cut_near_target_at_sentence_ends():
    cuts = pw.cut_unit(MIXED, 1200)
    assert len(cuts) >= 3
    for a, b in cuts[:-1]:
        assert 600 <= b - a <= 1800, (a, b)
        assert MIXED[b - 1] in '.;?!'
    # whole unit covered, in order, nothing lost but separating spaces
    assert cuts[0][0] == 0 and cuts[-1][1] == len(MIXED)
    for (a, b), (c, d) in zip(cuts, cuts[1:]):
        assert MIXED[b:c].strip() == ''
    assert all(MIXED[a].isupper() for a, _b in cuts)


def test_trailing_scrap_joins_previous_window():
    text = ' '.join(['Sentence number %d is a fair length for a test of cutting.' % i
                    for i in range(40)])
    cuts = pw.cut_unit(text, 500)
    assert all(b - a >= 500 / 3 for a, b in cuts)


def test_huge_single_sentence_is_cut_at_spaces_only():
    word = 'abcdefghij'
    text = 'Start ' + ' '.join([word] * 700) + '.'
    cuts = pw.cut_unit(text, 1200)
    assert len(cuts) > 1
    for a, b in cuts:
        piece = text[a:b]
        assert piece == piece.strip()
        assert all(w == word or w in ('Start', word + '.') for w in piece.split())


def test_greek_sentences_with_greek_capitals_and_question_mark():
    spans = pw.sentence_spans(GREEK[:400])
    assert len(spans) >= 2
    for a, b in spans[1:]:
        assert GREEK[a].isupper()
    cuts = pw.cut_unit(GREEK, 600)
    assert len(cuts) >= 2
    for a, b in cuts:
        assert GREEK[a:b] == GREEK[a:b].strip()


def test_windows_for_file_numbering_references_and_text(tmp_path):
    path = _write(tmp_path, [('T. 1.1', SHORT), ('T. 1.2', MIXED), ('T. 1.3', GREEK), ('T. 1.4', 'x')])
    wins, skipped = pw.windows_for_file('la', 'fixture.work.part.1', path, 1200, min_chars=40)
    assert skipped == 1
    assert [w['id'] for w in wins] == [f'fixture.work.part.1:prose:{i}' for i in range(len(wins))]
    by_ref = {}
    for w in wins:
        assert w['scale'] == 'prose'
        assert w['ref_start'] == w['ref_end']
        by_ref.setdefault(w['ref_start'], []).append(w)
    assert list(by_ref) == ['T. 1.1', 'T. 1.2', 'T. 1.3']
    for ref, ws in by_ref.items():
        assert [w['sub'] for w in ws] == list(range(1, len(ws) + 1))
    assert len(by_ref['T. 1.1']) == 1 and by_ref['T. 1.1'][0]['text'] == SHORT
    assert len(by_ref['T. 1.2']) >= 3
    unit = MIXED
    for w in by_ref['T. 1.2']:
        assert unit[w['char_start']:w['char_end']] == w['text']
    assert by_ref['T. 1.3'][0]['text'].startswith('ὁ δὲ Θουκυδίδης')


def test_work_files_prefers_parts(tmp_path):
    d = tmp_path / 'texts' / 'la'
    d.mkdir(parents=True)
    for n in ('w.tess', 'w.part.1.tess', 'w.part.2.tess', 'w.part.10.tess'):
        (d / n).write_text('<a 1> text here\n')
    got = [w for _l, w, _p in pw.work_files(str(tmp_path / 'texts'), 'w')]
    assert got == ['w.part.1', 'w.part.2', 'w.part.10']
    got = [w for _l, w, _p in pw.work_files(str(tmp_path / 'texts'), 'w.part.1')]
    assert got == ['w.part.1']


def test_upsert_window_texts(tmp_path):
    db = tmp_path / 'wt.db'
    con = sqlite3.connect(db)
    con.execute('CREATE TABLE window_texts (id TEXT PRIMARY KEY, language TEXT, work TEXT, '
                'ref_start TEXT, ref_end TEXT, text TEXT)')
    con.commit(); con.close()
    wj = tmp_path / 'w.jsonl'
    wj.write_text(json.dumps({'id': 'a:prose:0', 'language': 'la', 'work': 'a', 'ref_start': 'r',
                              'ref_end': 'r', 'text': 'hello'}) + '\n')
    assert pw.upsert_window_texts(str(db), str(wj)) == (1, 1)
    assert pw.upsert_window_texts(str(db), str(wj)) == (1, 1)
