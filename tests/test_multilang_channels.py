"""Persian/Urdu/Arabic fusion-channel registration (Phase 3 of the multilang
deploy plan, DEPLOY_PLAN_2026-09-03.md, closing gap A2 code half).

AUDIT_2026-09-03.md found the old dev branches ran exactly 7 of the (then 10,
now 11) fusion channels for fa/ur/ar: the four unrestricted/language-agnostic
ones (lemma, lemma_min1, exact, rare_word) plus sound, edit_distance, and
quotation registered explicitly in CHANNEL_LANGUAGE_SUPPORT. dictionary,
syntax, and semantic were never enabled for these three, because no
cross-lingual synonym CSV, syntax DB, or semantic embedding model exists for
them in this codebase. These tests pin that same shape on current mainline so
it cannot silently drift (the same kind of regression test_hebrew_channels.py
exists to catch for Hebrew).

Run: pytest tests/test_multilang_channels.py -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.fusion import (CHANNEL_LANGUAGE_SUPPORT, WEIGHT_PROFILES,
                            get_channels_for_language, get_weight_profile)

_LANGUAGE_AGNOSTIC_CHANNELS = {'lemma', 'lemma_min1', 'exact', 'rare_word',
                               'sound', 'edit_distance', 'quotation'}
# 2026-09-05: form (refrain and rhyme) and semantic (multilingual-e5 line
# embeddings) were added for fa/ur/ar; dictionary and syntax still have no
# resource for these languages.
_ADDED_2026_09_05 = {'form', 'semantic'}
_NOT_SUPPORTED_CHANNELS = {'dictionary', 'syntax'}


class TestPersianUrduArabicChannels:
    def test_persian_has_the_seven_agnostic_channels(self):
        chans = set(get_channels_for_language('fa'))
        assert _LANGUAGE_AGNOSTIC_CHANNELS | _ADDED_2026_09_05 <= chans
        assert not (_NOT_SUPPORTED_CHANNELS & chans)

    def test_urdu_has_the_seven_agnostic_channels(self):
        chans = set(get_channels_for_language('ur'))
        assert _LANGUAGE_AGNOSTIC_CHANNELS | _ADDED_2026_09_05 <= chans
        assert not (_NOT_SUPPORTED_CHANNELS & chans)

    def test_arabic_has_the_seven_agnostic_channels(self):
        chans = set(get_channels_for_language('ar'))
        assert _LANGUAGE_AGNOSTIC_CHANNELS | _ADDED_2026_09_05 <= chans
        # Arabic also has the dictionary channel (root equivalence, 2026-09-05).
        assert 'dictionary' in chans and 'syntax' not in chans

    def test_fa_ur_ar_use_the_fitted_persian_ghazal_profile(self):
        # At the Phase 4 port no tuned profile existed for these languages and
        # this test guarded against inventing one. Phase 5 validation showed
        # the latin_epic defaults tie single-rare-word pairs at the score
        # ceiling in ghazal corpora, and on 2026-09-05 a profile was fitted on
        # the Persian, Urdu and Arabic gold tests (see fusion.py and
        # research/languages/PHASE6_PREP_2026-09-05.md, item 4). The guard now
        # asserts that fitted profile is the one selected, and nothing else.
        for lang in ('fa', 'ur', 'ar'):
            assert get_weight_profile(language=lang) == WEIGHT_PROFILES['persian_ghazal']
        assert WEIGHT_PROFILES['persian_ghazal'] != WEIGHT_PROFILES['latin_epic']

    def test_classical_and_hebrew_defaults_untouched(self):
        # Registering fa/ur/ar must not have perturbed any existing language.
        assert get_weight_profile(language='la') == WEIGHT_PROFILES['latin_epic']
        assert get_weight_profile(language='grc') == WEIGHT_PROFILES['latin_epic']
        assert get_weight_profile(language='he') == WEIGHT_PROFILES['biblical_hebrew']
        assert get_weight_profile(language='cop') == WEIGHT_PROFILES['biblical_coptic']
        for lang in ('fa', 'ur'):
            assert lang not in CHANNEL_LANGUAGE_SUPPORT['dictionary']
        assert 'ar' in CHANNEL_LANGUAGE_SUPPORT['dictionary']
        for lang in ('fa', 'ur', 'ar'):
            assert lang not in CHANNEL_LANGUAGE_SUPPORT['syntax']
            assert lang in CHANNEL_LANGUAGE_SUPPORT['semantic']
            assert lang in CHANNEL_LANGUAGE_SUPPORT['form']


class TestPersianUrduArabicLanguageHandlersRegister:
    """The plugin pattern: importing backend.<lang> and calling register()
    must not raise, must set the *_ENABLED flag, and must be idempotent
    (mirrors backend/coptic, backend/hebrew's own contract)."""

    def test_persian_registers(self):
        from backend.persian import register, PERSIAN_ENABLED as _unused
        register()
        from backend.persian import PERSIAN_ENABLED
        assert PERSIAN_ENABLED is True
        from backend.text_processor import _LANGUAGE_HANDLERS
        assert 'fa' in _LANGUAGE_HANDLERS

    def test_urdu_registers(self):
        from backend.urdu import register, URDU_ENABLED as _unused
        register()
        from backend.urdu import URDU_ENABLED
        assert URDU_ENABLED is True
        from backend.text_processor import _LANGUAGE_HANDLERS
        assert 'ur' in _LANGUAGE_HANDLERS

    def test_arabic_registers(self):
        from backend.arabic import register, ARABIC_ENABLED as _unused
        register()
        from backend.arabic import ARABIC_ENABLED
        assert ARABIC_ENABLED is True
        from backend.text_processor import _LANGUAGE_HANDLERS
        assert 'ar' in _LANGUAGE_HANDLERS

    def test_stoplists_registered(self):
        from backend.persian import register as reg_fa
        from backend.urdu import register as reg_ur
        from backend.arabic import register as reg_ar
        reg_fa(); reg_ur(); reg_ar()
        from backend.fusion import _STOPLISTS
        assert len(_STOPLISTS.get('fa', set())) > 0
        assert len(_STOPLISTS.get('ur', set())) > 0
        assert len(_STOPLISTS.get('ar', set())) > 0


class TestSemanticModelSelection:
    def test_fa_ur_ar_use_multilingual_e5_and_others_unchanged(self):
        from backend.semantic_similarity import (model_name_for, E5_MODEL,
                                                 LATIN_GREEK_MODEL, HEBREW_MODEL)
        for lang in ('fa', 'ur', 'ar'):
            assert model_name_for(lang) == E5_MODEL
        for lang in ('la', 'grc', 'en', 'cop'):
            assert model_name_for(lang) == LATIN_GREEK_MODEL
        assert model_name_for('he') == HEBREW_MODEL


class TestE5SemanticPath:
    def test_floor_rescale_and_ref_alignment(self, monkeypatch, tmp_path):
        """fa/ur/ar: cosine floor 0.90, scores rescaled from the compressed
        e5 band, and a chunk of a text reads its own rows by ref."""
        import json
        import numpy as np
        import backend.semantic_similarity as SS
        import backend.embedding_storage as ES
        rng = np.random.default_rng(0)
        emb = rng.normal(size=(6, 8)).astype('float32')
        emb[4] = emb[1]  # target row 4 is identical to source row 1
        np.save(tmp_path / 't.npy', emb)
        json.dump({'line_refs': [f'x.{i}' for i in range(6)]}, open(tmp_path / 't.meta.json', 'w'))
        monkeypatch.setattr(ES, 'load_embeddings', lambda p, l: np.load(tmp_path / 't.npy'))
        monkeypatch.setattr(ES, 'get_metadata_path', lambda p, l: str(tmp_path / 't.meta.json'))
        units = lambda idxs: [{'ref': f'x.{i}', 'text': 't'} for i in idxs]
        # source = rows 0..2, target = a CHUNK starting at row 3 (rows 3..5)
        m, _ = SS.find_semantic_matches(units([0, 1, 2]), units([3, 4, 5]),
                                        {'language': 'fa', 'source_text_path': 'a', 'target_text_path': 'b'})
        assert m, 'the identical pair must survive the 0.90 floor'
        top = max(m, key=lambda x: x['cosine'])
        assert (top['source_idx'], top['target_idx']) == (1, 1)  # row 4 = second unit of the chunk
        assert abs(top['cosine'] - 1.0) < 1e-5 and abs(top['semantic_score'] - 1.0) < 1e-5
        assert all(x['cosine'] >= 0.90 for x in m)
        # The floor is the search's own 99.9th percentile (never below 0.90),
        # and the identical pair, at cosine 1.0, is the only one above it here.
        assert len(m) == 1


class TestArabicRoots:
    def test_roots_and_lookup(self):
        from backend.arabic.roots import arabic_root, build_root_lookup
        assert arabic_root('يستغفرون') == arabic_root('مغفرة') == 'غفر'
        assert arabic_root('بالقمر') == arabic_root('القمر') == 'قمر'
        a = [{'lemmas': ['قمر', 'انشق']}]; b = [{'lemmas': ['القمر', 'الساعة']}]
        lk = build_root_lookup(a, b)
        assert 'القمر' in lk['قمر'] and 'قمر' in lk['القمر']

    def test_dictionary_channel_fires_on_a_shared_root(self):
        import backend.arabic; backend.arabic.register()
        from backend.semantic_similarity import find_dictionary_matches
        src = [{'ref': 'q.1', 'text': '', 'tokens': ['اقتربت', 'الساعة', 'وانشق', 'القمر'], 'lemmas': ['اقتربت', 'الساعة', 'وانشق', 'القمر']}]
        tgt = [{'ref': 'b.1', 'text': '', 'tokens': ['اقسمت', 'بالقمر', 'المنشق'], 'lemmas': ['اقسمت', 'بالقمر', 'المنشق']}]
        m, _ = find_dictionary_matches(src, tgt, {'language': 'ar'})
        assert m and 'بالقمر' in m[0]['matched_lemmas']


class TestRareRoots:
    def test_rare_root_pair_in_different_forms(self, monkeypatch):
        import backend.arabic; backend.arabic.register()
        import backend.blueprints.hapax as H
        import backend.arabic.roots as R
        monkeypatch.setattr(H, '_corpus_token_frequencies', lambda lemmas, lang: {l: 5000 for l in lemmas})
        monkeypatch.setattr(R, 'root_frequencies', lambda: ({'شهب': 4, 'علم': 843}, 88646))
        src = [{'lemmas': ['استرق', 'الشهاب', 'علم']}]
        tgt = [{'lemmas': ['شهب', 'مصباح', 'علم']}]
        m = H.find_rare_word_matches_direct(src, tgt, language='ar', max_occurrences=100)
        rr = [x for x in m if x.get('rare_root')]
        assert rr and rr[0]['synonym_pairs'] == [('الشهاب', 'شهب')]
        assert not any('علم' in (x.get('matched_lemmas') or []) for x in rr)
