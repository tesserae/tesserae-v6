"""How a work is named, in one place.

A text that is too long for one file is stored as several: the Aeneid is
`vergil.aeneid.tess` and also `vergil.aeneid.part.1.tess` through
`.part.12.tess`. Counting, grouping and looking things up all need to treat
those as one work, and before 2026-09-21 fourteen places in the codebase
worked out how, each in its own way:

    backend/passage_index.py      _norm_work: strip directory, strip .tess,
                                  then split at '.part.'
    backend/translations.py       _norm_work: strip directory and .tess but
                                  KEEP the part, with a separate fallback
    backend/blueprints/corpus.py  re.sub(r'\\.part\\.\\d+$', ...)
    and eleven more inline copies of `.split('.part.')[0]`, plus the same
    rule written again as SQL in backend/blueprints/hapax.py.

TWO OPERATIONS, and confusing them is the bug. `work_id` answers "which
file is this?" and keeps the part, because a part is a real, separately
readable text. `base_work` answers "which work does this belong to?" and
collapses it.

THE REGEX VARIANT IS WRONG, which is why the split form is canonical. A
part file may carry a label after its number: `pindar.odes.part.2.nemeans`,
`nonnus_of_panopolis.dionysiaca.part.1.books_1-10`,
`jerome.vulgate.part.12.1_chronicles`. On 2026-09-21 the corpus held 215
such files across 16 works. `re.sub(r'\\.part\\.\\d+$', '', ...)` requires
the number to end the name, so it leaves all 215 uncollapsed and the work
is not recognised as itself. Nothing errors: a description, a translation
or a count simply is not found.
"""

__all__ = ['work_id', 'base_work', 'is_part', 'sql_base_work']

_PART = '.part.'
_SUFFIX = '.tess'


def work_id(name):
    """The file's own identifier: no directory, no .tess, part kept.

    `la/vergil.aeneid.part.1.tess` becomes `vergil.aeneid.part.1`. Use this
    when the part is the thing being named, as a Reader link or a
    translation file is.
    """
    w = name or ''
    if '/' in w:
        w = w.rsplit('/', 1)[-1]
    if w.endswith(_SUFFIX):
        w = w[:-len(_SUFFIX)]
    return w


def base_work(name):
    """The work the file belongs to: part collapsed.

    `la/vergil.aeneid.part.1.tess` and `pindar.odes.part.2.nemeans` become
    `vergil.aeneid` and `pindar.odes`. Use this for counting, grouping,
    de-duplicating, and any lookup keyed by the work rather than the file.
    """
    return work_id(name).split(_PART)[0]


def is_part(name):
    """True when this file is one part of a longer work."""
    return _PART in work_id(name)


def sql_base_work(column):
    """The same collapse as SQL, for a query that groups by work.

    Kept here so the rule cannot drift between the Python and the SQL, which
    is what happened in backend/blueprints/hapax.py. Returns an expression,
    not a statement, and keeps the .tess suffix the filename columns carry.
    """
    return (f"CASE WHEN instr({column}, '{_PART}') > 0 "
            f"THEN substr({column}, 1, instr({column}, '{_PART}') - 1) || '{_SUFFIX}' "
            f"ELSE {column} END")
