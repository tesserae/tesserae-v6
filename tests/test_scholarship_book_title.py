from backend.scholarship import _book_title


def test_subtitle_joined():
    assert _book_title({'title': 'Ilias Latina', 'subtitle': 'Text, Interpretation, and Reception'}) == \
        'Ilias Latina: Text, Interpretation, and Reception'


def test_no_subtitle():
    assert _book_title({'title': 'Luke and Vergil'}) == 'Luke and Vergil'
    assert _book_title({}) == ''
