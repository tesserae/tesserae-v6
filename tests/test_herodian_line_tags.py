"""Fixture tests for scripts/corpus/retag_herodian_refs.py.

The script rewrites the 26 CTS-URN line tags in
texts/grc/aelius_herodianus.on_enclitics.tess to the plain form every other
Greek file uses, the same fault the 21 Septuagint files had (#578). These
tests run the script against a small fixture file with the same tag shape,
the pattern used in tests/test_apply_whole_vs_parts_refs.py, rather than the
real corpus file. Covers: a dry run makes no change and reports every
rewrite; an apply rewrites the tags; the text after the tab is byte
identical before and after.
"""
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, 'scripts', 'corpus', 'retag_herodian_refs.py')

FIXTURE_LINES = [
    ('<aelius_herodianus. urn:cts:greekLit:tlg0087.tlg002.1st1K-grc1.1>',
     'Ἐγκλινόμενόν ἐϲτι μόριον λέξιϲ κατὰ τὸ τέλοϲ ὀξυνομένη.'),
    ('<aelius_herodianus. urn:cts:greekLit:tlg0087.tlg002.1st1K-grc1.2>',
     'Διαφέρει δὲ ἐγκλινόμενον ἐγκλιτικοῦ.'),
    ('<aelius_herodianus. urn:cts:greekLit:tlg0087.tlg002.1st1K-grc1.26>',
     'τελευταία ϲτίχοϲ.'),
]


def write_fixture(path):
    with open(path, 'w', encoding='utf-8') as fh:
        for tag, text in FIXTURE_LINES:
            fh.write(f'{tag}\t{text}\n')


def read_texts(path):
    """The text after the tab on each line, in order."""
    out = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if '\t' in line:
                out.append(line.split('\t', 1)[1])
    return out


def run(args, cwd):
    return subprocess.run(
        [sys.executable, SCRIPT] + args,
        cwd=cwd, capture_output=True, text=True,
    )


def test_dry_run_reports_every_change_and_writes_nothing(tmp_path):
    fixture = tmp_path / 'aelius_herodianus.on_enclitics.tess'
    write_fixture(fixture)
    before = fixture.read_bytes()

    result = run(['--path', str(fixture)], cwd=str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert fixture.read_bytes() == before, 'dry run must not touch the file'
    for tag, _text in FIXTURE_LINES:
        expected_locus = tag.rsplit('.', 1)[1].rstrip('>')
        assert f'{tag} -> <aelius_herodianus.on_enclitics {expected_locus}>' in result.stdout
    assert '3 tags to rewrite' in result.stdout


def test_apply_rewrites_tags_to_the_plain_form(tmp_path):
    fixture = tmp_path / 'aelius_herodianus.on_enclitics.tess'
    write_fixture(fixture)

    result = run(['--path', str(fixture), '--apply'], cwd=str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert '3 tags rewritten' in result.stdout

    lines = fixture.read_text(encoding='utf-8').splitlines()
    assert lines[0].split('\t')[0] == '<aelius_herodianus.on_enclitics 1>'
    assert lines[1].split('\t')[0] == '<aelius_herodianus.on_enclitics 2>'
    assert lines[2].split('\t')[0] == '<aelius_herodianus.on_enclitics 26>'
    for line in lines:
        assert 'urn:cts' not in line


def test_text_after_the_tab_is_byte_identical(tmp_path):
    fixture = tmp_path / 'aelius_herodianus.on_enclitics.tess'
    write_fixture(fixture)
    before_texts = read_texts(fixture)

    run(['--path', str(fixture), '--apply'], cwd=str(tmp_path))

    after_texts = read_texts(fixture)
    assert after_texts == before_texts


def test_a_file_with_no_matching_tags_is_left_alone(tmp_path):
    fixture = tmp_path / 'plain.tess'
    fixture.write_text('<some_work.title 1>\talready plain text.\n', encoding='utf-8')
    before = fixture.read_bytes()

    result = run(['--path', str(fixture), '--apply'], cwd=str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert 'nothing to do' in result.stdout
    assert fixture.read_bytes() == before
