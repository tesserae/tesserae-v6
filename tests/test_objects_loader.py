"""The Objects fetch filters and database builder (scripts/objects/) on a fixture
of six objects, two per museum, and inline records for the drop rules."""
import json
import os
import sqlite3
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, 'tests', 'fixtures', 'objects')
SCRIPTS = os.path.join(ROOT, 'scripts', 'objects')
sys.path.insert(0, SCRIPTS)
import build_objects_db as B  # noqa: E402
import fetch_objects as F  # noqa: E402
import embed_object_descriptions as E  # noqa: E402


def build(tmp_path, **folders):
    out = str(tmp_path / 'objects.sqlite')
    cmd = [sys.executable, '-I', os.path.join(SCRIPTS, 'build_objects_db.py'), '--out', out]
    for k, v in folders.items():
        cmd += [f'--{k}', v]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


@pytest.fixture(scope='module')
def db(tmp_path_factory):
    return build(tmp_path_factory.mktemp('objects'), cleveland=f'{FIX}/cleveland', chicago=f'{FIX}/chicago',
                 smithsonian=f'{FIX}/smithsonian')


def test_rows_columns_and_counts(db):
    c = sqlite3.connect(db)
    assert c.execute('SELECT COUNT(*) FROM objects').fetchone()[0] == 6
    assert dict(c.execute('SELECT museum, COUNT(*) FROM objects GROUP BY 1')) == \
        {'cleveland': 2, 'chicago': 2, 'smithsonian': 2}
    cols = {r[1] for r in c.execute('PRAGMA table_info(objects)')}
    for need in ('id', 'museum', 'title', 'object_type', 'culture', 'date_text', 'date_start', 'date_end',
                 'material', 'place_text', 'description', 'short_text', 'inscription_text', 'image_url',
                 'object_url', 'licence', 'credit', 'search_text'):
        assert need in cols
    rep = json.load(open(os.path.join(os.path.dirname(db), 'objects_build_report.json')))
    assert rep['cleveland'] == {'fetched': 2, 'kept': 2, 'dropped': 0, 'dropped_because': {},
                                'median_description_chars': rep['cleveland']['median_description_chars']}


def test_cleveland_row(db):
    r = sqlite3.connect(db).execute(
        "SELECT museum, date_start, date_end, culture, material, inscription_text, image_url, object_url, "
        "licence, credit, search_text FROM objects WHERE id = 'cma:1966.114'").fetchone()
    assert r[0] == 'cleveland' and (r[1], r[2]) == (-500, -490) and r[3] == 'Greek, Attic' and r[4] == 'ceramic'
    assert 'Graffito' in r[5] and r[6].endswith('1966.114_web.jpg') and r[7] == 'https://clevelandart.org/art/1966.114'
    assert r[8] == 'CC0' and 'Leonard C. Hanna Jr. Fund' in r[9]
    assert r[10] == r[10].lower() and 'ζωιλος' in r[10]


def test_chicago_row_strips_markup_and_gates_the_image(db):
    c = sqlite3.connect(db)
    d, img, lic = c.execute("SELECT description, image_url, licence FROM objects WHERE id = 'aic:1900.001'").fetchone()
    assert '<p>' not in d and d.startswith('The towering form')
    assert img.startswith('https://www.artic.edu/iiif/2/c93a1d18') and 'CC BY 4.0' in lic
    assert c.execute("SELECT image_url FROM objects WHERE id = 'aic:1900.002'").fetchone()[0] is None  # not public domain
    assert c.execute("SELECT object_url FROM objects WHERE id = 'aic:1900.002'").fetchone()[0] == 'https://www.artic.edu/artworks/22222'


def test_smithsonian_row_drops_citation_notes_and_reads_dates(db):
    c = sqlite3.connect(db)
    d, s, e, img, credit = c.execute("SELECT description, date_start, date_end, image_url, credit FROM objects "
                                     "WHERE id = 'si:A391051-0'").fetchone()
    assert 'Described in' not in d and 'Record Last Modified' not in d and 'BLACK FIGURE LEKYTHOS' in d
    assert (s, e) == (-500, -401) and img.startswith('https://ids.si.edu/') and 'Anthropology' in credit
    assert c.execute("SELECT image_url FROM objects WHERE id = 'si:A101982A-0'").fetchone()[0] is None


def test_fts_strips_diacritics(db):
    c = sqlite3.connect(db)
    assert c.execute("SELECT COUNT(*) FROM objects_fts WHERE objects_fts MATCH 'lekythos'").fetchone()[0] == 2


def test_drop_rules():
    short = {'accession_number': 'x', 'share_license_status': 'CC0', 'type': 'Sculpture', 'description': 'Too short.'}
    row, _ = B.cleveland_row(short)
    assert B.text_length(row) < B.MIN_TEXT
    assert B.cleveland_row({**short, 'type': 'Coins'})[0] is None
    assert B.cleveland_row({**short, 'share_license_status': 'Copyright'})[0] is None
    assert B.chicago_row({'id': 1, '_in_scope': False})[0] is None
    assert B.smithsonian_row({'content': {'freetext': {'notes': [
        {'label': 'Notes', 'content': 'This description is copied from another institution database page.'}]}}})[0] is None


def test_si_dates():
    assert B.si_dates('c.500-480 BC') == (-500, -480)
    assert B.si_dates('ca. 475-410 B.C.') == (-475, -410)
    assert B.si_dates('the 5th century B.C.') == (-500, -401)
    assert B.si_dates('2nd century A.D.') == (101, 200)
    assert B.si_dates('no date') == (None, None)


def test_chicago_scope_rule():
    base = {'department_title': 'Arts of Greece, Rome, and Byzantium', 'artwork_type_title': 'Vessel',
            'place_of_origin': 'Apulia', 'date_start': -350}
    assert F.chicago_wanted(base)
    assert not F.chicago_wanted({**base, 'artwork_type_title': 'Coin'})
    assert not F.chicago_wanted({**base, 'date_display': 'Byzantine, 6th century'})
    assert not F.chicago_wanted({**base, 'date_start': 1250})
    assert not F.chicago_wanted({**base, 'place_of_origin': 'Iran'})
    assert not F.chicago_wanted({**base, 'department_title': 'Prints and Drawings'})


def test_smithsonian_scope_rule():
    def rec(title, culture, place):
        return {'title': title, 'content': {'freetext': {'culture': [{'content': culture}], 'place': [{'content': place}]},
                                            'indexedStructured': {}}}
    assert F.si_wanted(rec('Lamp', 'Roman', 'Italy'))
    assert F.si_wanted(rec('Lekythos', 'Greek, Attic', 'Greece'))
    assert not F.si_wanted(rec('Bead', 'Egyptians', 'Egypt'))
    assert not F.si_wanted(rec('Glass', 'Islamic', 'Syria'))
    assert not F.si_wanted(rec('Ball', 'Taino', 'Puerto Rico'))


def test_embed_text_and_grouping(db, tmp_path):
    assert E.text_for('A Vase.', 'Shows a banquet.') == 'A Vase. Shows a banquet.'
    rows = E.collect(db)
    assert len(rows) == 6 and all(len(r['types']) == 1 for r in rows)
