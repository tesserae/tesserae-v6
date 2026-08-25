# Arabic

**Demo only. This is not an Arabic corpus, and it is deliberately withheld from
the released passage index.**

- 32 passage windows from a six-text demo, four of them Qur'an.
- Assembled to show a colleague. Our own development record states Arabic is not
  ready as an intertextuality tool until a real corpus is committed and
  validation passes.
- Three authors dated (Imru al-Qais, Tarafa, the Qur'an) so that anything
  appearing in a chronological view is not stranded.
- A lexical index exists in `~/tesserae-multilang` (`ar_index.db`) on branch
  `feature/multilang-ship`, not merged.

Publishing this as an "Arabic slice" would misrepresent it, which is why
`scripts/build_passage_index_release.py` names it `_ar_withheld` and refuses to
emit it.
