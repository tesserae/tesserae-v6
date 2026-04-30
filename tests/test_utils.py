import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend import utils


def test_resolve_text_path_handles_unicode_filename_when_direct_exists_raises(tmp_path, monkeypatch):
    texts_dir = tmp_path / "texts"
    lang_dir = texts_dir / "grc"
    lang_dir.mkdir(parents=True, exist_ok=True)

    filename = "aelius_herodianus.περι_καθολικης_προσῳδιας.tess"
    text_path = lang_dir / filename
    text_path.write_text("test line\n", encoding="utf-8")

    real_exists = utils.os.path.exists
    direct_path = os.path.realpath(os.path.join(str(lang_dir), filename))

    def unicode_hostile_exists(path):
        if path == direct_path:
            raise UnicodeEncodeError('ascii', filename, 20, 24, 'ordinal not in range(128)')
        return real_exists(path)

    monkeypatch.setattr(utils.os.path, 'exists', unicode_hostile_exists)

    resolved = utils.resolve_text_path(str(texts_dir), "grc", filename)

    assert resolved is not None
    assert real_exists(resolved)
    assert utils.fix_surrogate_escapes(os.path.basename(resolved)) == filename


def test_resolve_text_path_matches_unicode_normalization_variants(tmp_path):
    texts_dir = tmp_path / "texts"
    lang_dir = texts_dir / "grc"
    lang_dir.mkdir(parents=True, exist_ok=True)

    filename_nfc = "tryphon_i_grammaticus.περὶ_τρόπων.tess"
    filename_nfd = unicodedata.normalize("NFD", filename_nfc)
    (lang_dir / filename_nfd).write_text("test line\n", encoding="utf-8")

    resolved = utils.resolve_text_path(str(texts_dir), "grc", filename_nfc)

    assert resolved is not None
    assert unicodedata.normalize('NFC', os.path.basename(resolved)) == filename_nfc
