"""Add the table form_entities to a copy of the People & Places store (2026-10-21).

One row per folded token the scan linked: the entity whose page lists most of that token's lines.
The search falls back to it when the typed text matches no heading or spelling, so the Reader's
"Shared names" links, which carry the word as the line spells it, open an entry. Before it, 22
percent of those links (by passage, in a sample of 1,500 rare names) found nothing.

    python scripts/entities/write_form_index.py STORE_COPY
"""
import sys

from backend import entity_extras as extras

if __name__ == '__main__':
    extras.write_form_index(sys.argv[1])
