"""The guide answers from the Help page, not from a second copy in a prompt.

NC: "Is this thing so dumb that we really have to preprogram every response? It
won't be enough to just feed it the help Page?" Mostly it is enough, and this is
that: the Help page is 44,000 characters describing every feature, kept current
because readers use it. Hand-copying any of it into a prompt would create a
second version to keep in step, and the copy is the one that goes stale.
"""
from backend.assistant import site_help


def test_the_help_page_yields_usable_chunks():
    chunks = site_help._load()
    assert len(chunks) > 50, 'extraction produced almost nothing'
    assert all(len(c) <= site_help.CHUNK_MAX for c in chunks)


def test_jsx_fragments_are_merged_into_paragraphs():
    """JSX splits a sentence across elements, so raw fragments are unreadable
    scraps. Most chunks should be long enough to carry an idea."""
    chunks = site_help._load()
    long_enough = [c for c in chunks if len(c) >= site_help.CHUNK_MIN]
    assert len(long_enough) > len(chunks) * 0.8


def test_a_question_finds_the_section_that_answers_it():
    hits = ' '.join(site_help.relevant('what is theme search?', k=3)).lower()
    assert 'theme search' in hits


def test_export_question_finds_the_export_section():
    hits = ' '.join(site_help.relevant('how do I export my results?', k=3)).lower()
    assert 'export' in hits or 'csv' in hits


def test_an_unrelated_question_matches_nothing_rather_than_anything():
    assert site_help.relevant('qwertyuiop zxcvbnm', k=3) == []


def test_the_prompt_block_names_its_source():
    block = site_help.context_for('what is theme search?')
    assert 'HELP PAGE' in block
    assert 'do not invent' in block


def test_no_block_when_nothing_matches():
    assert site_help.context_for('qwertyuiop zxcvbnm') == ''
