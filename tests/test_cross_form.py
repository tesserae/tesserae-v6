"""Refrain and rhyme across Persian and Urdu (backend/poetics.find_cross_form_matches,
2026-10-07). Ghalib's Urdu ghazal 64 keeps Hafez's refrain "dost" and his -ar rhyme;
a refrain of function words (Urdu hua, "became", spelled like Persian hava, "air")
must not count."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.persian import register as register_fa  # noqa: E402
from backend.urdu import register as register_ur  # noqa: E402
from backend.poetics import find_cross_form_matches  # noqa: E402
from test_form_channel import _mk_fa, _mk_ur  # noqa: E402

register_fa()
register_ur()


def _poem(mk, stem, lines):
    return [mk(f'{stem}.{i + 1}', t) for i, t in enumerate(lines)]


HAFEZ = _poem(_mk_fa, 'hafez.diwan', [
    'آن پیک نامور که رسید از دیار دوست',
    'آورد حرز جان ز خط مشکبار دوست',
    'خوش می‌دهد نشان جلال و جمال یار',
    'خوش می‌کند حکایت عز و وقار دوست',
    'دل دادمش به مژده و خجلت همی‌برم',
    'زین نقد قلب خویش که کردم نثار دوست',
])
GHALIB = _poem(_mk_ur, 'ghalib.diwan.ghazal.64', [
    'آمدِ خط سے ہوا ہے سرد جو بازارِ دوست',
    'دودِ شمعِ کشتہ تھا شاید خطِ رخسارِ دوست',
    'اے دلِ نا عاقبت اندیش ضبطِ شوق کر',
    'کون لا سکتا ہے تابِ جلوۂ دیدارِ دوست',
    'خانہ ویراں سازئ حیرت تماشا کیجیے',
    'صورتِ نقشِ قدم ہوں رفتۂ رفتارِ دوست',
])


def test_hafez_and_ghalib_share_refrain_and_rhyme_across_languages():
    matches, stats = find_cross_form_matches(HAFEZ, GHALIB, 'fa', 'ur',
                                             {'form_corpus_rarity': False})
    assert stats['poem_pairs'] == 1
    m = matches[0]
    assert m['radif'] == 'دوست' and m['form_score'] == 1.0
    assert m['source_lines'][0] == 'hafez.diwan.1'
    assert m['target_lines'][0] == 'ghalib.diwan.ghazal.64.1'


def test_a_refrain_of_function_words_is_not_a_match():
    # Persian lines ending in hava ("air") and Urdu lines ending in hua ("became").
    fa = _poem(_mk_fa, 'saeb.diwan', [
        'که هست داروی بیهوشی شراب هوا',
        'دلم گرفت ز بی‌تابی سحاب هوا',
        'ز باغ آمد و بگذشت با شتاب هوا',
        'نشست بر سر گل همچو آب هوا',
    ])
    ur = _poem(_mk_ur, 'nazeer.kulliyat.80', [
        'دل دیکھ اسے جس گھڑی بے تاب ہوا',
        'جو خواب میں دیکھا تھا وہ خواب ہوا',
        'آنکھوں میں جو آنسو تھا وہ آب ہوا',
        'یہ دل بھی مرا خانہ خراب ہوا',
    ])
    matches, _ = find_cross_form_matches(fa, ur, 'fa', 'ur', {'form_corpus_rarity': False})
    assert matches == []
