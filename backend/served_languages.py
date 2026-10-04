"""The languages this server serves (2026-09-06).

A preview machine that holds only some languages' indexes sets
TESSERAE_LANGUAGES (comma-separated codes) so the site never offers, or tries
to list, a language it cannot serve. Production leaves it unset and serves
everything. Lives in its own module because both app.py and the corpus
blueprint need it and the blueprint cannot import app.py.
"""
import os


def allowed_languages():
    """The set of served language codes, or None when everything is served."""
    raw = (os.environ.get('TESSERAE_LANGUAGES') or '').strip()
    if not raw:
        return None
    return {x.strip() for x in raw.split(',') if x.strip()}


def is_served(language):
    allowed = allowed_languages()
    return not allowed or language in allowed
