"""Arabic normalization and lemmatization fixes found by the Burda-Qur'an
benchmark (2026-09-05): Uthmani annotation marks must not survive into
tokens, and a token that Stanza splits into clitic + word must keep the
word's lemma, not the clitic's."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.arabic.processor import normalize_arabic  # noqa: E402


def test_uthmani_marks_and_wasla_are_stripped():
    assert normalize_arabic('فَعَمُوا۟') == 'فعموا'
    assert normalize_arabic('وَٱنشَقَّ ٱلْقَمَرُ') == 'وانشق القمر'
    assert normalize_arabic('صَلَوٰةَ') == 'صلوة'
    # Pause signs and small high letters (U+06D6-U+06ED) go too.
    assert normalize_arabic('ذَٰلِكَۚ ٱلْكِتَٰبُۛ') == 'ذلك الكتب'


@pytest.mark.skipif(os.environ.get('TESSERAE_SKIP_STANZA') == '1', reason='Stanza not available')
def test_split_clitic_keeps_the_content_word():
    from backend.arabic.processor import lemmatize_and_tag_arabic
    lemmas, tags = lemmatize_and_tag_arabic(['أقسمت', 'بالقمر', 'المنشق'])
    assert len(lemmas) == 3
    assert 'قمر' in lemmas[1], lemmas
