"""Build a Coptic NT→Psalms gold set from TSK cross-references.

Maps TSK Hebrew-numbered psalm refs to LXX (Sahidic) numbering.
"""
import csv
import re


def hebrew_to_lxx_psalm(h_chap, h_verse):
    """Convert Hebrew/Protestant psalm numbering to LXX numbering used by Sahidic.

    Mapping:
      Hebrew Ps 1-8   = LXX Ps 1-8
      Hebrew Ps 9-10  = LXX Ps 9 (the two get merged)
      Hebrew Ps 11-113 = LXX Ps 10-112 (off by 1)
      Hebrew Ps 114-115 = LXX Ps 113 (merged)
      Hebrew Ps 116 = LXX Ps 114-115 (split)
      Hebrew Ps 117-146 = LXX Ps 116-145 (off by 1)
      Hebrew Ps 147 = LXX Ps 146-147 (split)
      Hebrew Ps 148-150 = LXX Ps 148-150

    Returns a list of (lxx_chap, lxx_verse_lower_bound, lxx_verse_upper_bound) tuples
    so verse-level matching can be approximate for the merged/split psalms.
    """
    h_chap = int(h_chap)
    h_verse = int(h_verse)

    if 1 <= h_chap <= 8:
        return [(h_chap, h_verse, h_verse)]
    if h_chap == 9 or h_chap == 10:
        # both merge into LXX 9 — verses re-number; approximate as the whole LXX 9
        return [(9, 1, 38)]
    if 11 <= h_chap <= 113:
        return [(h_chap - 1, h_verse, h_verse)]
    if h_chap in (114, 115):
        # Hebrew 114+115 merge into LXX 113
        return [(113, 1, 26)]
    if h_chap == 116:
        # Hebrew 116 splits into LXX 114-115
        return [(114, 1, 9), (115, 1, 10)]
    if 117 <= h_chap <= 146:
        return [(h_chap - 1, h_verse, h_verse)]
    if h_chap == 147:
        # splits into LXX 146-147
        return [(146, 1, 11), (147, 1, 9)]
    if 148 <= h_chap <= 150:
        return [(h_chap, h_verse, h_verse)]
    return []


def parse_tsk_ref(ref):
    """Parse a TSK ref like 'Ps.110.1' or 'Ps.110.1-Ps.110.2' into a verse list."""
    if '-' in ref:
        left, right = ref.split('-', 1)
        # If right is just a verse (no book.chap), reuse left's prefix
        left_parts = left.split('.')
        if '.' not in right:
            # e.g., "Ps.110.1-2"
            right_parts = left_parts[:-1] + [right]
        else:
            right_parts = right.split('.')
        if len(left_parts) < 3 or len(right_parts) < 3:
            return []
        book, chap = left_parts[0], int(left_parts[1])
        v_low = int(left_parts[2])
        v_high = int(right_parts[2])
        return [(book, chap, v) for v in range(v_low, v_high + 1)]
    else:
        parts = ref.split('.')
        if len(parts) < 3:
            return []
        try:
            return [(parts[0], int(parts[1]), int(parts[2]))]
        except ValueError:
            return []


# TSK NT book -> V6 Sahidic NT filename stem
NT_BOOK_TO_SAHIDICA = {
    'Matt': 'sahidica.matthew',
    'Mark': 'sahidica.mark',
    'Luke': 'sahidica.luke',
    'John': 'sahidica.john',
    'Acts': 'sahidica.acts_of_the_apostles',
    'Rom': 'sahidica.romans',
    '1Cor': 'sahidica.1corinthians',
    '2Cor': 'sahidica.2_corinthians',
    'Gal': 'sahidica.galatians',
    'Eph': 'sahidica.ephesians',
    'Phil': 'sahidica.philippians',
    'Col': 'sahidica.colossians',
    '1Thess': 'sahidica.1_thessalonians',
    '2Thess': 'sahidica.2_thessalonians',
    '1Tim': 'sahidica.1_timothy',
    '2Tim': 'sahidica.2_timothy',
    'Titus': 'sahidica.titus',
    'Phlm': 'sahidica.philemon',
    'Heb': 'sahidica.hebrews',
    'Jas': 'sahidica.james',
    '1Pet': 'sahidica.1_peter',
    '2Pet': 'sahidica.2_peter',
    '1John': 'sahidica.1_john',
    '2John': 'sahidica.2_john',
    '3John': 'sahidica.3_john',
    'Jude': 'sahidica.jude',
    'Rev': 'sahidica.revelation',
}


def main():
    nt_books_focus = {'Heb', 'Matt'}  # build gold for these book(s) only
    gold_pairs = []

    with open('cross_references.txt') as f:
        next(f)  # header
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 3:
                continue
            from_ref, to_ref, votes_str = parts[0], parts[1], parts[2]
            try:
                votes = int(votes_str)
            except ValueError:
                votes = 0

            from_book = from_ref.split('.')[0]
            to_book = to_ref.split('.')[0]
            if from_book not in nt_books_focus or to_book != 'Ps':
                continue

            # Parse NT verse
            from_parsed = parse_tsk_ref(from_ref)
            if not from_parsed:
                continue
            # Parse Psalm verse(s)
            ps_parsed = parse_tsk_ref(to_ref)
            if not ps_parsed:
                continue

            for nt_book, nt_chap, nt_verse in from_parsed:
                for _ps_book, h_chap, h_verse in ps_parsed:
                    lxx_pairs = hebrew_to_lxx_psalm(h_chap, h_verse)
                    for lxx_chap, lxx_low, lxx_high in lxx_pairs:
                        for lxx_v in range(lxx_low, lxx_high + 1):
                            nt_filename_stem = NT_BOOK_TO_SAHIDICA.get(nt_book, '')
                            if not nt_filename_stem:
                                continue
                            gold_pairs.append({
                                'nt_book': nt_book,
                                'nt_chap': nt_chap,
                                'nt_verse': nt_verse,
                                'lxx_chap': lxx_chap,
                                'lxx_verse': lxx_v,
                                'votes': votes,
                                'nt_v6_ref': f"{nt_filename_stem}.{nt_chap}.{nt_verse}",
                                'lxx_v6_ref': f"sahidic.psalms.{lxx_chap}.{lxx_v}",
                            })

    # Dedup by (nt_v6_ref, lxx_v6_ref), keeping max votes
    dedup = {}
    for g in gold_pairs:
        key = (g['nt_v6_ref'], g['lxx_v6_ref'])
        if key not in dedup or dedup[key]['votes'] < g['votes']:
            dedup[key] = g
    gold_pairs = list(dedup.values())

    # Sort by votes descending
    gold_pairs.sort(key=lambda g: -g['votes'])

    out = 'nt_psalm_gold_lxx.csv'
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(gold_pairs[0].keys()))
        w.writeheader()
        w.writerows(gold_pairs)
    print(f"Wrote {out} with {len(gold_pairs)} unique gold pairs")
    print(f"Books: {set(g['nt_book'] for g in gold_pairs)}")
    print(f"Vote distribution: max={max(g['votes'] for g in gold_pairs)}, "
          f"min={min(g['votes'] for g in gold_pairs)}, "
          f"strong (votes>=10): {sum(1 for g in gold_pairs if g['votes']>=10)}, "
          f"verse-strong (votes>=20): {sum(1 for g in gold_pairs if g['votes']>=20)}")


if __name__ == '__main__':
    main()
