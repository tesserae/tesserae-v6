"""Translation files with HTML entities are decoded when loaded (owner's
review 2026-10-10: "C&aelig;sar" in the Reader's Translation tab)."""
from backend import translations


def test_entities_decoded_in_every_string():
    data = {'units': [{'ref': '1.1', 'text': 'C&aelig;sar &mdash; Augustus&mdash;more'},
                      {'ref': '1.2', 'text': 'plain text', 'notes': ['&OElig;dipus']}],
            'source': 'LacusCurtius &amp; co.'}
    out = translations._decode_entities(data)
    assert out['units'][0]['text'] == 'C\u00e6sar \u2014 Augustus\u2014more'
    assert out['units'][1]['text'] == 'plain text'
    assert out['units'][1]['notes'] == ['\u0152dipus']
    assert out['source'] == 'LacusCurtius & co.'


def test_a_lone_ampersand_is_left_alone():
    assert translations._decode_entities('Church & Brodribb') == 'Church & Brodribb'
