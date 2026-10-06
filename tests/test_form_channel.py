#!/usr/bin/env python3
"""
Tests for the refrain-and-rhyme ("form") fusion channel (backend/poetics.py),
its scorer branch (backend/scorer.py Scorer._score_form_match), and its
fusion wiring (backend/fusion.py CHANNEL_WEIGHTS / WEIGHT_PROFILES /
CHANNEL_ORDER / CHANNEL_LANGUAGE_SUPPORT / CHANNEL_CONFIGS / run_channel /
fuse_results' rarity bypass).

Spec: research/languages/FORM_CHANNEL_SPEC_2026-09-05.md (Tesserae V6 dev
repo). Run with:
    /home/ncoffee/tesserae-v6-dev/venv/bin/python -m pytest tests/test_form_channel.py -v
"""
import csv
import os
import re
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

_FORM_CHANNEL_SKIP = (
    "stage 2b: the 'form' (refrain/rhyme) fusion channel is not yet wired "
    "into backend/fusion.py (CHANNEL_WEIGHTS, CHANNEL_ORDER, CHANNEL_CONFIGS, "
    "CHANNEL_LANGUAGE_SUPPORT, WEIGHT_PROFILES['persian_ghazal']) or "
    "backend/scorer.py (Scorer._score_form_match). Applied in stage 2b."
)
_TEXTS_MISSING_SKIP = (
    "corpus files not in the repository: the texts/ar, texts/fa and "
    "texts/ur .tess files this test reads are held back by the licensing "
    "guardrail on those three languages' texts and reach the repository "
    "only as a later data operation, not through this module port."
)

# Register the Persian and Urdu plugins so backend.fusion._STOPLISTS['fa']
# and ['ur'] are populated -- the matching rule (stoplisted single-token
# radif) needs the real curated lists, mirroring test_multilang_channels.py.
from backend.persian import register as _register_persian
from backend.urdu import register as _register_urdu
_register_persian()
_register_urdu()

from backend.persian.processor import tokenize_persian, normalize_persian
from backend.urdu.processor import tokenize_urdu, normalize_urdu
from backend.poetics import segment_poems, poem_signature, find_form_matches
from backend.fusion import (
    CHANNEL_WEIGHTS, WEIGHT_PROFILES, CHANNEL_ORDER, CHANNEL_LANGUAGE_SUPPORT,
    CHANNEL_CONFIGS, get_channels_for_language, get_weight_profile, fuse_results,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mk_fa(ref, text):
    tokens, _ = tokenize_persian(text)
    return {'ref': ref, 'text': text, 'tokens': tokens, 'lemmas': tokens}


def _mk_ur(ref, text):
    tokens, _, _ = tokenize_urdu(text)
    return {'ref': ref, 'text': text, 'tokens': tokens, 'lemmas': tokens}


def _units_from_tess(path, language, lo=None, hi=None, ref_prefixes=None):
    """Read a .tess file directly and build V6-style unit dicts with the
    real language tokenizer (lemmas = tokens, per the spec's allowance).
    lo/hi filter by the ref's LAST numeric component; ref_prefixes filters
    by literal ref prefix (used for poem-numbered refs)."""
    mk = _mk_ur if language == 'ur' else _mk_fa
    units = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            m = re.match(r'<([^>]+)>\t(.*)', line)
            if not m:
                continue
            ref, text = m.group(1), m.group(2).strip()
            if ref_prefixes is not None and not any(ref.startswith(p) for p in ref_prefixes):
                continue
            if lo is not None:
                nums = [int(x) for x in re.findall(r'\d+', ref)]
                if not nums or not (lo <= nums[-1] <= hi):
                    continue
            units.append(mk(ref, text))
    return units


TEXTS_FA = os.path.join(PROJECT_ROOT, 'texts', 'fa')
TEXTS_UR = os.path.join(PROJECT_ROOT, 'texts', 'ur')
DATA_POETICS = os.path.join(PROJECT_ROOT, 'data', 'poetics')


# ---------------------------------------------------------------------------
# 1. Segmentation
# ---------------------------------------------------------------------------

class TestSegmentation:
    def test_ref_based_hemistich_poem_numbered(self):
        """x.ghazal.N.N style: poem boundary = ref minus last component;
        radif on the opening two lines and every second line after."""
        lines = [
            ('x.ghazal.1.1', 'الف ب شب'),
            ('x.ghazal.1.2', 'ج د شب'),
            ('x.ghazal.1.3', 'ه و'),
            ('x.ghazal.1.4', 'ز ح شب'),
            ('x.ghazal.1.5', 'ط ی'),
            ('x.ghazal.1.6', 'ك ل شب'),
            ('x.ghazal.2.1', 'م ن روز'),
            ('x.ghazal.2.2', 'س ع روز'),
            ('x.ghazal.2.3', 'ف ص'),
            ('x.ghazal.2.4', 'ق ر روز'),
        ]
        units = [_mk_fa(r, t) for r, t in lines]
        poems = segment_poems(units, 'fa')
        assert [p.key for p in poems] == ['x.ghazal.1', 'x.ghazal.2']
        assert poems[0].unit_idxs == [0, 1, 2, 3, 4, 5]
        assert poems[1].unit_idxs == [6, 7, 8, 9]
        assert poems[0].layout == 'hemistich'
        assert poems[1].layout == 'hemistich'

    def test_ref_based_couplet_pipe_poem_numbered(self):
        """author.work.N.N style (like iqbal.zabur_e_ajam.1.1: 4 total
        dot-components, so the ref rule fires) with ' | ' inside the line:
        layout is couplet_pipe, poem boundary is ref minus last component."""
        lines = [
            ('x.work.1.1', 'الف ب شب | ج د شب'),
            ('x.work.1.2', 'ه و نو | ز ح شب'),
            ('x.work.1.3', 'ط ی نو | ك ل شب'),
            ('x.work.2.1', 'م ن روز | س ع روز'),
            ('x.work.2.2', 'ف ص نو | ق ر روز'),
        ]
        units = [_mk_fa(r, t) for r, t in lines]
        poems = segment_poems(units, 'fa')
        assert [p.key for p in poems] == ['x.work.1', 'x.work.2']
        assert poems[0].unit_idxs == [0, 1, 2]
        assert poems[1].unit_idxs == [3, 4]
        assert poems[0].layout == 'couplet_pipe'
        assert poems[1].layout == 'couplet_pipe'

    def test_run_heuristic_line_numbered_only(self):
        """No poem-numbering in the ref at all (y.1, y.2, ...): fall back to
        the run heuristic. Keeps poems with >=6 lines of which >=3 end with
        the radif; a buffer of unrelated lines separates the two ghazals."""
        lines = [
            ('y.1', 'الف شب'), ('y.2', 'ب شب'), ('y.3', 'ج نو'),
            ('y.4', 'د شب'), ('y.5', 'ه نو'), ('y.6', 'و شب'),
            ('y.7', 'زط پنجم'), ('y.8', 'حك ششم'), ('y.9', 'من هفتم'),
            ('y.10', 'الف روز'), ('y.11', 'ب روز'), ('y.12', 'ج نو2'),
            ('y.13', 'د روز'), ('y.14', 'ه نو2'), ('y.15', 'و روز'),
        ]
        units = [_mk_fa(r, t) for r, t in lines]
        poems = segment_poems(units, 'fa')
        assert len(poems) == 2
        assert poems[0].unit_idxs == [0, 1, 2, 3, 4, 5, 6]
        assert poems[1].unit_idxs == [9, 10, 11, 12, 13, 14]
        assert poems[0].layout == 'hemistich'

    def test_run_heuristic_tolerates_one_non_radif_line(self):
        """A single non-radif line between radif lines does not split the
        poem (spec: 'tolerate one non-radif line between radif lines')."""
        lines = [
            ('z.1', 'الف شب'), ('z.2', 'ب نو'), ('z.3', 'ج شب'),
            ('z.4', 'د نو'), ('z.5', 'ه شب'), ('z.6', 'و نو'),
            ('z.7', 'ز شب'), ('z.8', 'ح نو'),
        ]
        units = [_mk_fa(r, t) for r, t in lines]
        poems = segment_poems(units, 'fa')
        assert len(poems) == 1
        assert poems[0].unit_idxs == list(range(8))

    def test_run_heuristic_rejects_too_short_run(self):
        """Fewer than 6 lines, or fewer than 3 radif lines: not a poem for
        this channel's purposes -- emits nothing."""
        lines = [
            ('w.1', 'الف شب'), ('w.2', 'ب نو'), ('w.3', 'ج شب'), ('w.4', 'د نو'),
        ]
        units = [_mk_fa(r, t) for r, t in lines]
        poems = segment_poems(units, 'fa')
        assert poems == []


# ---------------------------------------------------------------------------
# 2. Signature
# ---------------------------------------------------------------------------

class TestSignature:
    def test_single_token_radif_and_qafia(self):
        lines = [
            ('x.ghazal.1.1', 'الف جانان شما'),
            ('x.ghazal.1.2', 'ج فرمان شما'),
            ('x.ghazal.1.3', 'ه و'),
            ('x.ghazal.1.4', 'ز زمان شما'),
            ('x.ghazal.1.5', 'ط ی'),
            ('x.ghazal.1.6', 'ك دوران شما'),
        ]
        units = [_mk_fa(r, t) for r, t in lines]
        poem = segment_poems(units, 'fa')[0]
        radif, qafia, idxs = poem_signature(poem, 'fa')
        assert radif == ('شما',)
        assert qafia == 'ان'
        assert idxs == [0, 1, 3, 5]

    def test_multi_token_radif_urdu_rakhte_hain(self):
        lines = [
            ('x.ghazal.1.1', 'الف ب رکھتے ہیں'),
            ('x.ghazal.1.2', 'ج د رکھتے ہیں'),
            ('x.ghazal.1.3', 'ه و نو'),
            ('x.ghazal.1.4', 'ز ح رکھتے ہیں'),
            ('x.ghazal.1.5', 'ط ی نو'),
            ('x.ghazal.1.6', 'ك ل رکھتے ہیں'),
        ]
        units = [_mk_ur(r, t) for r, t in lines]
        poem = segment_poems(units, 'ur')[0]
        radif, qafia, idxs = poem_signature(poem, 'ur')
        expected = (normalize_urdu('رکھتے'), normalize_urdu('ہیں'))
        assert radif == expected
        assert idxs == [0, 1, 3, 5]

    def test_multi_token_radif_urdu_hota_hai(self):
        lines = [
            ('x.ghazal.1.1', 'الف ب ہوتا ہے'),
            ('x.ghazal.1.2', 'ج د ہوتا ہے'),
            ('x.ghazal.1.3', 'ه و نو'),
            ('x.ghazal.1.4', 'ز ح ہوتا ہے'),
            ('x.ghazal.1.5', 'ط ی نو'),
            ('x.ghazal.1.6', 'ك ل ہوتا ہے'),
        ]
        units = [_mk_ur(r, t) for r, t in lines]
        poem = segment_poems(units, 'ur')[0]
        radif, qafia, idxs = poem_signature(poem, 'ur')
        expected = (normalize_urdu('ہوتا'), normalize_urdu('ہے'))
        assert radif == expected

    def test_radifless_poem(self):
        """No line-final token sequence shared by >=60% of candidate lines:
        radif is empty, and qafia falls back to the plain final token."""
        lines = [
            ('y.ghazal.1.1', 'الف ب پنجم'),
            ('y.ghazal.1.2', 'ج د ششم'),
            ('y.ghazal.1.3', 'ه و هفتم'),
            ('y.ghazal.1.4', 'ز ح هشتم'),
            ('y.ghazal.1.5', 'ط ی نهم'),
            ('y.ghazal.1.6', 'ك ل دهم'),
        ]
        units = [_mk_fa(r, t) for r, t in lines]
        poem = segment_poems(units, 'fa')[0]
        radif, qafia, idxs = poem_signature(poem, 'fa')
        assert radif == ()
        # Fallback qafia is the most common last-two-letters over all lines
        # (two lines each end in -tam and -ham; either is acceptable).
        assert qafia in ('تم', 'هم')

    def test_trailing_punctuation_stripped(self):
        """A token with Arabic-script punctuation fused onto its end (no
        separating space -- confirmed the Persian tokenizer produces this,
        e.g. 'شما،') must still match the clean form."""
        lines = [
            ('x.ghazal.1.1', 'الف جانان شما،'),
            ('x.ghazal.1.2', 'ج فرمان شما'),
            ('x.ghazal.1.3', 'ه و'),
            ('x.ghazal.1.4', 'ز زمان شما.'),
            ('x.ghazal.1.5', 'ط ی'),
            ('x.ghazal.1.6', 'ك دوران شما؟'),
        ]
        units = [_mk_fa(r, t) for r, t in lines]
        # Since 2026-09-06 the tokenizers drop Arabic-script punctuation, so
        # the mark no longer rides on the token; the signature must match
        # either way (older lemma caches still carry the fused form).
        assert units[0]['tokens'][-1] in ('شما', 'شما،')
        poem = segment_poems(units, 'fa')[0]
        radif, qafia, idxs = poem_signature(poem, 'fa')
        assert radif == ('شما',)
        assert idxs == [0, 1, 3, 5]


# ---------------------------------------------------------------------------
# 3. Matching rule
# ---------------------------------------------------------------------------

import pytest as _pytest
from backend import poetics as _poetics


@_pytest.fixture(autouse=True)
def _no_corpus_tables(monkeypatch):
    """The unit tests reason about two texts in isolation; keep the corpus-wide
    refrain tables (data/poetics/form_signatures_<lang>.json) out of them."""
    monkeypatch.setattr(_poetics, '_FORM_SIG_CACHE', {'fa': None, 'ur': None, 'ar': None})


class TestMatchingRule:
    def _poem(self, mk, lines, language):
        units = [mk(r, t) for r, t in lines]
        return units, segment_poems(units, language)[0]

    def test_radif_and_qafia_equal_scores_one(self):
        src_lines = [
            ('s.ghazal.1.1', 'الف جانان شما'), ('s.ghazal.1.2', 'ج فرمان شما'),
            ('s.ghazal.1.3', 'ه و'), ('s.ghazal.1.4', 'ز زمان شما'),
            ('s.ghazal.1.5', 'ط ی'), ('s.ghazal.1.6', 'ك دوران شما'),
        ]
        tgt_lines = [
            ('t.ghazal.1.1', 'م خیابان شما'), ('t.ghazal.1.2', 'ن کافرستان شما'),
            ('t.ghazal.1.3', 'س ع'), ('t.ghazal.1.4', 'ف بیابان شما'),
            ('t.ghazal.1.5', 'ق ر'), ('t.ghazal.1.6', 'ص ض بدخشان شما'),
        ]
        src = [_mk_fa(r, t) for r, t in src_lines]
        tgt = [_mk_fa(r, t) for r, t in tgt_lines]
        matches, stats = find_form_matches(src, tgt, {'language': 'fa'})
        assert stats['poem_pairs'] == 1
        assert matches
        assert all(m['form_base'] == 1.0 for m in matches)
        # One poem on each side with this signature: no rarity discount.
        assert all(m['form_rarity'] == 1.0 for m in matches)
        # The pair of opening lines carries the full score; the rest a share.
        assert max(m['form_score'] for m in matches) == 1.0
        assert {m['form_score'] for m in matches} <= {1.0, 0.6}
        assert all(m['radif'] == 'شما' for m in matches)

    def test_radif_equal_qafia_differs_multi_token_scores_half(self):
        src_lines = [
            ('s.ghazal.1.1', 'الف ب رکھتے ہیں'), ('s.ghazal.1.2', 'ج د رکھتے ہیں'),
            ('s.ghazal.1.3', 'ه و نو'), ('s.ghazal.1.4', 'ز ح رکھتے ہیں'),
            ('s.ghazal.1.5', 'ط ی نو'), ('s.ghazal.1.6', 'ك ل رکھتے ہیں'),
        ]
        tgt_lines = [
            ('t.ghazal.1.1', 'مہ نہ رکھتے ہیں'), ('t.ghazal.1.2', 'سع صف رکھتے ہیں'),
            ('t.ghazal.1.3', 'قر نو'), ('t.ghazal.1.4', 'صض طظ رکھتے ہیں'),
            ('t.ghazal.1.5', 'غف نو'), ('t.ghazal.1.6', 'ذش ثخ رکھتے ہیں'),
        ]
        src = [_mk_ur(r, t) for r, t in src_lines]
        tgt = [_mk_ur(r, t) for r, t in tgt_lines]
        matches, stats = find_form_matches(src, tgt, {'language': 'ur'})
        assert stats['poem_pairs'] == 1
        assert matches
        assert all(m['form_base'] == 0.5 for m in matches)
        assert max(m['form_score'] for m in matches) == 0.5

    def test_single_stoplisted_radif_differing_qafia_no_match(self):
        """'ast' (Persian 'ist/is', a stoplisted function word) shared by
        chance between two poems with different qafia must NOT match."""
        src_lines = [
            ('s.ghazal.1.1', 'الف جانان است'), ('s.ghazal.1.2', 'ج فرمان است'),
            ('s.ghazal.1.3', 'ه و'), ('s.ghazal.1.4', 'ز زمان است'),
            ('s.ghazal.1.5', 'ط ی'), ('s.ghazal.1.6', 'ك دوران است'),
        ]
        tgt_lines = [
            ('t.ghazal.1.1', 'م گلشن است'), ('t.ghazal.1.2', 'ن روشن است'),
            ('t.ghazal.1.3', 'ه و'), ('t.ghazal.1.4', 'س بهمن است'),
            ('t.ghazal.1.5', 'ط ی'), ('t.ghazal.1.6', 'ك دشمن است'),
        ]
        src = [_mk_fa(r, t) for r, t in src_lines]
        tgt = [_mk_fa(r, t) for r, t in tgt_lines]
        # Confirm the qafia genuinely differs before asserting on the result.
        src_poem = segment_poems(src, 'fa')[0]
        tgt_poem = segment_poems(tgt, 'fa')[0]
        s_radif, s_qafia, _ = poem_signature(src_poem, 'fa')
        t_radif, t_qafia, _ = poem_signature(tgt_poem, 'fa')
        assert s_radif == t_radif == (normalize_persian('است'),)
        assert s_qafia != t_qafia
        matches, stats = find_form_matches(src, tgt, {'language': 'fa'})
        assert matches == []
        assert stats['poem_pairs'] == 0

    def test_radifless_poem_no_match(self):
        lines = [
            ('y.ghazal.1.1', 'الف ب پنجم'), ('y.ghazal.1.2', 'ج د ششم'),
            ('y.ghazal.1.3', 'ه و هفتم'), ('y.ghazal.1.4', 'ز ح هشتم'),
            ('y.ghazal.1.5', 'ط ی نهم'), ('y.ghazal.1.6', 'ك ل دهم'),
        ]
        units = [_mk_fa(r, t) for r, t in lines]
        matches, stats = find_form_matches(units, units, {'language': 'fa'})
        assert matches == []
        assert stats['poem_pairs'] == 0


# ---------------------------------------------------------------------------
# 4. Real-text slices
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason=_TEXTS_MISSING_SKIP)
class TestRealTextSlices:
    def test_hafez_iqbal_shama_radif(self):
        """Hafez diwan lines 882-907 (line-numbered, run heuristic) against
        Iqbal Zabur-e Ajam ghazal 118 (poem-numbered couplet-with-pipe
        layout) must yield form matches with radif 'شما' and score 1.0."""
        hafez_path = os.path.join(TEXTS_FA, 'hafez.diwan.tess')
        iqbal_path = os.path.join(TEXTS_FA, 'iqbal.zabur_e_ajam.tess')
        assert os.path.exists(hafez_path) and os.path.exists(iqbal_path)

        # Generous margin around 882-907 so the run heuristic can find the
        # ghazal's natural boundary rather than being cut off mid-poem.
        hafez_units = _units_from_tess(hafez_path, 'fa', lo=860, hi=920)
        iqbal_units = _units_from_tess(
            iqbal_path, 'fa', ref_prefixes=['iqbal.zabur_e_ajam.118.'])
        assert iqbal_units, "iqbal.zabur_e_ajam ghazal 118 not found in texts/fa"

        matches, stats = find_form_matches(
            hafez_units, iqbal_units, {'language': 'fa'})
        assert matches, "expected form matches between Hafez 882-907 and Iqbal ghazal 118"
        assert all(m['form_base'] == 1.0 for m in matches)
        assert max(m['form_score'] for m in matches) == 1.0
        assert all(m['radif'] == 'شما' for m in matches)

        src_refs = {hafez_units[m['source_idx']]['ref'] for m in matches}
        tgt_refs = {iqbal_units[m['target_idx']]['ref'] for m in matches}
        # The benchmark's own crude boundary was 882-907; with the Ganjoor
        # alignment in place (data/poetics/ganjoor_hafez.diwan.json) the
        # poem is bounded by Ganjoor's record, which may differ by a line.
        assert src_refs <= {f'hafez.diwan.{n}' for n in range(878, 912)}
        assert tgt_refs == {f'iqbal.zabur_e_ajam.118.{n}' for n in range(1, 8)}

    def test_ghalib_mir_chahiye_radif(self):
        """Ghalib (ghalib.diwan_wikisource) ghazals 162 and 220 -- both
        genuinely end in the radif 'چاہیے', confirmed directly against the
        .tess file -- against Mir ghazals with the same radif must yield
        matches.

        DEVIATION FROM SPEC: data/poetics/mir.radif_index.csv (and
        mir_ghalib_shared_radif_javab_candidates.csv) number their Mir
        ghazals against `mir.diwan_rekhta.tess`, a staged Rekhta-edition
        text (research/languages/staging/ur/mir.diwan_rekhta.tess in the
        dev repo) that is NOT present in this workspace's texts/ur/ (only
        mir.kulliyat_wikisource.tess is). Those CSVs' ghazal numbers 172/175
        do not correspond to chahiye-radif ghazals in mir.kulliyat_wikisource
        (its own ghazals 172/175 end in different radifs). Substituted
        mir.kulliyat_wikisource ghazals 136 and 321, independently confirmed
        by grep to end in chahiye, so the test still exercises a real,
        present-in-corpus Ghalib/Mir chahiye pairing.
        """
        ghalib_path = os.path.join(TEXTS_UR, 'ghalib.diwan_wikisource.tess')
        mir_path = os.path.join(TEXTS_UR, 'mir.kulliyat_wikisource.tess')
        assert os.path.exists(ghalib_path) and os.path.exists(mir_path)

        radif_csv = os.path.join(DATA_POETICS, 'mir.radif_index.csv')
        assert os.path.exists(radif_csv), "data/poetics/mir.radif_index.csv missing"
        with open(radif_csv, encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        assert any(row.get('radif', '').strip() == 'چاہیے' for row in rows), (
            "mir.radif_index.csv no longer lists a چاہیے radif -- re-check "
            "the substitution note above")

        ghalib_units = _units_from_tess(
            ghalib_path, 'ur',
            ref_prefixes=['ghalib.diwan_wikisource.ghazal.162.',
                          'ghalib.diwan_wikisource.ghazal.220.'])
        mir_units = _units_from_tess(
            mir_path, 'ur',
            ref_prefixes=['mir.kulliyat_wikisource.ghazal.136.',
                          'mir.kulliyat_wikisource.ghazal.321.'])
        assert ghalib_units and mir_units

        matches, stats = find_form_matches(ghalib_units, mir_units, {'language': 'ur'})
        assert matches, "expected form matches between Ghalib 162/220 and Mir 136/321"
        assert stats['poem_pairs'] == 4  # 2 Ghalib poems x 2 Mir poems
        assert all(m['radif'] == normalize_urdu('چاہیے') for m in matches)


# ---------------------------------------------------------------------------
# 5. Fusion wiring
# ---------------------------------------------------------------------------

class TestFusionWiring:
    def test_form_registered_for_fa_ur_ar_only(self):
        for lang in ('fa', 'ur', 'ar'):
            assert 'form' in get_channels_for_language(lang), lang
        for lang in ('la', 'grc', 'cop', 'he', 'en'):
            assert 'form' not in get_channels_for_language(lang), lang

    def test_form_in_channel_order_after_quotation(self):
        assert 'form' in CHANNEL_ORDER
        assert CHANNEL_ORDER.index('form') == CHANNEL_ORDER.index('quotation') + 1

    def test_form_channel_config_present(self):
        assert 'form' in CHANNEL_CONFIGS
        assert CHANNEL_CONFIGS['form']['match_type'] == 'form'

    def test_form_weight_profiles(self):
        assert get_weight_profile('fa')['form'] == 16.0
        assert get_weight_profile('ur')['form'] == 16.0
        for name, profile in WEIGHT_PROFILES.items():
            assert 'form' in profile, name
            if name == 'persian_ghazal':
                assert profile['form'] == 16.0
            else:
                assert profile['form'] == 0.0, name
        assert 'form' in CHANNEL_WEIGHTS
        assert CHANNEL_WEIGHTS['form'] == 0.0


# ---------------------------------------------------------------------------
# 6. Bypass: form contribution must skip the rarity multiplier
# ---------------------------------------------------------------------------

class TestRarityBypass:
    def test_form_score_bypasses_rarity_multiplier(self):
        result = {
            'source': {'ref': 's.1', 'text': 'x', 'tokens': ['x'],
                       'highlight_indices': [0]},
            'target': {'ref': 't.1', 'text': 'y', 'tokens': ['y'],
                       'highlight_indices': [0]},
            'matched_words': [{'lemma': 'شما', 'source_word': 'شما',
                               'target_word': 'شما', 'frequency': 0, 'idf': 0}],
            'overall_score': 1.0,
            'match_basis': 'form',
        }
        channel_results = {'form': [result]}
        fused = fuse_results(channel_results, language='fa')
        assert len(fused) == 1
        weight = get_weight_profile('fa')['form']
        assert fused[0]['fused_score'] == round(1.0 * weight, 4)


# ---------------------------------------------------------------------------
# 8. Scoring refinements (2026-09-05, after the first benchmark run)
# ---------------------------------------------------------------------------

class TestScoringRefinements:
    def test_opening_line_without_radif_still_signs(self):
        """Ghalib, Wikisource ghazal 3 opens with a line that lacks the radif
        (the matla's first hemistich ends in 'kar', the radif is 'tha').
        The threshold is taken against the lines expected to carry the
        radif (about half in hemistich layout), not against the first
        line's ending."""
        lines = [
            ('g.ghazal.3.1', 'جز قیس اور کوئی نہ آیا بروئے کار'),
            ('g.ghazal.3.2', 'صحرا مگر بہ تنگئ چشم حسود تھا'),
            ('g.ghazal.3.3', 'آشفتگی نے نقش سویدا کیا درست'),
            ('g.ghazal.3.4', 'ظاہر ہوا کہ داغ کا سرمایہ دود تھا'),
            ('g.ghazal.3.5', 'تھا خواب میں خیال کو تجھ سے معاملہ'),
            ('g.ghazal.3.6', 'جب آنکھ کھل گئی نہ زیاں تھا نہ سود تھا'),
            ('g.ghazal.3.7', 'لیتا ہوں مکتب غم دل میں سبق ہنوز'),
            ('g.ghazal.3.8', 'لیکن یہی کہ رفت گیا اور بود تھا'),
        ]
        units = [_mk_ur(r, t) for r, t in lines]
        poems = segment_poems(units, 'ur')
        assert len(poems) == 1
        radif, qafia, idxs = poem_signature(poems[0], 'ur')
        assert radif == ('تھا',)
        assert qafia == 'ود'
        assert idxs == [1, 3, 5, 7]

    def test_shared_signature_is_discounted_by_its_frequency(self):
        """Two source poems and two target poems on the same refrain and
        rhyme: each pairing is discounted to 1/sqrt(2*2) = 0.5, and the
        opening-line pair of each poem pair carries that full discounted
        score."""
        def poem(prefix, n):
            return [
                (f'{prefix}.ghazal.{n}.1', f'{prefix}{n}الف جانان شما'),
                (f'{prefix}.ghazal.{n}.2', f'{prefix}{n}ج فرمان شما'),
                (f'{prefix}.ghazal.{n}.3', f'{prefix}{n}ه و'),
                (f'{prefix}.ghazal.{n}.4', f'{prefix}{n}ز زمان شما'),
                (f'{prefix}.ghazal.{n}.5', f'{prefix}{n}ط ی'),
                (f'{prefix}.ghazal.{n}.6', f'{prefix}{n}ك دوران شما'),
            ]
        src = [_mk_fa(r, t) for r, t in poem('s', 1) + poem('s', 2)]
        tgt = [_mk_fa(r, t) for r, t in poem('t', 1) + poem('t', 2)]
        matches, stats = find_form_matches(src, tgt, {'language': 'fa'})
        assert stats['poem_pairs'] == 4
        assert all(m['form_rarity'] == 0.5 for m in matches)
        assert max(m['form_score'] for m in matches) == 0.5
        openings = [m for m in matches if m['form_score'] == 0.5]
        assert len(openings) == 4


# ---------------------------------------------------------------------------
# 9. Arabic mode: rhyme letter (rawi) only, one qasida per text (2026-09-05)
# ---------------------------------------------------------------------------

TEXTS_AR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'texts', 'ar')


def _units_ar(name, lo=None, hi=None):
    import backend.arabic
    backend.arabic.register()
    from backend.arabic.processor import tokenize_arabic
    units = []
    path = os.path.join(TEXTS_AR, name + '.tess')
    for line in open(path, encoding='utf-8'):
        m = re.match(r'<([^>]+)>\t(.*)', line)
        if not m:
            continue
        ref, text = m.group(1), m.group(2).strip()
        n = int(ref.split('.')[-1])
        if lo is not None and n < lo:
            continue
        if hi is not None and n > hi:
            continue
        toks = tokenize_arabic(text)
        toks = toks[1] if isinstance(toks, tuple) else toks
        units.append({'ref': ref, 'text': text, 'tokens': list(toks), 'lemmas': list(toks)})
    return units


class TestArabicRhymeLetter:
    @pytest.mark.skip(reason=_TEXTS_MISSING_SKIP)
    def test_qasida_signature_is_its_rhyme_letter(self):
        burda = _units_ar('busiri.burda')
        poems = segment_poems(burda, 'ar')
        assert len(poems) == 1 and poems[0].key == 'busiri.burda'
        radif, qafia, idxs = poem_signature(poems[0], 'ar')
        assert radif == () and qafia == 'م'
        assert len(idxs) >= 0.9 * len(burda)

    @pytest.mark.skip(reason=_TEXTS_MISSING_SKIP)
    def test_quran_sura_is_not_a_poem(self):
        assert segment_poems(_units_ar('quran.al_waqia'), 'ar') == []

    @pytest.mark.skip(reason=_TEXTS_MISSING_SKIP)
    def test_shared_rhyme_letter_matches_at_half_and_different_letter_does_not(self):
        burda = _units_ar('busiri.burda', hi=20)
        shawqi = _units_ar('shawqi.nahj_al_burda', hi=20)
        kaab = _units_ar('kaab.banat_suad', hi=20)
        m, st = find_form_matches(burda, shawqi, {'language': 'ar'})
        assert st['poem_pairs'] == 1 and m
        assert all(x['form_base'] == 0.5 and x['qafia'] == 'م' for x in m)
        assert max(x['form_score'] for x in m) == 0.5
        m2, st2 = find_form_matches(burda, kaab, {'language': 'ar'})
        assert st2['poem_pairs'] == 0 and m2 == []

    def test_persian_rhyme_only_still_no_match(self):
        """The Arabic rhyme-only rule must not leak into fa/ur."""
        lines = [('y.ghazal.1.%d' % i, 'الف ب %sان' % c) for i, c in enumerate('ابجدهو', 1)]
        src = [_mk_fa(r, t) for r, t in lines]
        m, st = find_form_matches(src, src, {'language': 'fa'})
        assert st['poem_pairs'] == 0 and m == []

    def test_arabic_registered_for_form(self):
        assert 'form' in get_channels_for_language('ar')


# ---------------------------------------------------------------------------
# 10. Ganjoor poem boundaries and meter (2026-09-05)
# ---------------------------------------------------------------------------

class TestGanjoorBoundariesAndMeter:
    def _poem_lines(self, prefix, start, radif, n=6):
        return [(f'{prefix}.{start + i}', f'{prefix}{i} الف {"" if i % 2 else "ب "}{"جانان" if i % 2 == 0 else "خ"} {radif}' if False else f'{prefix}{i} کلمه {"دوران" if i % 2 == 0 or i == 1 else "ز"} {radif}') for i in range(n)]

    def test_ganjoor_records_bound_poems_and_carry_meter(self, monkeypatch, tmp_path):
        import json
        import backend.poetics as P
        monkeypatch.setattr(P, '_GANJOOR_DIR', str(tmp_path))
        P._GANJOOR_CACHE.clear()
        # Two Ganjoor poems on the same refrain and rhyme, different meters.
        lines = [('x.diwan.%d' % i, 'کلمه %s شما' % w) for i, w in enumerate(['جانان', 'فرمان', 'زمان', 'دوران', 'پنهان', 'ایمان'], 1)]
        lines += [('x.diwan.%d' % i, 'واژه %s شما' % w) for i, w in zip(range(7, 13), ['خیابان', 'کافرستان', 'بیابان', 'بدخشان', 'پنهان', 'دوران'])]
        json.dump([{'ganjoor_id': 1, 'first_ref': 'x.diwan.1', 'last_ref': 'x.diwan.6', 'contiguous': True,
                    'rhythm': 'فاعلاتن فاعلاتن فاعلاتن فاعلن (رمل مثمن محذوف)'},
                   {'ganjoor_id': 2, 'first_ref': 'x.diwan.7', 'last_ref': 'x.diwan.12', 'contiguous': True,
                    'rhythm': 'مفاعیلن مفاعیلن مفاعیلن مفاعیلن (هزج مثمن سالم)'}],
                  open(tmp_path / 'ganjoor_x.diwan.json', 'w', encoding='utf-8'), ensure_ascii=False)
        units = [_mk_fa(r, t) for r, t in lines]
        poems = segment_poems(units, 'fa')
        assert [p.unit_idxs for p in poems] == [list(range(0, 6)), list(range(6, 12))]
        assert [p.meter for p in poems] == ['رمل مثمن محذوف', 'هزج مثمن سالم']
        # Same refrain and rhyme but different meters: discounted to 0.3.
        matches, stats = find_form_matches(units[:6], units[6:], {'language': 'fa'})
        assert stats['poem_pairs'] == 1 and matches
        assert abs(max(m['form_score'] for m in matches) - 0.3) < 1e-6
        assert all(m['meter'] is None for m in matches)
        P._GANJOOR_CACHE.clear()

    def test_meter_family(self):
        from backend.poetics import meter_family
        assert meter_family('فاعلاتن فاعلاتن فاعلاتن فاعلن (رمل مثمن محذوف)') == 'رمل مثمن محذوف'
        assert meter_family(None) is None


@pytest.mark.skip(reason=_TEXTS_MISSING_SKIP)
class TestArabicMeter:
    def test_same_rhyme_different_meter_is_excluded(self, monkeypatch):
        import backend.poetics as P
        P._ARABIC_METERS_CACHE.clear()
        P._ARABIC_METERS_CACHE.update({'busiri.burda': {'meter': 'البسيط'}, 'shawqi.nahj_al_burda': {'meter': 'البسيط'},
                                       'kaab.banat_suad': {'meter': 'البسيط'}, 'imru_al_qais.muallaqa': {'meter': 'الطويل'}})
        burda = _units_ar('busiri.burda', hi=20); shawqi = _units_ar('shawqi.nahj_al_burda', hi=20)
        kaab = _units_ar('kaab.banat_suad', hi=20); imru = _units_ar('imru_al_qais.muallaqa', hi=20)
        m, st = find_form_matches(burda, shawqi, {'language': 'ar'})
        assert st['poem_pairs'] == 1 and max(x['form_score'] for x in m) == 0.5 and all(x['meter'] == 'البسيط' for x in m)
        m2, st2 = find_form_matches(kaab, imru, {'language': 'ar'})
        # Since 2026-09-06 (whole diwans on both sides) a labelled meter
        # mismatch excludes the pair instead of discounting it.
        assert st2['poem_pairs'] == 0 and m2 == []
        P._ARABIC_METERS_CACHE.clear()


class TestArabicDiwanSegmentation:
    """A poem-numbered Arabic diwan (stem.P.N, 2026-09-06 Wikisource import)
    is segmented on the poem number; flat refs stay one poem per file; the
    hadith collections are prose and yield no poems."""

    def _units(self, stem, poems):
        units = []
        for p, lines in enumerate(poems, 1):
            for n, text in enumerate(lines, 1):
                ref = f'{stem}.{p}.{n}' if len(poems) > 1 else f'{stem}.{n}'
                toks = text.split()
                units.append({'ref': ref, 'text': text, 'tokens': toks, 'lemmas': toks})
        return units

    def test_poem_numbered_refs_split(self):
        # poems shorter than _HEURISTIC_MIN_POEM_LINES (6) are dropped
        poems = [['قفا نبك من ذكرى حبيب ومنزل', 'بسقط اللوى بين الدخول فحومل', 'فتوضح فالمقراة لم يعف رسمها', 'لما نسجتها من جنوب وشمأل', 'ترى بعر الآرام في عرصاتها', 'وقيعانها كأنه حب فلفل'],
                 ['ألا عم صباحا أيها الطلل البالي', 'وهل يعمن من كان في العصر الخالي', 'وهل يعمن إلا سعيد مخلد', 'قليل الهموم ما يبيت بأوجال', 'وهل يعمن من كان أحدث عهده', 'ثلاثين شهرا في ثلاثة أحوال']]
        found = segment_poems(self._units('x.diwan_wikisource', poems), 'ar')
        assert [p.key for p in found] == ['x.diwan_wikisource.1', 'x.diwan_wikisource.2']
        assert [len(p.units) for p in found] == [6, 6]

    def test_flat_refs_one_poem(self):
        poems = [['قفا نبك من ذكرى حبيب ومنزل', 'بسقط اللوى بين الدخول فحومل', 'فتوضح فالمقراة لم يعف رسمها', 'لما نسجتها من جنوب وشمأل', 'ترى بعر الآرام في عرصاتها', 'وقيعانها كأنه حب فلفل']]
        found = segment_poems(self._units('x.muallaqa', poems), 'ar')
        assert len(found) == 1 and found[0].key == 'x.muallaqa'

    def test_hadith_excluded(self):
        poems = [['إنما الأعمال بالنيات وإنما لكل امرئ ما نوى'] * 6]
        assert segment_poems(self._units('nawawi.arbain', poems), 'ar') == []


# ---------------------------------------------------------------------------
# 6. One result per poem pair, and corpus-wide rarity (2026-10-06)
# ---------------------------------------------------------------------------

class TestOnePerPoemPair:
    SRC = [
        ('s.ghazal.1.1', 'الف جانان شما'), ('s.ghazal.1.2', 'ج فرمان شما'),
        ('s.ghazal.1.3', 'ه و'), ('s.ghazal.1.4', 'ز زمان شما'),
        ('s.ghazal.1.5', 'ط ی'), ('s.ghazal.1.6', 'ك دوران شما'),
    ]
    TGT = [
        ('t.ghazal.1.1', 'م خیابان شما'), ('t.ghazal.1.2', 'ن کافرستان شما'),
        ('t.ghazal.1.3', 'س ع'), ('t.ghazal.1.4', 'ف بیابان شما'),
        ('t.ghazal.1.5', 'ق ر'), ('t.ghazal.1.6', 'ص ض بدخشان شما'),
    ]

    def _run(self, settings=None):
        src = [_mk_fa(r, t) for r, t in self.SRC]
        tgt = [_mk_fa(r, t) for r, t in self.TGT]
        return find_form_matches(src, tgt, {'language': 'fa', **(settings or {})})

    def test_one_match_per_poem_pair_listing_the_refrain_lines(self):
        matches, stats = self._run()
        assert stats['poem_pairs'] == 1
        assert len(matches) == 1
        m = matches[0]
        # The opening-line pair carries the match ...
        assert m['source_idx'] == 0 and m['target_idx'] == 0
        assert m['form_score'] == 1.0
        # ... and the poems' other refrain lines are listed on it.
        assert m['source_lines'] == ['s.ghazal.1.1', 's.ghazal.1.2', 's.ghazal.1.4', 's.ghazal.1.6']
        assert m['target_lines'] == ['t.ghazal.1.1', 't.ghazal.1.2', 't.ghazal.1.4', 't.ghazal.1.6']
        assert m['form_corpus_poems'] is None and m['form_corpus_factor'] == 1.0

    def test_corpus_form_factor_values(self):
        from backend.poetics import corpus_form_factor
        assert corpus_form_factor(None) == 1.0
        assert corpus_form_factor(1) == 1.0
        assert corpus_form_factor(2) == 1.0
        assert abs(corpus_form_factor(8) - 0.5) < 1e-9
        assert abs(corpus_form_factor(32) - 0.25) < 1e-9
        assert abs(corpus_form_factor(200) - 0.1) < 1e-9

    def test_corpus_table_discounts_a_common_form(self, monkeypatch):
        from backend import poetics
        table = {'signatures': {'شما|ان': 8}, 'radifs': {'شما': 20}, 'total_poems': 100}
        monkeypatch.setattr(poetics, '_FORM_SIG_CACHE', {'fa': table})
        matches, _ = self._run()
        assert len(matches) == 1
        assert matches[0]['form_corpus_poems'] == 8
        assert abs(matches[0]['form_corpus_factor'] - 0.5) < 1e-9
        assert abs(matches[0]['form_score'] - 0.5) < 1e-9

    def test_corpus_rarity_can_be_switched_off(self, monkeypatch):
        from backend import poetics
        monkeypatch.setattr(poetics, '_FORM_SIG_CACHE', {'fa': {'signatures': {'شما|ان': 8}, 'radifs': {}, 'total_poems': 1}})
        matches, _ = self._run({'form_corpus_rarity': False})
        assert matches[0]['form_score'] == 1.0 and matches[0]['form_corpus_poems'] is None
