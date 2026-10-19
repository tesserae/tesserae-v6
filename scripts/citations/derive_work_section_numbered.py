"""Write backend/citations/work_section_numbered.json (round 6).

The corpus numbers Cicero's speeches and treatises by section ("de orat.
1.225"), while the journals cite book, chapter and section ("de orat. 1, 52,
225"). The recognizer drops the chapter level of a printed locus that has one
level more than the work's corpus depth (extractor._drop_chapter_level), and
only for the works this file lists.

A work is listed when its id begins with "cicero.", its corpus depth in
work_depth.json is consistent (not in work_depth_inconsistent.json), and it is
not a collection of letters: in the letters the second level is the number of
the letter, which the corpus keeps, so a third level there is a section inside
the letter and the second level must stay.

Run from the repository root:  python3 scripts/citations/derive_work_section_numbered.py
"""
import json
import os

CITATIONS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                         "backend", "citations")
LETTERS = ("cicero.epistulae_ad_familiares", "cicero.letters_to_")


def main():
    with open(os.path.join(CITATIONS, "work_depth.json"), encoding="utf-8") as f:
        depth = json.load(f)
    with open(os.path.join(CITATIONS, "work_depth_inconsistent.json"), encoding="utf-8") as f:
        inconsistent = set(json.load(f))
    works = sorted(w for w in depth
                   if w.startswith("cicero.") and w not in inconsistent and not w.startswith(LETTERS))
    comment = ("Round 6. Works whose corpus file is numbered by section while the journals cite book, chapter "
               "and section (de orat. 1, 52, 225 is 1.225 in the corpus). A printed locus with one level more "
               "than the corpus depth in work_depth.json drops its second-to-last level. Cicero's speeches and "
               "treatises with a consistent corpus depth, written by "
               "scripts/citations/derive_work_section_numbered.py. The letters are left out because their "
               "second level is the letter, not a chapter.")
    with open(os.path.join(CITATIONS, "work_section_numbered.json"), "w", encoding="utf-8") as f:
        json.dump({"_comment": comment, "works": works}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(len(works), "works")


if __name__ == "__main__":
    main()
