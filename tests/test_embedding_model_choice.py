"""One embedding space per channel: the admin builders and the search must read the
model from the same function (English was built with MiniLM, 384 dimensions, while the
search expected SPhilBERTa, 768, and every English cross-language search failed)."""
import inspect
import re

from backend import semantic_similarity
from backend.blueprints import admin


def test_english_uses_the_latin_greek_space():
    assert semantic_similarity.model_name_for('en') == semantic_similarity.model_name_for('la')
    assert semantic_similarity.model_name_for('en') == semantic_similarity.model_name_for('grc')
    assert semantic_similarity.ENGLISH_MODEL == semantic_similarity.model_name_for('en')


def test_admin_builders_do_not_choose_a_model_themselves():
    src = inspect.getsource(admin)
    assert 'all-MiniLM' not in src
    assert len(re.findall(r'model_name_for\(', src)) >= 2
