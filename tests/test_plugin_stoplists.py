"""The curated Persian/Urdu/Arabic stoplists must reach same-language matching.

Before 2026-09-05 these languages fell through to the English list in
Matcher.build_stoplist, so their curated lists had no effect and the most
frequent "matches" were forms of be/say/do. The Latin, Greek, English, Coptic
and Hebrew paths must be untouched by the fix.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.matcher import (  # noqa: E402
    Matcher,
    DEFAULT_LATIN_STOP_WORDS,
    DEFAULT_ENGLISH_STOP_WORDS,
    find_zipf_elbow,
)
from collections import Counter  # noqa: E402

_MATCHER_SKIP = (
    "stage 2b: backend.matcher.Matcher does not yet dispatch fa/ur/ar to the "
    "curated Persian/Urdu/Arabic stoplists in build_stoplist, build_stoplist_manual, "
    "find_matches or find_quotation_matches; they fall through to the English "
    "default stoplist on main. Applied to matcher.py in stage 2b."
)
_HAPAX_SKIP = (
    "stage 2b: backend.blueprints.hapax has no _corpus_token_frequencies hook; "
    "the plugin-language (fa/ur/ar) rare-word rarity path is added to hapax.py "
    "in stage 2b."
)


def _units(lines):
    return [{'ref': f'x.{i}', 'tokens': l.split(), 'lemmas': l.split()} for i, l in enumerate(lines)]


def test_persian_stoplist_uses_curated_list():
    from backend.persian.stopwords import PERSIAN_STOP_WORDS
    m = Matcher()
    src = _units(['خيز و در كاسه زر اب طربناك انداخت'] * 3)
    tgt = _units(['ساقيا بر جگرم شعلہ نمناك انداز دگر اشوب قيامت بہ كف خاك انداخت'] * 3)
    sl = m.build_stoplist(src, tgt, 'source_target', 'fa')
    assert PERSIAN_STOP_WORDS <= sl
    assert 'و' in sl and 'در' in sl
    # A content word that carries the radif must survive.
    assert 'انداخت' not in sl and 'خاك' not in sl
    # No English words leak into a Persian stoplist.
    assert not (sl & DEFAULT_ENGLISH_STOP_WORDS)


def test_persian_small_pair_gets_no_zipf_entries():
    from backend.persian.stopwords import PERSIAN_STOP_WORDS
    m = Matcher()
    src = _units(['خاك انداخت'] * 50)
    tgt = _units(['خاك انداخت'] * 50)
    sl = m.build_stoplist(src, tgt, 'source_target', 'fa')
    assert sl == PERSIAN_STOP_WORDS


def test_urdu_and_arabic_use_their_curated_lists():
    from backend.urdu.stopwords import URDU_STOP_WORDS
    from backend.arabic.stopwords import ARABIC_STOP_WORDS
    m = Matcher()
    units = _units(['a b c'] * 5)
    assert URDU_STOP_WORDS <= m.build_stoplist(units, units, 'source_target', 'ur')
    assert ARABIC_STOP_WORDS <= m.build_stoplist(units, units, 'source_target', 'ar')
    assert m.build_stoplist_manual(units, 5, 'fa') <= (
        set(list(__import__('backend.persian.stopwords', fromlist=['PERSIAN_STOP_WORDS']).PERSIAN_STOP_WORDS)[:5])
        | {'a', 'b', 'c'})


def test_plugin_stoplists_are_normalized_like_the_index():
    """Every entry must already be in the lemma stream's normalized form."""
    from backend.persian.stopwords import PERSIAN_STOP_WORDS
    from backend.arabic.stopwords import ARABIC_STOP_WORDS
    from backend.urdu.stopwords import URDU_STOP_WORDS
    from backend.persian.processor import normalize_persian
    from backend.arabic.processor import normalize_arabic
    from backend.urdu.processor import normalize_urdu
    assert all(normalize_persian(w) == w for w in PERSIAN_STOP_WORDS)
    assert all(normalize_arabic(w) == w for w in ARABIC_STOP_WORDS)
    assert all(normalize_urdu(w) == w for w in URDU_STOP_WORDS)


def test_arabic_stoplist_covers_clitic_forms():
    from backend.arabic.stopwords import ARABIC_STOP_WORDS
    from backend.arabic.processor import normalize_arabic
    for form in ('ولا', 'فما', 'كما', 'لهم', 'وفي', 'عنك', 'علي', 'الي', 'حتي', 'فلا', 'ولي', 'منهم'):
        assert normalize_arabic(form) in ARABIC_STOP_WORDS, form
    # Content words stay out.
    for form in ('لؤلؤ', 'قوس', 'اسد', 'وشاة'):
        assert normalize_arabic(form) not in ARABIC_STOP_WORDS, form


def test_fusion_path_applies_curated_list_for_plugin_languages():
    """Fusion calls find_matches with stoplist_size -1 (no automatic list);
    the curated list must still be merged for fa/ur/ar, and Latin must still
    get no stoplist on that path."""
    from backend.persian.stopwords import PERSIAN_STOP_WORDS
    m = Matcher()
    fa_src = _units(['همان بود است كه قدر'])
    fa_tgt = _units(['همان بود است كه قدر'])
    res = m.find_matches(fa_src, fa_tgt, {'language': 'fa', 'match_type': 'lemma', 'min_matches': 1, 'stoplist_size': -1})[0]
    matched = {w for r in res for w in r['matched_lemmas']}
    assert 'قدر' in matched
    assert not (matched & PERSIAN_STOP_WORDS)
    la_src = _units(['arma uir cano et in'])
    la_tgt = _units(['arma uir cano et in'])
    res = m.find_matches(la_src, la_tgt, {'language': 'la', 'match_type': 'lemma', 'min_matches': 1, 'stoplist_size': -1})[0]
    assert {'arma', 'uir', 'cano'} <= {w for r in res for w in r['matched_lemmas']}


def test_quotation_runs_of_only_stopwords_dropped_for_plugin_languages():
    m = Matcher()
    fa = _units(['همان بود است كه'])
    res = m.find_quotation_matches(fa, fa, {'language': 'fa'})[0]
    assert res == []
    fa2 = _units(['همان بود است كه قدر دانم'])
    res = m.find_quotation_matches(fa2, fa2, {'language': 'fa'})[0]
    assert res and res[0]['run_length'] >= 3
    la = _units(['et in ad'] * 1)
    res = m.find_quotation_matches(la, la, {'language': 'la'})[0]
    assert res and res[0]['run_length'] == 3


def test_latin_stoplist_path_unchanged():
    """Latin must be exactly Zipf-elbow entries plus the default Latin list."""
    m = Matcher()
    src = _units(['arma uir cano troia qui primus ab os'] * 30 + ['sum et in ad'] * 300)
    tgt = _units(['ille terra ad sum'] * 200)
    sl = m.build_stoplist(src, tgt, 'source_target', 'la')
    freq = Counter(l for u in src + tgt for l in u['lemmas'])
    expected = find_zipf_elbow(freq, min_stopwords=10, max_stopwords=50) | DEFAULT_LATIN_STOP_WORDS
    assert sl == expected
    from backend.persian.stopwords import PERSIAN_STOP_WORDS
    assert not (sl & PERSIAN_STOP_WORDS)


def test_english_and_unknown_languages_unchanged():
    m = Matcher()
    units = _units(['the quick brown fox'] * 5)
    sl_en = m.build_stoplist(units, units, 'source_target', 'en')
    sl_unknown = m.build_stoplist(units, units, 'source_target', 'xx')
    assert DEFAULT_ENGLISH_STOP_WORDS <= sl_en
    assert DEFAULT_ENGLISH_STOP_WORDS <= sl_unknown


def test_rare_word_rarity_is_corpus_frequency_for_plugin_languages(monkeypatch):
    """fa/ur/ar: a lemma is rare when its corpus token count is small, not
    when it appears in few texts; the curated stoplist is applied; Latin
    keeps the document-frequency path."""
    import backend.blueprints.hapax as H
    monkeypatch.setattr(H, '_corpus_token_frequencies', lambda lemmas, lang: {l: (3 if l == 'اردشير' else 5000) for l in lemmas})
    calls = []
    monkeypatch.setattr(H, 'get_document_frequencies_batch', lambda lemmas, lang: calls.append(lang) or {l: 1 for l in lemmas})
    src = [{'lemmas': ['اردشير', 'گفت', 'شاه']}]
    tgt = [{'lemmas': ['اردشير', 'گفت', 'شاه']}]
    m = H.find_rare_word_matches_direct(src, tgt, language='fa', max_occurrences=50)
    assert m and m[0]['matched_lemmas'] == ['اردشير']
    assert calls == []
    m = H.find_rare_word_matches_direct([{'lemmas': ['arma', 'uir']}], [{'lemmas': ['arma', 'uir']}], language='la', max_occurrences=50)
    assert calls == ['la'] and m


def test_standalone_punctuation_marks_are_stopwords():
    """The fa/ur tokenizers keep Arabic comma, question mark, semicolon and
    full stop as standalone tokens (index counts 2026-09-05: fa 825 commas,
    ur 1,361). Until the tokenizer excludes them they must not match."""
    from backend.persian.stopwords import PERSIAN_STOP_WORDS
    from backend.urdu.stopwords import URDU_STOP_WORDS
    from backend.arabic.stopwords import ARABIC_STOP_WORDS
    for mark in ('\u060c', '\u061f', '\u061b', '\u06d4'):
        assert mark in PERSIAN_STOP_WORDS and mark in URDU_STOP_WORDS and mark in ARABIC_STOP_WORDS


def test_curated_stoplists_endpoint_shows_persian_and_urdu_when_registered():
    """The Help page's stoplist cards come from get_curated_stoplists; Persian
    and Urdu were registered for matching but never listed there (2026-10-07).
    The displayed words are letters only, in the spelling the lists were typed."""
    from backend import fusion
    from backend.matcher import get_curated_stoplists
    from backend.persian import register as reg_fa
    from backend.urdu import register as reg_ur
    reg_fa(); reg_ur()
    out = get_curated_stoplists()
    for code, label in (('fa', 'Persian'), ('ur', 'Urdu')):
        assert code in out, code
        entry = out[code]
        assert entry['label'] == label and entry['dir'] == 'rtl'
        assert entry['count'] >= 60
        assert all(any(ch.isalpha() for ch in w) for w in entry['display'])
    assert 'که' in out['fa']['display']          # typed with Persian kaf, shown so
