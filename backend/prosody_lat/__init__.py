"""Latin verse scanners, taken from the Classical Language Toolkit.

These eleven modules are cltk/prosody/lat/ from CLTK 1.5.0 (MIT licence, see
LICENSE beside this file), with only the package path in the imports changed.
They are pure Python. The full CLTK distribution depends on torch, spacy,
stanza and gensim, several gigabytes that the web application has no use for,
so the production server did without it, and every verse outside the
precomputed MQDQ table went unscanned (and, until 2026-10-10, logged an error).
backend/metrical_scanner.py uses CLTK's own copy when it is installed and
these otherwise.
"""
