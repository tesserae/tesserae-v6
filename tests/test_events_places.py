"""The ancient name of an event's place and the approximate-location flag: the route (backend/blueprints/events.py)
and the scripts that make them (scripts/events/add_place_ancient.py, classify_event_points.py). Fixtures only."""
import json
import os
import sqlite3
import subprocess
import sys

import pytest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, 'tests', 'fixtures', 'events')
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'events'))

import add_place_ancient as A  # noqa: E402
import classify_event_points as C  # noqa: E402
import fetch_pleiades_names as FP  # noqa: E402


@pytest.fixture
def db(tmp_path):
    out = str(tmp_path / 'dossiers.sqlite')
    subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'events', 'load_dossiers_sqlite.py'),
                    '--dossiers', FIX, '--out', out], check=True)
    return out


@pytest.fixture
def client_for(monkeypatch):
    def make(path):
        monkeypatch.setenv('TESSERAE_EVENTS_DB', path)
        from backend.app import app
        app.config['TESTING'] = True
        return app.test_client()
    return make


def first_event(path):
    return sqlite3.connect(path).execute('SELECT id FROM events ORDER BY id LIMIT 1').fetchone()[0]


# ---- the route -------------------------------------------------------------

def test_a_store_before_the_columns_answers_with_no_ancient_name_and_an_exact_point(db, client_for):
    cl = client_for(db)
    ev = cl.get('/api/events/' + first_event(db)).get_json()['event']
    assert ev['place_ancient'] is None and ev['location_approximate'] is False
    row = cl.get('/api/events?sort=date&show=all').get_json()['events'][0]
    assert row['place_ancient'] is None


def test_the_ancient_name_and_the_approximate_flag_are_returned(db, client_for):
    c = sqlite3.connect(db)
    c.execute('ALTER TABLE events ADD COLUMN place_ancient TEXT')
    c.execute('ALTER TABLE events ADD COLUMN location_approximate INTEGER')
    eid = first_event(db)
    c.execute("UPDATE events SET place_ancient = 'Perusia', place = 'Perugia', lat = 43.1, lon = 12.4, "
              "location_approximate = 1 WHERE id = ?", (eid,))
    c.commit()
    c.close()
    body = client_for(db).get('/api/events/' + eid).get_json()
    assert body['event']['place_ancient'] == 'Perusia' and body['event']['place'] == 'Perugia'
    assert body['event']['location_approximate'] is True
    assert [p for p in body['map'] if p['kind'] == 'event'][0]['approximate'] is True


def test_an_empty_ancient_name_is_returned_as_none(db, client_for):
    c = sqlite3.connect(db)
    c.execute('ALTER TABLE events ADD COLUMN place_ancient TEXT')
    eid = first_event(db)
    c.execute("UPDATE events SET place_ancient = '' WHERE id = ?", (eid,))
    c.commit()
    c.close()
    assert client_for(db).get('/api/events/' + eid).get_json()['event']['place_ancient'] is None


def test_the_name_search_finds_an_event_by_the_ancient_name_of_its_place(db, client_for):
    """Tessa's lookup: "Perusia" finds the Battle of Perugia (2026-10-21). A store with no such column still searches."""
    eid = first_event(db)
    assert client_for(db).get('/api/events?show=all&q=Perusia').get_json()['events'] == []
    c = sqlite3.connect(db)
    c.execute('ALTER TABLE events ADD COLUMN place_ancient TEXT')
    c.execute("UPDATE events SET place_ancient = 'Perusia' WHERE id = ?", (eid,))
    c.commit()
    c.close()
    rows = client_for(db).get('/api/events?show=all&q=Perusia').get_json()['events']
    assert [r['id'] for r in rows] == [eid]


# ---- choosing the name -----------------------------------------------------

PERIODS = {'classical': [-550, -330], 'hellenistic-republican': [-330, -30], 'roman': [-30, 300],
           'late-antique': [300, 640], 'modern': [1700, 2100], 'archaic': [-750, -550], 'long': [-1000, 1000]}


def name(romanized, periods, lang='la', typ='geographic', acc='accurate'):
    return {'romanized': romanized, 'language': lang, 'nameType': typ, 'transcriptionAccuracy': acc,
            'attestations': [{'timePeriod': p} for p in periods]}


def test_the_name_attested_in_the_events_period_is_chosen_and_diacritics_dropped():
    place = {'title': 'Perusia', 'names': [name('Perugia', ['modern'], 'it'),
                                           name('Perusia, Perusium', ['hellenistic-republican', 'roman']),
                                           name('Peroúsia', ['classical'], 'grc')]}
    assert A.choose(place, PERIODS, -41, -40)[0] == 'Perusia'
    assert A.choose(place, PERIODS, -500, -500)[0] == 'Perousia'
    place['names'][1]['romanized'] = 'Perūsia'
    assert A.choose(place, PERIODS, -41, -41)[0] == 'Perusia'


def test_no_name_qualifies_when_nothing_is_attested_in_the_period_or_names_are_undated():
    place = {'title': 'X', 'names': [name('Ixion', []), name('Modernia', ['modern'], 'en'),
                                     name('Wrong', ['roman'], acc='inaccurate'), name('Tribe', ['roman'], typ='ethnic')]}
    assert A.choose(place, PERIODS, -41, -41) is None
    assert A.choose(place, PERIODS, 100, 100) is None


def test_the_narrowest_period_then_the_pleiades_title_decide():
    place = {'title': 'Roma/Rome', 'names': [name('Urbs', ['archaic', 'classical', 'hellenistic-republican', 'roman']),
                                             name('Valentia', ['roman']), name('Roma', ['roman'])]}
    # Valentia and Roma tie on period, and Roma matches the title
    assert A.choose(place, PERIODS, 50, 50)[0] == 'Rome'
    assert A.choose(place, PERIODS, -400, -400)[0] == 'Urbs'


def test_latin_then_english_then_untagged_then_greek_whatever_the_period_and_other_languages_never_qualify():
    greek_narrow = name('Taras', ['hellenistic-republican'], 'grc')
    latin_wide = name('Tarentum', ['archaic', 'classical', 'hellenistic-republican', 'roman'], 'la')
    english = name('Tarantum', ['hellenistic-republican'], 'en')
    place = {'title': 'Tarentum/Taras', 'names': [greek_narrow, latin_wide]}
    assert A.choose(place, PERIODS, -212, -212)[0] == 'Tarentum'
    place = {'title': 'T', 'names': [greek_narrow, english]}
    assert A.choose(place, PERIODS, -212, -212)[0] == 'Tarantum'
    place = {'title': 'T', 'names': [greek_narrow]}
    assert A.choose(place, PERIODS, -212, -212)[0] == 'Taras'
    # Latin out of period falls back to the Greek name attested in it
    place = {'title': 'T', 'names': [name('Tarentum', ['roman']), greek_narrow]}
    assert A.choose(place, PERIODS, -212, -212)[0] == 'Taras'
    # other languages and scripts are never used
    place = {'title': 'H', 'names': [name('hmt', ['classical'], 'egy'), name('Arahtu', ['classical'], 'akk'),
                                     name('Ἀραδος', ['classical'], 'grc'), name('Hama', ['classical'], 'arb')]}
    assert A.choose(place, PERIODS, -500, -500) is None
    # a name with no language given ranks after Latin and English and before Greek
    place = {'title': 'D', 'names': [name('Putho', ['classical'], 'grc'), name('Delphi', ['classical'], ''),
                                     name('Pytho', ['classical'], None)]}
    assert A.choose(place, PERIODS, -500, -500)[0] == 'Delphi'
    place['names'].append(name('Delphoe', ['classical'], 'la'))
    assert A.choose(place, PERIODS, -500, -500)[0] == 'Delphoe'
    # within one language the narrowest period decides
    place = {'title': 'X', 'names': [name('Wide', ['long']), name('Narrow', ['classical'])]}
    assert A.choose(place, PERIODS, -500, -500)[0] == 'Narrow'


def test_standard_english_forms_replace_latin_and_greek_ones_only_where_listed():
    place = {'title': 'Syracusae', 'names': [name('Syracusae', ['hellenistic-republican'])]}
    assert A.choose(place, PERIODS, -212, -212)[0] == 'Syracuse'
    place = {'title': 'Actium', 'names': [name('Actium', ['hellenistic-republican'])]}
    assert A.choose(place, PERIODS, -31, -31)[0] == 'Actium'
    place = {'title': 'Brundisium', 'names': [name('Brundisium', ['roman'])]}
    assert A.choose(place, PERIODS, 100, 100)[0] == 'Brundisium'


def test_the_period_vocabulary_is_read_from_the_page():
    html = ('<a href="time-periods/roman">Roman (30 BC-AD 300)\n (30 BC - AD 300)</a><br/>'
            '<span>The Roman period. [[-30, 300]]</span></p>'
            '<a href="time-periods/archaic">Archaic</a><br/><span>x [[-750,-550]]</span></p>')
    assert FP.parse_periods(html) == {'roman': [-30, 300], 'archaic': [-750, -550]}


def test_the_script_writes_a_copy_with_the_column_and_leaves_the_input_alone(tmp_path):
    src = str(tmp_path / 'in.sqlite')
    c = sqlite3.connect(src)
    c.execute('CREATE TABLE events (id TEXT, label TEXT, date_start INTEGER, date_end INTEGER, place TEXT, pleiades_id TEXT)')
    c.execute("INSERT INTO events VALUES ('E1', 'Siege of Perusia', -41, -40, 'Perugia', '11')")
    c.execute("INSERT INTO events VALUES ('E2', 'Nowhere', 1000, 1000, 'Somewhere', '12')")
    c.execute("INSERT INTO events VALUES ('E3', 'No id', -41, -40, 'Elsewhere', NULL)")
    c.commit()
    c.close()
    raw = tmp_path / 'raw'
    (raw / 'places').mkdir(parents=True)
    (raw / 'periods.json').write_text(json.dumps(PERIODS))
    (raw / 'places' / '11.json').write_text(json.dumps({'title': 'Perusia', 'names': [name('Perusia', ['hellenistic-republican'])]}))
    (raw / 'places' / '12.json').write_text(json.dumps({'title': 'Z', 'names': [name('Zed', ['classical'])]}))
    out = str(tmp_path / 'out.sqlite')
    assert A.main([src, out, str(raw), '--apply']) == 0
    got = dict(sqlite3.connect(out).execute('SELECT id, place_ancient FROM events'))
    assert got == {'E1': 'Perusia', 'E2': None, 'E3': None}
    assert 'place_ancient' not in [r[1] for r in sqlite3.connect(src).execute('PRAGMA table_info(events)')]


# ---- classifying the stored point --------------------------------------------

def test_class_labels_read_as_site_or_region():
    assert C.kind_of_classes(['city', 'port']) == 'site'
    assert C.kind_of_classes(['Roman province']) == 'region'
    assert C.kind_of_classes(['river']) == 'region'
    assert C.kind_of_classes(['mountain']) == 'site'
    assert C.kind_of_classes(['ancient city', 'historical region']) == 'site'
    assert C.kind_of_classes(['mountain range']) == 'region'
    assert C.kind_of_classes(['thing']) is None


def test_pleiades_titles_mark_regions_by_the_type_in_parentheses():
    assert C.title_is_region('Lydia/Maionia (region)') and C.title_is_region('Euphrates (river)')
    assert not C.title_is_region('Perusia') and not C.title_is_region('Roman amphitheater at Cumae')


def test_a_point_at_a_region_center_is_class_b_at_a_site_class_a_and_alone_class_c():
    here = (36.0, 40.0)
    region = [('Q1', 'Mesopotamia', (36.0, 40.0), 'region')]
    site = [('Q2', 'Edessa', (36.001, 40.0), 'site')]
    assert C.classify(here, region, None, None, [])[0] == 'b'
    assert C.classify(here, site, None, None, [])[0] == 'a'
    assert C.classify(here, [('Q3', 'Far', (37.0, 41.0), 'region')], None, None, [])[0] == 'c'
    assert C.classify(here, [], ((36.0, 40.0), ['river'], None), None, [])[0] == 'b'
    assert C.classify(here, [], ((36.0, 40.0), ['settlement'], None), None, [])[0] == 'a'
    assert C.classify(here, [], None, None, [((36.0, 40.0), True, 'X (region)')])[0] == 'b'
    # region and site both within a kilometer: the region wins, the point is a center
    assert C.classify(here, region + site, None, None, [])[0] == 'b'


def test_a_wikipedia_point_must_lie_in_or_beside_the_region():
    stored = (36.0, 40.0)
    box = [38.0, 35.0, 42.0, 37.0]  # west, south, east, north
    assert C.in_or_beside((36.5, 41.0), stored, box)
    assert C.in_or_beside((37.9, 42.9), stored, box)          # one degree beside the box
    assert not C.in_or_beside((50.0, 10.0), stored, box)
    assert C.in_or_beside((37.0, 41.0), stored, None)
    assert not C.in_or_beside((50.0, 10.0), stored, None)


def test_the_wikipedia_coordinates_follow_redirects_and_normalization(tmp_path):
    p = tmp_path / 'wikipedia_1.json'
    p.write_text(json.dumps({'query': {
        'normalized': [{'from': 'battle of x', 'to': 'Battle of X'}],
        'redirects': [{'from': 'Siege of Y', 'to': 'Y campaign'}],
        'pages': [{'title': 'Battle of X', 'coordinates': [{'lat': 1.5, 'lon': 2.5, 'primary': True, 'globe': 'earth'}]},
                  {'title': 'Y campaign', 'coordinates': [{'lat': 3.0, 'lon': 4.0, 'primary': True, 'globe': 'earth'}]},
                  {'title': 'Moon', 'coordinates': [{'lat': 1.0, 'lon': 1.0, 'primary': True, 'globe': 'moon'}]},
                  {'title': 'No coordinates'}]}}))
    got = C.wikipedia_coordinates([str(p)])
    assert got['battle of x'] == (1.5, 2.5) and got['Siege of Y'] == (3.0, 4.0) and got['Battle of X'] == (1.5, 2.5)
    assert 'Moon' not in got and 'No coordinates' not in got


# ---- the gateway choice (choose_place_names.py) -------------------------------

import choose_place_names as G  # noqa: E402


def test_the_answer_is_the_candidate_on_the_last_answer_line_or_none():
    forms = {'Tarentum', 'Taras', 'Brigantinus L.'}
    assert G.clean_answer('Latin is usual.\nANSWER: Tarentum', forms) == 'Tarentum'
    assert G.clean_answer('x ANSWER: **Taras**.', forms) == 'Taras'
    assert G.clean_answer('ANSWER: Brigantinus L.', forms) == 'Brigantinus L.'
    assert G.clean_answer('ANSWER: Brigantinus L', forms) == 'Brigantinus L.'
    assert G.clean_answer('ANSWER: none', forms) == 'NONE'
    assert G.clean_answer('ANSWER: Taranto', forms) is None
    assert G.clean_answer('no answer line', forms) is None
    assert G.clean_answer('', forms) is None
    assert G.clean_answer(None, forms) is None


def test_candidates_are_filtered_by_language_and_script_but_not_by_period():
    place = {'names': [name('Tarentum', ['roman'], ''), name('Taras', ['archaic'], 'grc'), name('Taranto', ['modern'], 'it'),
                       name('Ḥmt', ['classical'], 'egy'), name('Ἀραδος', ['classical'], 'grc'), name('Undated', [], 'la'),
                       name('Tarentum', ['archaic'], 'la'), name('Tribe', ['roman'], 'la', typ='ethnic')]}
    got = G.qualifying_names(place, PERIODS)
    assert [c['form'] for c in got] == ['Tarentum', 'Taras', 'Undated']
    assert [k for k, _ in got[0]['periods']] == ['roman', 'archaic']        # the two entries for one form are merged
    assert got[2]['periods'] == []


def test_the_question_lists_each_candidate_with_its_periods():
    cands = [{'form': 'Taras', 'language': 'grc', 'periods': [('archaic', [-750, -550])]},
             {'form': 'Tarentum', 'language': '', 'periods': []}]
    q = G.question('First Battle of Tarentum', -212, -212, 'Taranto', cands)
    assert 'Year: 212 BCE' in q and 'Modern place name: Taranto' in q
    assert '- Taras [attested: archaic (750 BCE to 550 BCE)]' in q and '- Tarentum [attested: no period given]' in q


def test_abbreviated_kinds_of_place_are_written_out_and_colonial_titles_dropped():
    assert G.expand('Brigantinus L.') == 'Lacus Brigantinus' and G.expand('Vesuvius M.') == 'Mons Vesuvius'
    assert G.expand('Col. Arelate') == 'Arelate' and G.expand('Tarentum') == 'Tarentum'


def test_overrides_apply_to_their_place_and_years_only():
    assert G.override_for('541044', -191, -191)[0] == 'Pherae'
    assert G.override_for('541044', 2000, 2000) is None
    assert G.override_for('999', -191, -191) is None
    assert all(len(o) == 5 and o[4] for o in G.OVERRIDES)                    # each has a reason


def test_the_run_asks_once_keeps_answers_in_the_cache_and_applies_overrides(tmp_path, monkeypatch):
    src = str(tmp_path / 'in.sqlite')
    c = sqlite3.connect(src)
    c.execute('CREATE TABLE events (id TEXT, label TEXT, date_start INTEGER, date_end INTEGER, place TEXT, pleiades_id TEXT)')
    c.executemany('INSERT INTO events VALUES (?,?,?,?,?,?)', [
        ('E1', 'Battle of Tarentum', -212, -212, 'Taranto', '11'), ('E2', 'Capture of Pherae', -191, -191, 'Pherae', '541044'),
        ('E3', 'Nowhere', 0, 0, 'X', '13'), ('E4', 'Same', -300, -300, 'Pisa', '14'), ('E5', 'No place', -300, -300, 'Y', None)])
    c.commit()
    c.close()
    raw = tmp_path / 'raw'
    (raw / 'places').mkdir(parents=True)
    (raw / 'periods.json').write_text(json.dumps(PERIODS))
    (raw / 'places' / '11.json').write_text(json.dumps({'names': [name('Taras', ['hellenistic-republican'], 'grc'), name('Tarentum', ['roman'], '')]}))
    (raw / 'places' / '541044.json').write_text(json.dumps({'names': [name('Pherai', ['classical'], 'grc'), name('Pherae', ['roman'], 'la')]}))
    (raw / 'places' / '13.json').write_text(json.dumps({'names': [name('Hmt', ['classical'], 'egy')]}))
    (raw / 'places' / '14.json').write_text(json.dumps({'names': [name('Pisa', ['classical'], 'la')]}))
    calls = []

    def fake_ask(url, key, user, stats, lock, max_tokens=0):
        calls.append(user)
        stats['requests'] += 1
        return 'ANSWER: Pherai' if 'Pherai' in user else ('ANSWER: Tarentum' if 'Tarentum' in user else 'ANSWER: NONE')

    monkeypatch.setattr(G, 'ask', fake_ask)
    monkeypatch.setattr(G.J, '_env', lambda: ('http://x', 'k'))
    out, cache = str(tmp_path / 'out.sqlite'), str(tmp_path / 'cache.sqlite')
    args = [src, out, str(raw), '--cache', cache, '--report', str(tmp_path / 'r.json'), '--sample-out', str(tmp_path / 's' / 's.csv'), '--apply']
    assert G.main(args) == 0
    assert len(calls) == 3                                                   # E3 has no candidate, E5 no Pleiades place
    got = dict(sqlite3.connect(out).execute('SELECT id, place_ancient FROM events'))
    assert got == {'E1': 'Tarentum', 'E2': 'Pherae', 'E3': None, 'E4': None, 'E5': None}   # override beats the model, NONE is empty
    rep = json.load(open(tmp_path / 'r.json'))['summary']
    assert rep['overridden'] == 1 and rep['model_none'] == 1 and rep['answer_rate'] == 1.0
    assert sqlite3.connect(cache).execute('SELECT count(*) FROM answers').fetchone()[0] == 3
    assert G.main(args) == 0 and len(calls) == 3                             # a rerun asks nothing
    rows = open(tmp_path / 's' / 's.csv', encoding='utf-8').read().splitlines()
    assert len(rows) == 2 and rows[0].endswith('lead grade (right / wrong / better name)')   # only Tarentum changes a heading


def test_the_event_titles_latinized_spelling_replaces_a_greek_transliteration():
    assert G.title_spelling('Siege of Themiscyra', 'Themiskyra') == 'Themiscyra'
    assert G.title_spelling('Battle of Caphyae', 'Kaphyai') == 'Caphyae'
    assert G.title_spelling('Battle of Mount Haemus', 'Haimos') == 'Haemus'
    assert G.title_spelling('Battle of Phoenice', 'Phenice') == 'Phoenice'
    assert G.title_spelling('Battle of Mount Gaurus', 'Mons Gaurus') == 'Mons Gaurus'


def test_the_title_never_replaces_a_latin_name_with_a_greek_or_modern_spelling():
    assert G.title_spelling('Battle of Korkyra', 'Corcyra') == 'Corcyra'
    assert G.title_spelling('Battle of Uskana', 'Uscana') == 'Uscana'
    assert G.title_spelling('Siege of Centuripe and Galaria', 'Centuripae') == 'Centuripae'
    assert G.title_spelling('Battle of the Ebro', 'Iberus') == 'Iberus'
    assert G.title_spelling('Battle of the Strait of Messina', 'Siculum Fretum') == 'Siculum Fretum'


def test_delos_shechem_and_the_malian_gulf_take_their_english_forms():
    assert A.english('Delus') == 'Delos'
    assert A.english('Sychem') == 'Shechem'
    assert A.english('Maliacus Sinus') == 'Malian Gulf'


def test_the_event_place_corrections_set_the_pleiades_place_and_both_names():
    con = sqlite3.connect(':memory:')
    con.execute('CREATE TABLE events (id TEXT, pleiades_id TEXT, place_ancient TEXT, place TEXT)')
    con.execute("INSERT INTO events VALUES ('Q160387', '1046', 'Ionian Sea', 'Ionian Sea'), ('Q1', '5', 'Tarentum', 'Taranto')")
    assert G.apply_event_places(con) == 1
    assert con.execute("SELECT pleiades_id, place_ancient, place FROM events WHERE id = 'Q160387'").fetchone() == ('530771', 'Actium', 'Aktio')
    assert con.execute("SELECT pleiades_id, place_ancient, place FROM events WHERE id = 'Q1'").fetchone() == ('5', 'Tarentum', 'Taranto')
