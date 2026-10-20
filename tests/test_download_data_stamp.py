"""The download script keeps a stamp beside each unpacked data file with the
SHA-256 of the archive it came from, so a file unpacked from an archive the
manifest no longer lists is fetched again instead of being skipped."""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, '..', 'scripts', 'download_data.py')

spec = importlib.util.spec_from_file_location('download_data', SCRIPT)
dd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dd)


def test_missing_file(tmp_path):
    assert dd.file_status(str(tmp_path / 'x.db'), 'ab' * 32) == 'missing'


def test_present_without_stamp_is_ok(tmp_path):
    f = tmp_path / 'x.db'
    f.write_bytes(b'data')
    assert dd.file_status(str(f), 'ab' * 32) == 'ok'


def test_matching_stamp_is_ok(tmp_path):
    f = tmp_path / 'x.db'
    f.write_bytes(b'data')
    dd.write_stamp(str(f), 'AB' * 32)
    assert dd.read_stamp(str(f)) == 'ab' * 32
    assert dd.file_status(str(f), 'ab' * 32) == 'ok'


def test_different_stamp_is_stale(tmp_path):
    f = tmp_path / 'x.db'
    f.write_bytes(b'data')
    dd.write_stamp(str(f), 'ab' * 32)
    assert dd.file_status(str(f), 'cd' * 32) == 'stale'


def test_pending_checksum_never_stale(tmp_path):
    f = tmp_path / 'x.db'
    f.write_bytes(b'data')
    dd.write_stamp(str(f), 'ab' * 32)
    assert dd.file_status(str(f), 'pending') == 'ok'
    assert dd.file_status(str(f), None) == 'ok'


def test_pending_checksum_writes_no_stamp(tmp_path):
    f = tmp_path / 'x.db'
    f.write_bytes(b'data')
    dd.write_stamp(str(f), 'pending')
    assert dd.read_stamp(str(f)) is None
