# Greek

**Live.** ~1,288 works, 146 authors, including the SBL Greek New Testament and
the Septuagint (First1KGreek).

- 113,536 passage windows in the content index.
- Recall 78.5%@200 on Hunter 1989 Apollonius-Homer, type 4+5, 121 pairs.
- Lemmatisation: UD treebank lookup (58,481 mappings) with CLTK backoff.
- Cross-lingual Greek-Latin works through dictionary and semantic channels, plus
  a phonetic channel that transliterates Greek to Latin script and applies edit
  distance, used as a convergence booster only.

**Known issue, fix written but not merged:** exact search discarded every
SINGLE-WORD query in every language. A gate requiring two unique matched lemmas
was inherited from pairwise search, where it belongs, and applied to exact
search, where the regex has already found the literal phrase. `ῥοδοδάκτυλος`
returned 0 exact and 35 by lemma. Also affects repeated-word phrases such as
`iam iam`, which collapse to one unique word. Branch `fix/greek-exact-search`.
NC has asked that single-word exact search list occurrences.
