"""_dedup_same_passage collapses the same passage duplicated across text_ids
that differ only by author/work spelling, without touching distinct loci."""
import os
# Importing backend.app has DB/secret side effects and captures DEPLOYMENT_ENV
# into a module global at import time. Set the same env other suites expect
# BEFORE importing, so whichever test module imports app first leaves it in the
# non-dev state test_security_headers.py relies on (HSTS is gated on this global).
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("TESSERAE_DIRECT_SERVER", "1")
os.environ.setdefault("SESSION_SECRET", "test-secret-key")
os.environ.setdefault("DEPLOYMENT_ENV", "test")

from backend.app import _dedup_same_passage  # noqa: E402


def test_collapses_author_variant_duplicate():
    # cyprian vs cyprian_saint at the same locus with the same line = one passage.
    rows = [
        {'author': 'Vergil', 'text_id': 'vergil.georgics.tess', 'locus': '1.154',
         'text': 'infelix lolium et steriles dominantur avenae'},
        {'author': 'Cyprian Saint', 'text_id': 'cyprian_saint.ad_demetrianum.tess',
         'locus': '23', 'text': 'lolium et avena'},
        {'author': 'Cyprian', 'text_id': 'cyprian.ad_demetrianum.tess',
         'locus': '23', 'text': 'lolium et avena'},
        {'author': 'Arnobius Of Sicca',
         'text_id': 'arnobius_of_sicca.adversus_nationes_libri_vii.tess',
         'locus': '2.59', 'text': 'inter lolium et avenam'},
        {'author': 'Arnobius', 'text_id': 'arnobius.adversus_nationes.tess',
         'locus': '2.59', 'text': 'inter lolium et avenam'},
    ]
    out = _dedup_same_passage(rows)
    assert len(out) == 3  # Vergil + one Cyprian + one Arnobius
    # the first occurrence is kept as representative
    assert out[1]['author'] == 'Cyprian Saint'
    assert out[2]['author'] == 'Arnobius Of Sicca'


def test_keeps_same_text_at_different_loci():
    # A repeated refrain: identical text, different loci -> both kept.
    rows = [
        {'text_id': 'x.tess', 'locus': '1.1', 'text': 'io triumphe'},
        {'text_id': 'x.tess', 'locus': '5.9', 'text': 'io triumphe'},
    ]
    assert len(_dedup_same_passage(rows)) == 2


def test_keeps_same_locus_different_text():
    # Same locus label in different works but different lines -> both kept.
    rows = [
        {'text_id': 'a.tess', 'locus': '1.1', 'text': 'arma virumque cano'},
        {'text_id': 'b.tess', 'locus': '1.1', 'text': 'in nova fert animus'},
    ]
    assert len(_dedup_same_passage(rows)) == 2


def test_empty_text_rows_always_kept():
    rows = [
        {'text_id': 'a.tess', 'locus': '1', 'text': ''},
        {'text_id': 'b.tess', 'locus': '1', 'text': ''},
    ]
    assert len(_dedup_same_passage(rows)) == 2


def test_whitespace_and_case_normalized():
    rows = [
        {'text_id': 'a.tess', 'locus': '3', 'text': 'Lolium  et   avena'},
        {'text_id': 'b.tess', 'locus': '3', 'text': 'lolium et avena'},
    ]
    assert len(_dedup_same_passage(rows)) == 1
