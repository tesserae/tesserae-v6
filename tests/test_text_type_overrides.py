"""Texts whose type the content rule gets wrong are fixed by an override."""

from backend.utils import detect_text_type

DIOGENIANUS = 'diogenianus_of_heraclea.paroemiae.tess'


def test_diogenianus_proverb_collection_is_prose_not_verse(tmp_path):
    # One short proverb per line: the median line length alone reads as verse.
    p = tmp_path / DIOGENIANUS
    p.write_text(''.join(f'<d. {i}>\tἈγαθὸν ἡ πενία\n' for i in range(1, 30)), encoding='utf-8')
    assert detect_text_type(DIOGENIANUS, filepath=str(p), language='grc') == 'prose'
    assert detect_text_type(DIOGENIANUS) == 'prose'
    # Without the override the same file is typed by its content, as poetry.
    other = tmp_path / 'zzunlisted.proverbs.tess'
    other.write_text(p.read_text(encoding='utf-8'), encoding='utf-8')
    assert detect_text_type(other.name, filepath=str(other), language='grc') == 'poetry'
