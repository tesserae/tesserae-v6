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


# --- headings must stay attached to their OWN text -------------------------
#
# Getting this wrong manufactured a false statement and fed it to the model,
# which is worse than giving it no context at all. It went wrong twice, in two
# different ways, so both are pinned here.

FIXTURE = '''
  <h4 className="x">Theme Search <span className="y">(its own tab)</span></h4>
  <p className="z">
    Describe what happens in a passage, in your own words, and find passages
    that match the description rather than the wording across the whole corpus.
  </p>
  <h4 className="x">Read <span className="y">(its own tab)</span></h4>
  <p className="z">
    Read a text with a gutter showing where the rest of the corpus connects to
    each line, by wording and by content, and a panel of those connections.
  </p>
'''


def _chunks_from_fixture(tmp_path):
    p = tmp_path / 'HelpPage.jsx'
    p.write_text(FIXTURE, encoding='utf-8')
    return site_help._extract(str(p))


def test_a_heading_does_not_run_on_into_the_next_section(tmp_path):
    """The first bug: a paragraph's closing '<' swallowed the '<' opening the
    next heading, so 'Theme Search' was glued to the READER's description."""
    for c in _chunks_from_fixture(tmp_path):
        if c.lower().startswith('theme search'):
            assert 'gutter' not in c, c


def test_a_heading_with_a_nested_span_keeps_its_first_word(tmp_path):
    """The second bug: <h4>Read <span>(its own tab)</span></h4> gave 'Read ',
    five characters, under the fragment minimum -- so the heading became
    '(its own tab)' and the word Read was lost."""
    chunks = _chunks_from_fixture(tmp_path)
    reader = [c for c in chunks if 'gutter' in c]
    assert reader, 'the Reader paragraph vanished'
    assert reader[0].startswith('Read'), reader[0]


def test_each_section_keeps_its_own_description(tmp_path):
    chunks = _chunks_from_fixture(tmp_path)
    theme = [c for c in chunks if c.lower().startswith('theme search')]
    assert theme and 'Describe what happens' in theme[0]


def test_the_real_help_page_has_no_mislabelled_reader_section():
    for c in site_help._load():
        if 'gutter' in c:
            assert not c.lower().startswith(('theme search', '(its own tab')), c


# --- the Help page decides what counts as a question about the site --------

def test_a_site_question_is_recognised_without_a_keyword_list():
    """"What is Theme Search?" is not phrased as a how-to, so a keyword list
    missed it and the corpus listing answered "the corpus contains 1826 Latin
    works", then said Theme Search "is not a defined feature within the corpus's
    current interface or documentation" -- confidently, about a tab on the site.
    """
    from backend.assistant.agent import _is_about_the_site
    assert _is_about_the_site('What is Theme Search?')
    assert _is_about_the_site('What is the Reader for?')
    assert _is_about_the_site('How do I export my results?')


def test_a_holdings_question_still_goes_to_the_corpus():
    from backend.assistant.agent import _is_about_the_site
    assert not _is_about_the_site('what do you have by Ovid?')
    assert not _is_about_the_site('how many Latin works are there?')
