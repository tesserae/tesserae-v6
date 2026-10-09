"""scripts/reuse/build_documents_reuse_table.py: the cross-collection
literary-vs-documents reuse table (cache/reuse_pairs/<lang>_documents.db).

Builds tiny fixture literary lemma caches (the same JSON shape
scripts/reuse/build_reuse_table.py's own discover_corpus reads) and a tiny
fixture documents index db (the same texts/lines/postings shape
scripts/documents/build_documents_index.py writes), so this runs with no
real corpus or documents index present -- the pattern tests/
test_build_reuse_table_pairs.py and tests/test_reuse_routes.py already use.
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'reuse'))

import build_documents_reuse_table as bdrt  # noqa: E402

VERGIL_TOKENS = ['arma', 'uirumque', 'cano', 'troiae', 'qui', 'primus', 'ab', 'oris']
VERGIL_LEMMAS = ['armo', 'uir', 'cano', 'troia', 'qui', 'primus', 'ab', 'ora']


def _write_literary_cache(cache_root, language, work, lines):
    """lines: [(ref, tokens, lemmas)]."""
    lang_dir = os.path.join(cache_root, language)
    os.makedirs(lang_dir, exist_ok=True)
    units = [{'ref': ref, 'text': ' '.join(tokens), 'tokens': tokens, 'lemmas': lemmas,
              'original_tokens': tokens}
             for ref, tokens, lemmas in lines]
    data = {'text_id': work, 'language': language, 'units_line': units}
    with open(os.path.join(lang_dir, work + '.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f)


def _build_documents_index(path, docs):
    """docs: [(doc_id, bucket_filename, ref, content, tokens, lemmas)].
    Writes the minimal texts/lines/postings schema this module's
    discover_documents/document_lemma_doc_counts read."""
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE texts (text_id INTEGER PRIMARY KEY, filename TEXT UNIQUE, "
                 "author TEXT, title TEXT, line_count INTEGER)")
    conn.execute("CREATE TABLE lines (text_id INTEGER, ref TEXT, content TEXT, lemmas TEXT, "
                 "tokens TEXT, PRIMARY KEY (text_id, ref))")
    conn.execute("CREATE TABLE postings (lemma TEXT, text_id INTEGER, ref TEXT, positions TEXT)")
    buckets = {}
    for doc_id, bucket, ref, content, tokens, lemmas in docs:
        if bucket not in buckets:
            tid = len(buckets) + 1
            buckets[bucket] = tid
            conn.execute("INSERT INTO texts VALUES (?,?,?,?,?)", (tid, bucket, '', '', 0))
        tid = buckets[bucket]
        conn.execute("INSERT INTO lines VALUES (?,?,?,?,?)",
                     (tid, ref, content, json.dumps(lemmas), json.dumps(tokens)))
        for i, lem in enumerate(lemmas):
            conn.execute("INSERT INTO postings VALUES (?,?,?,?)", (lem, tid, ref, json.dumps([i])))
    conn.commit()
    conn.close()


def _write_formula_words(path, words):
    with open(path, 'w', encoding='utf-8') as f:
        f.write("# test formula words\n")
        for w in words:
            f.write(w + "\n")


def _run_build(tmp_path, language='la'):
    index_db_path = os.path.join(tmp_path, 'index.db')
    doc_lines, doc_lemma_counts = bdrt.discover_documents(language, str(tmp_path))
    # discover_documents expects <lang>_documents_index.db under the dir
    # it is passed -- the fixture above wrote it at tmp_path/index.db, so
    # point it at tmp_path with the right filename instead.
    return doc_lines, doc_lemma_counts


def test_shared_quotation_is_kept_as_a_strict_pair(tmp_path, monkeypatch):
    """A document line that verbatim-repeats a literary line produces a
    pair with shared>=2 (the shape backend/reuse_documents.line() reads
    as tier 'strict') -- the Pompeii-graffito case this feature exists
    for (Aen. 1.1 "arma virumque cano...")."""
    cache_root = os.path.join(tmp_path, 'cache_lemmas')
    _write_literary_cache(cache_root, 'la', 'vergil.aeneid', [
        ('verg. aen. 1.1', VERGIL_TOKENS, VERGIL_LEMMAS),
    ])
    index_db = os.path.join(tmp_path, 'la_documents_index.db')
    _build_documents_index(index_db, [
        ('edr:GRAFFITO1', 'edr__pompeii.tess', 'edr:GRAFFITO1',
         'Arma virumque cano Troiae qui primus ab oris',
         VERGIL_TOKENS, VERGIL_LEMMAS),
    ])
    _write_formula_words(os.path.join(tmp_path, 'formula_words_la.txt'), [])
    monkeypatch.setattr(bdrt, 'FORMULA_WORDS_DIR_DEFAULT', str(tmp_path))

    orig = (bdrt.lit.TEXTS_DIR, bdrt.lit.CACHE_DIR)
    texts_root = os.path.join(tmp_path, 'texts')
    os.makedirs(os.path.join(texts_root, 'la'), exist_ok=True)
    with open(os.path.join(texts_root, 'la', 'vergil.aeneid.tess'), 'w', encoding='utf-8') as f:
        f.write('<verg. aen. 1.1>\tArma virumque cano, Troiae qui primus ab oris\n')
    bdrt.lit.TEXTS_DIR = texts_root
    bdrt.lit.CACHE_DIR = cache_root
    bdrt.lemma_cache_mod.TEXTS_DIR = texts_root
    bdrt.lemma_cache_mod.CACHE_DIR = cache_root
    try:
        # get_cached_units validates the cache's file_hash against the live
        # .tess file; write a cache whose file_hash matches it, via the same
        # helper production's own cache builder uses.
        import hashlib
        file_hash = hashlib.md5(open(os.path.join(texts_root, 'la', 'vergil.aeneid.tess'), 'rb').read()).hexdigest()  # nosec B324
        cache_path = os.path.join(cache_root, 'la', 'vergil.aeneid.json')
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data['file_hash'] = file_hash
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        lit_cache_data, skipped, missing = bdrt.lit.discover_corpus('la')
    finally:
        bdrt.lit.TEXTS_DIR, bdrt.lit.CACHE_DIR = orig
        bdrt.lemma_cache_mod.TEXTS_DIR, bdrt.lemma_cache_mod.CACHE_DIR = orig

    assert not missing, f"lemma cache should have validated: {missing}"
    doc_lines, doc_lemma_counts = bdrt.discover_documents('la', str(tmp_path))
    assert len(doc_lines) == 1

    formula_words = bdrt.load_formula_words('la')
    index_path = os.path.join(tmp_path, 'combined_index.db')
    stats, formula_hashes = bdrt.build_combined_index(
        lit_cache_data, doc_lines, index_path, max_df=200,
        formula_words=formula_words, doc_lemma_counts=doc_lemma_counts, language='la')
    pair_info, pair_stats = bdrt.find_cross_pairs(
        index_path, min_shared=2, min_jaccard=0.15, min_shared_override=4,
        min_containment=0.5, rare_max_df=20, rare_min_containment=0.06,
        formula_hashes=formula_hashes)

    assert len(pair_info) == 1
    lit_work, lit_ref, lit_seq, doc_id, doc_ref, doc_seq, shared, jaccard, span_len = pair_info[0]
    assert lit_work == 'vergil.aeneid'
    assert lit_ref == 'verg. aen. 1.1'
    assert doc_id == 'edr:GRAFFITO1'
    assert shared >= 2


def test_formula_only_pair_is_excluded(tmp_path, monkeypatch):
    """A shared n-gram made entirely of formula words (data/documents/
    formula_words_<lang>.txt) is not evidence of reuse on its own -- a
    pair whose ONLY shared n-grams are formula-only is dropped, same as
    the literary table drops an all-commonplace-word pair."""
    cache_root = os.path.join(tmp_path, 'cache_lemmas')
    formula_tokens = ['dis', 'manibus', 'sacrum', 'hic', 'situs', 'est', 'bene', 'merenti']
    formula_lemmas = ['deus', 'manus', 'sacer', 'hic', 'situs', 'sum', 'bene', 'mereo']
    _write_literary_cache(cache_root, 'la', 'some.epitaph_poem', [
        ('ep. 1', formula_tokens, formula_lemmas),
    ])
    index_db = os.path.join(tmp_path, 'la_documents_index.db')
    _build_documents_index(index_db, [
        ('edh:FORMULA1', 'edh__formula.tess', 'edh:FORMULA1',
         'Dis manibus sacrum hic situs est bene merenti',
         formula_tokens, formula_lemmas),
    ])
    # The real formula_words_*.txt lists are surface word FORMS, not
    # lemmas (stage 2 review measured document frequency of actual words,
    # e.g. "annis"/"annorum"/"annos" all separately) -- the builder's own
    # formula check tests a shared n-gram's TOKENS against this list (see
    # build_combined_index's formula pass), so the fixture must too.
    _write_formula_words(os.path.join(tmp_path, 'formula_words_la.txt'), formula_tokens)
    monkeypatch.setattr(bdrt, 'FORMULA_WORDS_DIR_DEFAULT', str(tmp_path))

    texts_root = os.path.join(tmp_path, 'texts')
    os.makedirs(os.path.join(texts_root, 'la'), exist_ok=True)
    with open(os.path.join(texts_root, 'la', 'some.epitaph_poem.tess'), 'w', encoding='utf-8') as f:
        f.write('<ep. 1>\tDis manibus sacrum hic situs est bene merenti\n')
    import hashlib
    file_hash = hashlib.md5(open(os.path.join(texts_root, 'la', 'some.epitaph_poem.tess'), 'rb').read()).hexdigest()  # nosec B324
    cache_path = os.path.join(cache_root, 'la', 'some.epitaph_poem.json')
    with open(cache_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data['file_hash'] = file_hash
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(data, f)

    orig = (bdrt.lit.TEXTS_DIR, bdrt.lit.CACHE_DIR)
    orig_lcm = (bdrt.lemma_cache_mod.TEXTS_DIR, bdrt.lemma_cache_mod.CACHE_DIR)
    bdrt.lit.TEXTS_DIR = texts_root
    bdrt.lit.CACHE_DIR = cache_root
    bdrt.lemma_cache_mod.TEXTS_DIR = texts_root
    bdrt.lemma_cache_mod.CACHE_DIR = cache_root
    try:
        lit_cache_data, skipped, missing = bdrt.lit.discover_corpus('la')
    finally:
        bdrt.lit.TEXTS_DIR, bdrt.lit.CACHE_DIR = orig
        bdrt.lemma_cache_mod.TEXTS_DIR, bdrt.lemma_cache_mod.CACHE_DIR = orig_lcm
    assert not missing

    doc_lines, doc_lemma_counts = bdrt.discover_documents('la', str(tmp_path))
    formula_words = bdrt.load_formula_words('la')
    assert formula_words, "the fixture formula word list should not be empty"

    index_path = os.path.join(tmp_path, 'combined_index.db')
    stats, formula_hashes = bdrt.build_combined_index(
        lit_cache_data, doc_lines, index_path, max_df=200,
        formula_words=formula_words, doc_lemma_counts=doc_lemma_counts, language='la')
    pair_info, pair_stats = bdrt.find_cross_pairs(
        index_path, min_shared=2, min_jaccard=0.15, min_shared_override=4,
        min_containment=0.5, rare_max_df=20, rare_min_containment=0.06,
        formula_hashes=formula_hashes)

    assert pair_info == [], (
        "an all-formula-word pair must be dropped; got " + repr(pair_info))
    assert pair_stats['candidates_excluded_all_formula'] >= 1


def test_document_lemma_doc_counts_counts_distinct_documents():
    """document_lemma_doc_counts counts DISTINCT documents sharing a lemma,
    not postings rows -- two rows for the same (lemma, doc_id) must count
    once, matching backend/documents.py's doc_for convention (split a ref
    on its first space to get the owning doc_id)."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'idx.db')
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE postings (lemma TEXT, text_id INTEGER, ref TEXT, positions TEXT)")
        # 'formula' lemma: two postings rows, same document (two lines of
        # one long inscription) -- must count as ONE document.
        conn.executemany("INSERT INTO postings VALUES (?,?,?,?)", [
            ('formula', 1, 'edh:LONG1 1', '[]'),
            ('formula', 1, 'edh:LONG1 2', '[]'),
            ('formula', 1, 'edh:LONG2', '[]'),
            ('rare', 1, 'edh:LONG1 1', '[]'),
        ])
        conn.commit()
        conn.close()
        counts = bdrt.document_lemma_doc_counts(path)
    assert counts['formula'] == 2   # edh:LONG1, edh:LONG2
    assert counts['rare'] == 1


def test_adjacent_lines_chain_into_a_span(tmp_path, monkeypatch):
    """Two consecutive literary lines, each quoted by the corresponding
    consecutive line of the SAME document, chain into one span_len=2 pair
    on both rows -- the same chaining rule the literary table applies to
    two literary works, applied here to a literary work and a document."""
    cache_root = os.path.join(tmp_path, 'cache_lemmas')
    line1_tok = ['primus', 'ego', 'in', 'patriam', 'mecum', 'modo', 'uita', 'supersit']
    line1_lem = ['primus', 'ego', 'in', 'patria', 'mecum', 'modo', 'uita', 'supersum']
    line2_tok = ['aonio', 'rediens', 'deducam', 'uertice', 'musas', 'nunc', 'age', 'festina']
    line2_lem = ['aonius', 'redeo', 'deduco', 'uertex', 'musa', 'nunc', 'ago', 'festino']
    _write_literary_cache(cache_root, 'la', 'vergil.georgics', [
        ('verg. g. 3.10', line1_tok, line1_lem),
        ('verg. g. 3.11', line2_tok, line2_lem),
    ])
    index_db = os.path.join(tmp_path, 'la_documents_index.db')
    _build_documents_index(index_db, [
        ('merged:1', 'merged__test.tess', 'merged:1 1',
         'Primus ego in patriam mecum modo vita supersit',
         line1_tok, line1_lem),
        ('merged:1', 'merged__test.tess', 'merged:1 2',
         'Aonio rediens deducam vertice musas nunc age festina',
         line2_tok, line2_lem),
    ])
    _write_formula_words(os.path.join(tmp_path, 'formula_words_la.txt'), [])
    monkeypatch.setattr(bdrt, 'FORMULA_WORDS_DIR_DEFAULT', str(tmp_path))

    texts_root = os.path.join(tmp_path, 'texts')
    os.makedirs(os.path.join(texts_root, 'la'), exist_ok=True)
    with open(os.path.join(texts_root, 'la', 'vergil.georgics.tess'), 'w', encoding='utf-8') as f:
        f.write('<verg. g. 3.10>\tPrimus ego in patriam mecum modo vita supersit\n')
        f.write('<verg. g. 3.11>\tAonio rediens deducam vertice musas nunc age festina\n')
    import hashlib
    file_hash = hashlib.md5(open(os.path.join(texts_root, 'la', 'vergil.georgics.tess'), 'rb').read()).hexdigest()  # nosec B324
    cache_path = os.path.join(cache_root, 'la', 'vergil.georgics.json')
    with open(cache_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data['file_hash'] = file_hash
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(data, f)

    orig = (bdrt.lit.TEXTS_DIR, bdrt.lit.CACHE_DIR)
    orig_lcm = (bdrt.lemma_cache_mod.TEXTS_DIR, bdrt.lemma_cache_mod.CACHE_DIR)
    bdrt.lit.TEXTS_DIR = texts_root
    bdrt.lit.CACHE_DIR = cache_root
    bdrt.lemma_cache_mod.TEXTS_DIR = texts_root
    bdrt.lemma_cache_mod.CACHE_DIR = cache_root
    try:
        lit_cache_data, skipped, missing = bdrt.lit.discover_corpus('la')
    finally:
        bdrt.lit.TEXTS_DIR, bdrt.lit.CACHE_DIR = orig
        bdrt.lemma_cache_mod.TEXTS_DIR, bdrt.lemma_cache_mod.CACHE_DIR = orig_lcm
    assert not missing

    doc_lines, doc_lemma_counts = bdrt.discover_documents('la', str(tmp_path))
    formula_words = bdrt.load_formula_words('la')
    index_path = os.path.join(tmp_path, 'combined_index.db')
    stats, formula_hashes = bdrt.build_combined_index(
        lit_cache_data, doc_lines, index_path, max_df=200,
        formula_words=formula_words, doc_lemma_counts=doc_lemma_counts, language='la')
    pair_info, pair_stats = bdrt.find_cross_pairs(
        index_path, min_shared=2, min_jaccard=0.15, min_shared_override=4,
        min_containment=0.5, rare_max_df=20, rare_min_containment=0.06,
        formula_hashes=formula_hashes)

    assert len(pair_info) == 2
    span_lens = {p[8] for p in pair_info}
    assert span_lens == {2}, f"both rows of a chained span must carry span_len=2, got {pair_info}"
