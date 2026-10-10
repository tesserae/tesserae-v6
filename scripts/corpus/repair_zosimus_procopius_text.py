#!/usr/bin/env python3
"""Repair the encoding damage in Perseus's Procopius and First1KGreek's Zosimus.

The First1KGreek TEI of Zosimus, Historia Nova (tlg4084.tlg001.1st1K-grc1)
carries 20 places where a letter was lost in digitising and a literal
"??" stands between a rough-breathing mark and a smooth one (for example
"μητρόπ̔??ʼλιν" for μητρόπολιν). Eighteen are restored below to the reading
the word and its context fix. The two consular numerals in 6.2.1, which
the context does not fix, are removed (the damaged token is dropped, no
numeral is invented). Perseus's Procopius has two places where a combining
rough breathing joins two words ("ἄδοξον̔τὸ"): a space is put back.

    repair_zosimus_procopius_text.py FILE.tess [FILE.tess ...]

Each file is rewritten in place. Prints how many replacements were made in
each file; run on the whole-work file and the per-book files alike.
"""
import re
import sys

ZOSIMUS = [
    ("μητρόπ̔??'λιν", "μητρόπολιν"),
    ("Σ̔??'ρπηδονἴου", "Σαρπηδονίου"),
    ("καρτερὡ??'έρα", "καρτερώτερα"),
    ("Μαιὥ??'ιδι", "Μαιώτιδι"),
    ("ʽ??'υνεῖναι", "συνεῖναι"),
    ("ʽ??'ο δεῖπνον", "τὸ δεῖπνον"),
    ("ʽ??'οίαις", "ποίαις"),
    ("χ̔??'ρσὶν", "χερσὶν"),
    ("ʽ??'ουάδοι", "Κουάδοι"),
    ("μ̔??'τὰ", "μετὰ"),
    ("ʽ??'αταστήσας", "καταστήσας"),
    ("τ̔??' ἐν", "τὰ ἐν"),
    ("ʽ??'ί τι", "εἴ τι"),
    ("ὅ??'α", "ὅσα"),
    ("ʽ??'ὐτὸν", "αὐτὸν"),
    ("ἀπὁ??'φαλεὶς", "ἀποσφαλεὶς"),
    ("αὐθἁ??'ιζομένη", "αὐθαδιζομένη"),
    ("ʽ??'οιεῖσθαι", "ποιεῖσθαι"),
    ("τὸ ʽ??', καὶ Θεοδοσίου τὸ ʽ??',", "τὸ, καὶ Θεοδοσίου τὸ,"),
]
# combining rough breathing after a consonant joins two words
JOINED = re.compile('(?<=[βγδζθκλμνξπρστφχψς])̔(?=[Ͱ-Ͽἀ-῿])')

for path in sys.argv[1:]:
    text = open(path, encoding='utf-8').read()
    n = 0
    if 'zosimus' in path:
        for old, new in ZOSIMUS:
            n += text.count(old)
            text = text.replace(old, new)
        old = "τὸ \u02bd??' καὶ Θεοδοσίου τὸ \u02bd??',"
        n += text.count(old)
        text = text.replace(old, "τὸ καὶ Θεοδοσίου τὸ,")
        if '??' in text:
            sys.exit(f'{path}: "??" left after repair')
    else:
        text, k = JOINED.subn(' ', text)
        n += k
    open(path, 'w', encoding='utf-8', newline='').write(text)
    print(f'{path}: {n} replacements')
