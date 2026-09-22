"""How rare "rare" is has to depend on how big the corpus is.

The rare_word fusion channel called a lemma rare at a document frequency of
100 or fewer, a document being a work with its parts collapsed. That number
was set against Latin, which holds 744 works, so it meant "in at most 13% of
the corpus". English holds 42 works. The commonest English word sits in all
42, so nothing could fail the test and every shared word counted as rare.

That was not only a scoring problem. `backend/fusion.py` already carried a
note about it: 431,000 window matches for Paradise Lost Book 1 against
Hyperion, and 12 GB of memory blown on the whole poem, which is why the
channel got a result cap in September. The cap treated the symptom.

Measured on the live indexes, 2026-09-22:

    language  works  old threshold  0.12 x works
    la          744            100            89
    grc         853            100           102
    cop         180             25            22
    en           42            100             5
    he           39            100             5

One share reproduces every threshold that had been set by hand, which is why
it is the rule rather than a fourth special case.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend.blueprints import hapax  # noqa: E402


@pytest.fixture(autouse=True)
def clear_cache():
    hapax._work_count_cache.clear()
    yield
    hapax._work_count_cache.clear()


def sized(monkeypatch, works):
    monkeypatch.setattr(hapax, 'corpus_work_count', lambda _lang: works)


class TestTheThresholdFollowsTheCorpus:
    @pytest.mark.parametrize('works,expected', [
        (744, 89),    # Latin, against the hand-set 100
        (853, 102),   # Greek, against the hand-set 100
        (180, 22),    # Coptic, against the hand-set 25
        (42, 5),      # English, against a 100 that excluded nothing
        (39, 5),      # Hebrew, the same
    ])
    def test_it_reproduces_the_numbers_that_were_set_by_hand(
            self, monkeypatch, works, expected):
        sized(monkeypatch, works)
        assert hapax.rare_word_threshold('any') == expected

    def test_english_can_now_exclude_its_commonest_word(self, monkeypatch):
        """`the` is in all 42 English works. Under the old fixed 100 it
        counted as rare; it must not now."""
        sized(monkeypatch, 42)
        assert hapax.rare_word_threshold('en') < 42

    def test_latin_barely_moves(self, monkeypatch):
        """Latin is the language the old number was chosen for, so the change
        must not disturb it much."""
        sized(monkeypatch, 744)
        assert abs(hapax.rare_word_threshold('la') - 100) <= 12


class TestItCannotProduceAUselessThreshold:
    def test_a_tiny_corpus_still_admits_a_word_shared_by_two_texts(self, monkeypatch):
        """Rounding down to 1 would mean only a word unique to one work
        counted, which is not what the channel is for."""
        sized(monkeypatch, 3)
        assert hapax.rare_word_threshold('xx') >= 2

    def test_an_unknown_corpus_size_falls_back_to_the_old_number(self, monkeypatch):
        """If the index cannot be read, behave as before rather than treating
        every word as common."""
        sized(monkeypatch, 0)
        assert hapax.rare_word_threshold('xx') == 100

    def test_the_share_is_a_named_constant(self):
        assert hapax.RARE_WORD_SHARE == 0.12


class TestTheChannelUsesIt:
    def test_fusion_no_longer_pins_every_language_to_100(self):
        import backend.fusion as fusion
        src = open(fusion.__file__.replace('.pyc', '.py'), encoding='utf-8').read()
        assert '"rare_word_max_occurrences": 100' not in src
        assert 'rare_word_threshold(language)' in src

    def test_a_caller_can_still_override_it(self):
        """The setting remains, so one search can ask for a different rule."""
        import backend.fusion as fusion
        src = open(fusion.__file__.replace('.pyc', '.py'), encoding='utf-8').read()
        assert 'settings.get("rare_word_max_occurrences", default_max_occ)' in src


class TestTheWorkCount:
    def test_a_real_answer_is_memoized(self, monkeypatch):
        """Counted once per language, not once per search."""
        calls = []

        class Cur:
            def execute(self, *a, **k):
                return self

            def fetchone(self):
                return [744]

        class Conn:
            def cursor(self):
                return Cur()

        def fake_conn(language):
            calls.append(language)
            return Conn()

        monkeypatch.setattr(hapax, 'get_connection', fake_conn)
        assert hapax.corpus_work_count('la') == 744
        assert hapax.corpus_work_count('la') == 744
        assert len(calls) == 1

    def test_an_unreadable_index_counts_zero_rather_than_raising(self, monkeypatch):
        monkeypatch.setattr(hapax, 'get_connection', lambda _l: None)
        assert hapax.corpus_work_count('nope') == 0

    def test_a_failed_read_is_not_remembered(self, monkeypatch):
        """Caching a zero would pin the worker to the fallback threshold for
        its whole life, which for English is the behaviour being fixed. One
        unlucky read at startup must not undo it silently."""
        monkeypatch.setattr(hapax, 'get_connection', lambda _l: None)
        assert hapax.corpus_work_count('en') == 0
        assert 'en' not in hapax._work_count_cache

        class Row(list):
            pass

        class Cur:
            def execute(self, *a, **k):
                return self

            def fetchone(self):
                return Row([42])

        class Conn:
            def cursor(self):
                return Cur()

        monkeypatch.setattr(hapax, 'get_connection', lambda _l: Conn())
        assert hapax.corpus_work_count('en') == 42
        assert hapax._work_count_cache['en'] == 42
