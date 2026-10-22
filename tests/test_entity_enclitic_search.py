"""People & Places search: a Latin name copied from a line with its enclitic (Laviniaque) finds the entry."""
from backend import entity_extras as x


def _e(eid, label, forms=(), total=10):
    f = x.ei.fold(label)
    return {'eid': eid, 'id': f'nm:{eid}', 'label': label, 'folded_label': f, 'label_key': f,
            'search_names': [], 'forms': list(forms), 'form_stems': [], 'total': total, 'duplicate': False}


def _cat(*names):
    return {'by_eid': {}, 'names': {n['eid']: n for n in names}}


def _ids(cat, q):
    hits, names = x.rank_entities(cat, q)
    return [h[3]['eid'] for h in hits + names]


def test_without_enclitic():
    assert x.without_enclitic('Laviniaque') == ('lauinia', 'que')
    assert x.without_enclitic('Teucrive') == ('teucri', 'ue')
    assert x.without_enclitic('Lavinia') == (None, None)
    assert x.without_enclitic('neque') == (None, None)


def test_que_is_dropped_and_its_match_comes_first():
    cat = _cat(_e(1, 'Lavinium', forms=['lauinia', 'lauinium']), _e(2, 'Romaque'), _e(3, 'Roma'))
    assert _ids(cat, 'Laviniaque') == [1]
    assert _ids(cat, 'Romaque')[0] == 3


def test_ne_is_dropped_only_when_the_word_matches_nothing():
    cat = _cat(_e(1, 'Daphne'), _e(2, 'Daph'), _e(3, 'Iuno', forms=['iunone', 'iuno']))
    assert _ids(cat, 'Daphne')[0] == 1
    assert _ids(cat, 'Iunone') == [3]
    assert _ids(cat, 'Mycene') == []
