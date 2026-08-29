"""Build Greek-Greek gold set: Greek NT verses → Greek LXX Psalms verses.

Uses TSK cross-references (Hebrew psalm numbering) and converts to LXX numbering
to match the Greek LXX Psalms file. Source: Hebrews only for parity with the
Coptic experiment.
"""
import csv
from build_gold_set import hebrew_to_lxx_psalm, parse_tsk_ref

# V6 ref formats for the Greek files
NT_HEB_PREFIX = 'novum_testamentum.ad_hebraeos'
PSALMI_PREFIX = 'septuaginta.psalmi urn:cts:greekLit:tlg0527.tlg027.1st1K-grc1'


def main():
    gold_pairs = []

    with open('cross_references.txt') as f:
        next(f)
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 3:
                continue
            from_ref, to_ref, votes_str = parts[0], parts[1], parts[2]
            try:
                votes = int(votes_str)
            except ValueError:
                votes = 0
            if not from_ref.startswith('Heb.'):
                continue
            if not to_ref.startswith('Ps.'):
                continue

            from_parsed = parse_tsk_ref(from_ref)
            ps_parsed = parse_tsk_ref(to_ref)
            if not from_parsed or not ps_parsed:
                continue

            for _nt_book, nt_chap, nt_verse in from_parsed:
                for _ps_book, h_chap, h_verse in ps_parsed:
                    lxx_pairs = hebrew_to_lxx_psalm(h_chap, h_verse)
                    for lxx_chap, lxx_low, lxx_high in lxx_pairs:
                        for lxx_v in range(lxx_low, lxx_high + 1):
                            gold_pairs.append({
                                'nt_book': 'Heb',
                                'nt_chap': nt_chap,
                                'nt_verse': nt_verse,
                                'lxx_chap': lxx_chap,
                                'lxx_verse': lxx_v,
                                'votes': votes,
                                'nt_v6_ref': f"{NT_HEB_PREFIX}.{nt_chap}.{nt_verse}",
                                'lxx_v6_ref': f"{PSALMI_PREFIX}.{lxx_chap}.{lxx_v}",
                            })

    # Dedup by (nt_v6_ref, lxx_v6_ref), keep highest votes
    dedup = {}
    for g in gold_pairs:
        key = (g['nt_v6_ref'], g['lxx_v6_ref'])
        if key not in dedup or dedup[key]['votes'] < g['votes']:
            dedup[key] = g
    gold_pairs = sorted(dedup.values(), key=lambda g: -g['votes'])

    out = 'nt_psalm_gold_greek.csv'
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(gold_pairs[0].keys()))
        w.writeheader()
        w.writerows(gold_pairs)
    print(f"Wrote {out} with {len(gold_pairs)} pairs (Heb × LXX Psalmi)")
    print(f"Vote distribution: strong (votes>=20): {sum(1 for g in gold_pairs if g['votes']>=20)}, "
          f"verse-strong (votes>=50): {sum(1 for g in gold_pairs if g['votes']>=50)}")


if __name__ == '__main__':
    main()
