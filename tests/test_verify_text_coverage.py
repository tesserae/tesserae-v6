"""Store checks of scripts/corpus/verify_text_coverage.py (syntax, names, wnames, descfts, reuse, meter, label),
against tiny fixture stores built in a temporary folder."""
import importlib.util
import os
import sqlite3

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      'scripts', 'corpus', 'verify_text_coverage.py')
spec = importlib.util.spec_from_file_location('verify_text_coverage', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _db(path, ddl, rows=()):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    c = sqlite3.connect(path)
    for d in ddl:
        c.execute(d)
    for sql, args in rows:
        c.execute(sql, args)
    c.commit()
    c.close()


def _write_tess(path, n=12):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        for i in range(n):
            fh.write(f'<fix. work. 1.{i + 1}>\tarma virumque cano {i}\n')


def test_syntax_files_true_false_and_not_applicable(tmp_path):
    _db(str(tmp_path / 'data/inverted_index/syntax_latin.db'),
        ['create table texts (text_id integer primary key, filename text unique)'],
        [('insert into texts (filename) values (?)', ('fix.work.tess',))])
    have = mod.syntax_files(str(tmp_path), 'la')
    assert 'fix.work.tess' in have and 'fix.other.tess' not in have
    assert mod.syntax_files(str(tmp_path), 'en') is None      # no parser for English: column is '-'
    assert mod.syntax_files(str(tmp_path), 'grc') == set()    # language with a parser but no database yet


def test_entity_names_and_desc_stores_per_window(tmp_path):
    root = str(tmp_path)
    _db(root + '/data/entity_index/entities.sqlite',
        ['create table windows (wid integer primary key, window_id text, work text, ref_start text, ref_end text, language text)'],
        [('insert into windows (window_id, work, language) values (?,?,?)', ('fix.work:fine:0', 'fix.work', 'la'))])
    _db(root + '/data/passage_index/window_names.db',
        ['create table window_names (id text, k text, form text)'],
        [('insert into window_names values (?,?,?)', ('fix.work:fine:0', 'iesus', 'Iesus'))])
    _db(root + '/data/passage_index/desc_fts.sqlite',
        ['create table desc_content (id integer primary key, c0, c1)'],
        [('insert into desc_content (c0, c1) values (?,?)', ('fix.work:fine:0', 'text')),
         ('insert into desc_content (c0, c1) values (?,?)', ('fix.work:fine:1', 'text'))])
    ent, wn, fts = mod.entity_work_counts(root), mod.window_name_works(root), mod.desc_fts_counts(root)
    assert ent == {'fix.work': 1} and wn == {'fix.work': 1} and fts == {'fix.work': 2}
    win = {'fix.work': 2, 'fix.new': 3}
    # true: the work has rows
    assert mod.store_flag('fix.work', 'fix.work', False, 12, {}, win, ent) is True
    # false: windows exist and the store has no row for the work
    assert mod.store_flag('fix.new', 'fix.new', False, 12, {}, win, ent) is False
    assert mod.store_flag('fix.new', 'fix.new', False, 12, {}, win, wn) is False
    # descfts must reach the window count
    assert mod.store_flag('fix.work', 'fix.work', False, 12, {}, win, fts, full=True) is True
    assert mod.store_flag('fix.work', 'fix.work', False, 12, {}, win, {'fix.work': 1}, full=True) is False
    # not applicable: no windows, or a file too short to make one
    assert mod.store_flag('fix.none', 'fix.none', False, 12, {}, win, ent) is True
    assert mod.store_flag('fix.new', 'fix.new', False, 3, {}, win, ent) is True


def test_store_flag_for_whole_with_parts_and_for_a_part(tmp_path):
    parts = {'fix.w.part.1': 40, 'fix.w.part.2': 2}
    win = {'fix.w.part.1': 3}
    assert mod.store_flag('fix.w', 'fix.w', False, 42, parts, win, {'fix.w.part.1': 1}) is True
    assert mod.store_flag('fix.w', 'fix.w', False, 42, parts, win, {}) is False
    # a part whose windows live under the whole work
    assert mod.store_flag('fix.w.part.1', 'fix.w', True, 40, {}, {'fix.w': 4}, {'fix.w': 1}) is True
    assert mod.store_flag('fix.w.part.1', 'fix.w', True, 40, {}, {'fix.w': 4}, {}) is False


def test_reuse_works_and_flag(tmp_path):
    root = str(tmp_path)
    _db(root + '/cache/reuse_pairs/la.db', ['create table line_counts (work text, line_ref text, n_works integer)'],
        [('insert into line_counts values (?,?,?)', ('fix.work', 'r 1', 1))])
    reuse = mod.reuse_works(root, 'la')
    assert mod.reuse_flag('fix.work', 'fix.work', False, reuse) is True
    assert mod.reuse_flag('fix.work.part.1', 'fix.work', True, reuse) is True    # part resolves to its whole
    assert mod.reuse_flag('fix.new', 'fix.new', False, reuse) is False
    assert mod.reuse_works(root, 'cop') is None and mod.reuse_flag('x', 'x', False, None) == '-'
    assert mod.reuse_works(root, 'fa') == set()                                   # table not built


def test_meter_flag_not_applicable_for_prose_and_uses_scanner_for_verse(tmp_path, monkeypatch):
    p = tmp_path / 'texts/la/fix.work.tess'
    _write_tess(str(p))
    assert mod.first_lines(str(p), 2)[0][0] == 'fix. work. 1.1'
    assert mod.meter_flag(str(p), {'meter': 'prose'}) == '-'
    assert mod.meter_flag(str(p), None) == '-'
    import sys
    import types
    fake = types.ModuleType('backend.metrical_scanner')
    fake.lookup_mqdq_scansion = lambda tag: None
    fake.detect_meter_type = lambda name: 'hexameter'
    fake.scan_latin_verse = lambda text, m: {'pattern': '-uu-uu'}
    monkeypatch.setitem(sys.modules, 'backend.metrical_scanner', fake)
    monkeypatch.setitem(sys.modules, 'backend', types.ModuleType('backend'))
    assert mod.meter_flag(str(p), {'meter': 'hexameter'}) is True
    fake.scan_latin_verse = lambda text, m: None
    assert mod.meter_flag(str(p), {'meter': 'hexameter'}) == 'no scansion'


def test_label_flag_author_and_fragment():
    rows = [('publius vergilius maro', 'aeneid'), ('anonymous', 'carmen de bello actiaco')]
    ok = {'author': 'Publius Vergilius Maro', 'work': 'Aeneid'}
    assert mod.label_flag('vergil.aeneid.tess', ok, rows) is True
    wrong_author = {'author': 'Vergil', 'work': 'Aeneid'}
    assert mod.label_flag('vergil.aeneid.tess', wrong_author, rows).startswith('check: author shown')
    fragment = {'author': 'Anonymous', 'work': 'Carmen'}
    assert 'one word of' in mod.label_flag('anonymous.carmen_de_bello_actiaco.tess', fragment, rows)
    assert mod.label_flag('anonymous.carmen_de_bello_actiaco.tess',
                          {'author': 'Anonymous', 'work': 'Carmen de Bello Actiaco'}, rows) is True
    assert mod.label_flag('x.y.tess', {}, rows) == 'no-api'
