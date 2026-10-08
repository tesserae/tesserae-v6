"""Shared name-normalization helpers for matching hucit KB names/titles against
Tesserae file-stem slugs, and for building/looking up abbreviation keys.

Latin and Greek author/work names come down to us with a lot of orthographic
variance that isn't meaningful for identity (u/v, i/j, ae/oe/e, accents,
transliteration differences). We fold all of that away for MATCHING purposes
only; the original strings are always preserved in the output data.
"""
import re
import unicodedata

_STOPWORDS = {"the", "of", "de", "in", "et", "ad", "a", "an", "and"}


def strip_accents(s):
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def canonical_key(s):
    """Fold orthographic variants into one canonical token string, for
    matching only. 'Virgil' / 'Vergil' / 'Vergilius' -> comparable forms."""
    if not s:
        return ""
    s = strip_accents(s).lower()
    s = s.replace("j", "i").replace("v", "u")
    s = s.replace("ae", "e").replace("oe", "e")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    tokens = [t for t in s.split() if t and t not in _STOPWORDS]
    return " ".join(tokens)


def tokens_of(s):
    return canonical_key(s).split()


def slug_to_words(slug):
    """Tesserae file-stem component ('vergil_pseudo', 'oedipus_tyrannus') to
    a space-joined word string for matching."""
    return slug.replace("_", " ")


def split_work_id(base_id):
    """'vergil.aeneid' -> ('vergil', 'aeneid'); 'vergil_pseudo.appendix_vergiliana_combined'
    -> ('vergil_pseudo', 'appendix_vergiliana_combined'). Only the first dot
    matters; some ids have none (rare)."""
    if "." in base_id:
        author_slug, work_slug = base_id.split(".", 1)
    else:
        author_slug, work_slug = base_id, ""
    return author_slug, work_slug
