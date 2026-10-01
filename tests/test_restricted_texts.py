"""The guardrail that keeps a licence-bound text out of the public repository.

A text held under an indexing-only licence (the first is from the Packard
Humanities Institute) lives on the production server under texts/<lang>/ like
any other text, but must never reach this repository, a public download, or a
release bundle. Three things have to stay true for that to hold:

1. backend/restricted_texts.py answers `is_restricted` correctly for every
   form a caller holds a text's name in (bare id, filename, book part,
   language-prefixed path).
2. scripts/corpus/restricted_texts_gitignore.py turns a registry entry into
   an actual ignore rule that `git check-ignore` honours.
3. The live registry and the live repository agree right now: nothing it
   names is tracked.

(1) and (2) are tested against a throwaway fixture registry and a throwaway
git repository, because the real registry is empty (no PHI text exists yet)
and this guarantee has to hold before the first one ever arrives. (3) is
tested against the real repository and real registry, which is a vacuous pass
today and a real regression guard from the day an entry is added.

A GIT HOOK CHECK TOO? The repository's pre-commit hook
(/home/ncoffee/tesserae-v6-dev/.git/hooks/pre-commit) is NOT itself tracked in
git -- hooks live outside the repository on this machine, so there is nothing
under .githooks/ to extend. The mechanical check instead lives only here, run
in CI on every push, which is the enforcement point this repository actually
has control over.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, 'scripts', 'corpus'))

import backend.restricted_texts as restricted_texts  # noqa: E402
import restricted_texts_gitignore as gitignore_gen  # noqa: E402


# ---------------------------------------------------------------------------
# A fixture repository: its own git init, its own registry, its own texts/.
# Isolated from the real one so the test can exercise a non-empty registry
# without the real registry ever needing a fake entry.
# ---------------------------------------------------------------------------
@pytest.fixture
def fixture_repo(tmp_path, monkeypatch):
    root = tmp_path / 'repo'
    root.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.invalid'], cwd=root, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=root, check=True)

    (root / 'texts' / 'la').mkdir(parents=True)
    # The restricted work: a whole-file stand-in plus one book part, the two
    # shapes a multi-file work takes on disk.
    (root / 'texts' / 'la' / 'heldwork.history.tess').write_text('<line> text </line>\n')
    (root / 'texts' / 'la' / 'heldwork.history.part.2.tess').write_text('<line> text </line>\n')
    # An ordinary text, to prove the rule is specific rather than blanket.
    (root / 'texts' / 'la' / 'ordinary.poem.tess').write_text('<line> text </line>\n')

    registry = {
        '_comment': 'fixture',
        'texts': {
            'heldwork.history': {
                'holder': 'Test Licence Holder',
                'credit': 'Source: Test Licence Holder (example.invalid)',
                'license': 'indexing and search only; no redistribution',
                'added': '2026-10-01',
                'ends': None,
            }
        },
    }
    data_dir = root / 'data'
    data_dir.mkdir()
    (data_dir / 'restricted_texts.json').write_text(json.dumps(registry))

    gitignore_path = root / '.gitignore'
    gitignore_path.write_text(
        'texts/*\n!texts/la/\n'
        f'{gitignore_gen.BEGIN}\n{gitignore_gen.END}\n'
    )

    # Point the module under test at the fixture registry instead of the real
    # one, and reset its mtime cache so it actually re-reads.
    monkeypatch.setattr(restricted_texts, 'REGISTRY_PATH', data_dir / 'restricted_texts.json')
    restricted_texts._cache['mtime'] = None
    restricted_texts._cache['texts'] = {}
    yield root
    restricted_texts._cache['mtime'] = None
    restricted_texts._cache['texts'] = {}


def git_check_ignore(root, path):
    """True if git, run inside `root`, would ignore `path`."""
    result = subprocess.run(
        ['git', 'check-ignore', '-q', path], cwd=root,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0


# ---------------------------------------------------------------------------
# The module's lookups
# ---------------------------------------------------------------------------
class TestLookups:
    def test_bare_id(self, fixture_repo):
        assert restricted_texts.is_restricted('heldwork.history')

    def test_filename(self, fixture_repo):
        assert restricted_texts.is_restricted('heldwork.history.tess')

    def test_book_part(self, fixture_repo):
        assert restricted_texts.is_restricted('heldwork.history.part.2.tess')
        assert restricted_texts.is_restricted('heldwork.history.part.2')

    def test_language_prefixed(self, fixture_repo):
        assert restricted_texts.is_restricted('la/heldwork.history.tess')
        assert restricted_texts.is_restricted('la/heldwork.history.part.2.tess')

    def test_unrestricted_text_is_not_flagged(self, fixture_repo):
        assert not restricted_texts.is_restricted('ordinary.poem.tess')
        assert not restricted_texts.is_restricted('ordinary.poem')

    def test_credit_for(self, fixture_repo):
        assert restricted_texts.credit_for('heldwork.history.part.2.tess') == (
            'Source: Test Licence Holder (example.invalid)')
        assert restricted_texts.credit_for('ordinary.poem.tess') is None

    def test_license_for(self, fixture_repo):
        assert restricted_texts.license_for('heldwork.history') == (
            'indexing and search only; no redistribution')

    def test_filenames_lists_whole_file_and_part(self, fixture_repo):
        names = restricted_texts.filenames('la', texts_root=str(fixture_repo / 'texts'))
        assert names == ['heldwork.history.part.2.tess', 'heldwork.history.tess']

    def test_filenames_empty_registry_returns_nothing(self, tmp_path, monkeypatch):
        empty = tmp_path / 'empty_registry.json'
        empty.write_text(json.dumps({'texts': {}}))
        monkeypatch.setattr(restricted_texts, 'REGISTRY_PATH', empty)
        restricted_texts._cache['mtime'] = None
        assert restricted_texts.filenames('la', texts_root=str(tmp_path)) == []
        restricted_texts._cache['mtime'] = None
        restricted_texts._cache['texts'] = {}

    def test_missing_registry_file_is_not_an_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(restricted_texts, 'REGISTRY_PATH', tmp_path / 'missing.json')
        restricted_texts._cache['mtime'] = None
        assert restricted_texts.load() == {}
        assert not restricted_texts.is_restricted('anything.tess')
        restricted_texts._cache['mtime'] = None
        restricted_texts._cache['texts'] = {}


# ---------------------------------------------------------------------------
# The .gitignore generator actually produces rules git honours
# ---------------------------------------------------------------------------
class TestGitignoreGeneration:
    def test_generated_block_ignores_restricted_files_only(self, fixture_repo, monkeypatch):
        monkeypatch.setattr(gitignore_gen, 'load', restricted_texts.load)
        lines = gitignore_gen.build_lines(str(fixture_repo))
        gitignore_gen.write_block(str(fixture_repo / '.gitignore'), lines)

        assert git_check_ignore(fixture_repo, 'texts/la/heldwork.history.tess')
        assert git_check_ignore(fixture_repo, 'texts/la/heldwork.history.part.2.tess')
        assert not git_check_ignore(fixture_repo, 'texts/la/ordinary.poem.tess')

    def test_every_registry_entry_gets_a_matching_rule(self, fixture_repo, monkeypatch):
        monkeypatch.setattr(gitignore_gen, 'load', restricted_texts.load)
        lines = gitignore_gen.build_lines(str(fixture_repo))
        gitignore_gen.write_block(str(fixture_repo / '.gitignore'), lines)

        for text_id in restricted_texts.load():
            # Both shapes a registered work can take on disk.
            assert git_check_ignore(fixture_repo, f'texts/la/{text_id}.tess'), (
                f'{text_id}: whole-file path is not ignored')
            assert git_check_ignore(fixture_repo, f'texts/la/{text_id}.part.2.tess'), (
                f'{text_id}: book-part path is not ignored')

    def test_restricted_file_is_never_tracked_even_after_add_all(self, fixture_repo, monkeypatch):
        monkeypatch.setattr(gitignore_gen, 'load', restricted_texts.load)
        lines = gitignore_gen.build_lines(str(fixture_repo))
        gitignore_gen.write_block(str(fixture_repo / '.gitignore'), lines)

        subprocess.run(['git', 'add', '-A'], cwd=fixture_repo, check=True)
        tracked = subprocess.run(
            ['git', 'ls-files'], cwd=fixture_repo, check=True,
            capture_output=True, text=True).stdout.splitlines()

        assert 'texts/la/heldwork.history.tess' not in tracked
        assert 'texts/la/heldwork.history.part.2.tess' not in tracked
        assert 'texts/la/ordinary.poem.tess' in tracked
        assert 'data/restricted_texts.json' in tracked

    def test_missing_markers_refuses_rather_than_guessing(self, tmp_path):
        bad_gitignore = tmp_path / '.gitignore'
        bad_gitignore.write_text('texts/*\n')
        with pytest.raises(SystemExit):
            gitignore_gen.write_block(str(bad_gitignore), ['texts/la/x.tess'])


# ---------------------------------------------------------------------------
# The real repository, right now: vacuous today, a real guard from the first
# entry on. Run against origin/main (never the working tree) for the ignore
# check, matching claim_check.py's own rule that a stale worktree is not
# trustworthy evidence -- the committed .gitignore is what a fresh clone sees.
# ---------------------------------------------------------------------------
class TestLiveRegistryAgreesWithLiveRepo:
    def test_every_live_entry_is_ignored_by_origin_mains_gitignore(self, tmp_path):
        """Resolves the ignore rule against origin/main's .gitignore, not the
        working tree's, per claim_check.py's rule: a stale worktree is the
        failure mode this whole guardrail exists to prevent.

        `git check-ignore` only ever reads .gitignore from a real filesystem,
        not from a ref directly, so origin/main's copy is checked out into a
        scratch directory and asked there.
        """
        registry = restricted_texts.load()
        if not registry:
            pytest.skip('registry is empty: nothing to check yet')
        show = subprocess.run(
            ['git', 'show', 'origin/main:.gitignore'],
            cwd=REPO_ROOT, capture_output=True, text=True)
        if show.returncode != 0:
            pytest.skip('origin/main not available in this checkout')
        scratch = tmp_path / 'origin_main_check'
        scratch.mkdir()
        subprocess.run(['git', 'init', '-q'], cwd=scratch, check=True)
        (scratch / '.gitignore').write_text(show.stdout)
        for text_id in registry:
            for lang_dir in os.listdir(os.path.join(REPO_ROOT, 'texts')):
                (scratch / 'texts' / lang_dir).mkdir(parents=True, exist_ok=True)
                candidate = f'texts/{lang_dir}/{text_id}.tess'
                if not git_check_ignore(scratch, candidate):
                    continue  # this is not the text's language; try the others
                break
            else:
                pytest.fail(
                    f'{text_id}: no language directory ignores it under '
                    "origin/main's .gitignore")

    def test_no_live_registry_entry_is_tracked_in_origin_main(self):
        registry = restricted_texts.load()
        if not registry:
            pytest.skip('registry is empty: nothing to check yet')
        tracked = subprocess.run(
            ['git', 'ls-tree', '-r', '--name-only', 'origin/main'],
            cwd=REPO_ROOT, capture_output=True, text=True)
        if tracked.returncode != 0:
            pytest.skip('origin/main not available in this checkout')
        tracked_files = set(tracked.stdout.splitlines())
        for text_id in registry:
            for path in tracked_files:
                if path.startswith('texts/') and path.endswith('.tess'):
                    base = os.path.basename(path)
                    stem = base[:-len('.tess')]
                    assert restricted_texts._normalize(stem) != text_id, (
                        f'{path} is tracked in origin/main but {text_id} is '
                        'in the restricted-texts registry')
