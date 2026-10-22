"""The pull request check that Help is updated with visitor-facing changes."""
import importlib.util
import os

spec = importlib.util.spec_from_file_location(
    'help_coverage', os.path.join(os.path.dirname(__file__), '..', '.github', 'scripts', 'help_coverage.py'))
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


def test_code_without_help_fails():
    ok, msg = h.check(['backend/blueprints/events.py', 'tests/test_events_api.py'], '')
    assert not ok and 'backend/blueprints/events.py' in msg


def test_help_or_scope_box_passes():
    assert h.check(['client/src/components/events/EventView.jsx', 'client/src/components/pages/HelpPage.jsx'], '')[0]
    assert h.check(['backend/blueprints/entities.py', 'client/src/data/searchScope.js'], '')[0]


def test_tests_scripts_and_records_only_pass():
    assert h.check(['tests/test_x.py', 'scripts/events/x.py', 'docs/DATA_OPERATIONS.md', 'CHANGELOG.md',
                    'client/src/components/reader/ResultsPanel.test.jsx'], '')[0]


def test_waiver_needs_a_reason():
    assert h.check(['backend/runtime.py'], 'Body\n\nHelp: not needed, internal refactor with no visible change.\n')[0]
    assert not h.check(['backend/runtime.py'], 'Help: not needed')[0]
