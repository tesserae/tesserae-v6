"""Tests for _resolve_with_fallback in backend.blueprints.search.

Covers:
  - Primary resolution (correct language) returns immediately
  - Fallback resolution (mismatched language) finds text in alternative directory
  - Completely missing text returns (None, None)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.blueprints.search import _resolve_with_fallback


def test_primary_resolution_returns_correct_language(tmp_path, monkeypatch):
    """When text exists in the requested language dir, return it directly."""
    texts_dir = tmp_path / "texts"
    la_dir = texts_dir / "la"
    la_dir.mkdir(parents=True)
    (la_dir / "vergil.aeneid.part.1.tess").write_text("test")

    path, lang = _resolve_with_fallback(str(texts_dir), "la", "vergil.aeneid.part.1.tess")

    assert path is not None
    assert lang == "la"
    assert os.path.basename(path) == "vergil.aeneid.part.1.tess"


def test_fallback_finds_text_in_alternative_language(tmp_path):
    """When text does NOT exist in the requested language dir, find it in another."""
    texts_dir = tmp_path / "texts"
    # Create Latin dir with a text file
    la_dir = texts_dir / "la"
    la_dir.mkdir(parents=True)
    (la_dir / "vergil.aeneid.part.1.tess").write_text("test")
    # Create empty Greek dir (no files)
    grc_dir = texts_dir / "grc"
    grc_dir.mkdir(parents=True)

    # Request resolution with wrong language 'grc' for a Latin text
    path, lang = _resolve_with_fallback(str(texts_dir), "grc", "vergil.aeneid.part.1.tess")

    assert path is not None
    assert lang == "la"  # Should have fallen back to Latin
    assert os.path.basename(path) == "vergil.aeneid.part.1.tess"


def test_missing_text_returns_none(tmp_path):
    """When text does not exist in any language directory, return (None, None)."""
    texts_dir = tmp_path / "texts"
    la_dir = texts_dir / "la"
    la_dir.mkdir(parents=True)
    grc_dir = texts_dir / "grc"
    grc_dir.mkdir(parents=True)

    path, lang = _resolve_with_fallback(str(texts_dir), "la", "nonexistent.text.tess")

    assert path is None
    assert lang is None


def test_fallback_greek_text_with_latin_language(tmp_path):
    """A Greek text ID sent with language='la' should resolve via fallback."""
    texts_dir = tmp_path / "texts"
    la_dir = texts_dir / "la"
    la_dir.mkdir(parents=True)
    grc_dir = texts_dir / "grc"
    grc_dir.mkdir(parents=True)
    (grc_dir / "homer.iliad.part.1.tess").write_text("test")

    path, lang = _resolve_with_fallback(str(texts_dir), "la", "homer.iliad.part.1.tess")

    assert path is not None
    assert lang == "grc"
    assert os.path.basename(path) == "homer.iliad.part.1.tess"
