"""GET /text/<work>/book-for: which book file of a whole-file work holds a
line. The Reader shows works held in books one book at a time (PR #427) and
first guessed the book from the first number of the line reference; that
guess is wrong wherever the book files are not numbered by that number
(Alcuin's part 97 holds poems 97 to 101; Cicero's Verrines part 3 holds
actio 2 book 2, refs "2.2.x") and wherever the whole file and its parts tag
lines differently (Hyperides: "hyp. 1.1" against "hyp. speeches. 1.1").
The server looks the line up in the part files instead (NC, 2026-09-20)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from backend.app import app  # noqa: E402
from backend.blueprints import corpus  # noqa: E402


@pytest.fixture
def texts(tmp_path, monkeypatch):
    la = tmp_path / 'la'
    la.mkdir()
    (la / 'cicero.verrines.tess').write_text(
        '<cic. ver. 1.1.1> a\n<cic. ver. 2.1.1> b\n<cic. ver. 2.2.1> c\n', encoding='utf-8')
    (la / 'cicero.verrines.part.1.tess').write_text('<cic. ver. 1.1.1> a\n', encoding='utf-8')
    (la / 'cicero.verrines.part.2.tess').write_text('<cic. ver. 2.1.1> b\n', encoding='utf-8')
    (la / 'cicero.verrines.part.3.tess').write_text('<cic. ver. 2.2.1> c\n', encoding='utf-8')
    (la / 'hyperides.speeches.tess').write_text('<hyp. 1.1> x\n<hyp. 2.1> y\n', encoding='utf-8')
    (la / 'hyperides.speeches.part.1.tess').write_text('<hyp. speeches. 1.1> x\n', encoding='utf-8')
    (la / 'hyperides.speeches.part.2.tess').write_text('<hyp. speeches. 2.1> y\n', encoding='utf-8')
    (la / 'dion.ant.tess').write_text('<dion. ant 1.1.1> p\n<dion. ant 15.1.1> q\n', encoding='utf-8')
    (la / 'dion.ant.part.1.tess').write_text('<dion. ant 1.1.1> p\n', encoding='utf-8')
    (la / 'dion.ant.part.12.books_12-20.tess').write_text('<dion. ant 15.1.1> q\n', encoding='utf-8')
    (la / 'lone.work.tess').write_text('<lone. 1.1> z\n', encoding='utf-8')
    monkeypatch.setattr(corpus, '_texts_dir', str(tmp_path))
    monkeypatch.setattr(corpus, '_book_refs_cache', {})
    return app.test_client()


def _get(client, work, ref=None):
    q = '?language=la' + (f'&ref={ref}' if ref else '')
    r = client.get(f'/api/text/{work}/book-for{q}')
    assert r.status_code == 200
    return r.get_json()


def test_book_is_found_by_the_line_not_by_its_first_number(texts):
    assert _get(texts, 'cicero.verrines.tess', 'cic. ver. 2.2.1') == {
        'file': 'cicero.verrines.part.3.tess', 'found': True}
    assert _get(texts, 'cicero.verrines.tess', 'cic. ver. 2.1.1')['file'] == 'cicero.verrines.part.2.tess'


def test_whole_file_and_parts_may_tag_lines_differently(texts):
    out = _get(texts, 'hyperides.speeches.tess', 'hyp. 2.1')
    assert out == {'file': 'hyperides.speeches.part.2.tess', 'found': True}


def test_a_part_file_with_a_suffix_after_its_number_counts(texts):
    out = _get(texts, 'dion.ant.tess', 'dion. ant 15.1.1')
    assert out == {'file': 'dion.ant.part.12.books_12-20.tess', 'found': True}


def test_no_ref_or_unknown_ref_opens_the_first_book(texts):
    assert _get(texts, 'cicero.verrines.tess') == {'file': 'cicero.verrines.part.1.tess', 'found': False}
    assert _get(texts, 'cicero.verrines.tess', 'cic. ver. 9.9.9')['file'] == 'cicero.verrines.part.1.tess'


def test_a_work_without_books_and_a_part_file_answer_null(texts):
    assert _get(texts, 'lone.work.tess', 'lone. 1.1') == {'file': None, 'found': False}
    assert _get(texts, 'cicero.verrines.part.2.tess', 'cic. ver. 2.1.1') == {'file': None, 'found': False}
