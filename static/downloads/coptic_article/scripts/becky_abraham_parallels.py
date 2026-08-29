"""Generate a parallels-inspection file for Becky Krawiec.

Runs V6 fusion (biblical_coptic profile) on:
    Source: Sahidic Coptic Bible (the older, quoted corpus)
    Target: Shenoute, Abraham our Father (the later, quoting text)

Tesserae convention: "source" is the text being alluded to (older); "target"
is the text doing the alluding (later). The fusion search itself produces
the same line pairs either way; orienting the search this way just makes
the labelling unambiguous for a reader.

Outputs two files:

  1. A CSV (the primary deliverable for Becky) that opens cleanly in Excel /
     Numbers / Google Sheets with one row per parallel and real columns for
     Becky's Label and Notes.
  2. A readable Markdown view of the same parallels (text rendered, easy to
     skim before opening the CSV).

Both files are generated from the same fusion run.

Usage:
    python evaluation/coptic_recall/becky_abraham_parallels.py
    python evaluation/coptic_recall/becky_abraham_parallels.py --top 100
"""

import argparse
import csv
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, '/home/ncoffee/tesserae-v6-dev')
os.chdir('/home/ncoffee/tesserae-v6-dev')

from dotenv import load_dotenv
load_dotenv('/home/ncoffee/tesserae-v6-dev/.env')

from backend.text_processor import TextProcessor
from backend.matcher import Matcher
from backend.scorer import Scorer
from backend.fusion import iter_fusion_search

# Bible = source (older, quoted), Shenoute = target (later, quoting).
SOURCE_ID = 'sahidic.bible.tess'
TARGET_ID = 'shenoute.abraham.tess'
SOURCE_PATH = f'/home/ncoffee/tesserae-v6-dev/texts/cop/{SOURCE_ID}'
TARGET_PATH = f'/home/ncoffee/tesserae-v6-dev/texts/cop/{TARGET_ID}'


def run_fusion(top_n):
    tp = TextProcessor()
    src = tp.process_file(SOURCE_PATH, language='cop')
    tgt = tp.process_file(TARGET_PATH, language='cop')

    print(f"  source (Bible): {SOURCE_ID} ({len(src)} units)")
    print(f"  target (Shenoute): {TARGET_ID} ({len(tgt)} units)")
    print(f"  running fusion (biblical_coptic profile)...")

    results = []
    last_pct = -1
    for evt, data in iter_fusion_search(
        source_units=src, target_units=tgt,
        matcher=Matcher(), scorer=Scorer(),
        source_id=SOURCE_ID, target_id=TARGET_ID,
        language='cop', mode='merged',
        max_results=max(top_n * 2, 500),
        source_path=SOURCE_PATH, target_path=TARGET_PATH,
    ):
        if evt == 'progress':
            pct = int(data.get('progress', 0) * 100)
            if pct >= last_pct + 10:
                print(f"  {pct}%...")
                last_pct = pct
        elif evt == 'complete':
            results = data.get('results', [])
    return results[:top_n]


def format_markdown(results, top_n):
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    header = f"""# Tesserae V6 parallels: Sahidic Coptic Bible × Shenoute, *Abraham our Father*

Generated {now}. V6 configuration: biblical-Coptic profile (10 channels,
including the multilingual-e5 semantic channel, the quotation-finder channel,
and the Coptic Wordnet–backed dictionary channel). Source: Sahidic Coptic Bible
(`{SOURCE_ID}`, OT + NT combined, 27,134 lines). Target: Shenoute,
*Abraham our Father* (`{TARGET_ID}`, 318 lines). Top {top_n} ranked results
below.

The companion CSV file `becky_abraham_parallels.csv` has the same parallels
in a spreadsheet-friendly format with real Label and Notes columns. Use that
file for filling in your judgements; this Markdown file is provided for
readable skimming.

## How to grade

For each parallel, please fill in **Label** with one of:

- **Q** — verbatim quotation
- **P** — paraphrase (same idea, different vocabulary)
- **A** — looser allusion or thematic echo
- **N** — not a real intertext / coincidence
- **?** — unsure / needs more context

The **Notes** field is free-form. Anything you want to flag (Greek-loanword
issue, mis-segmented bound group, candidate reference to a third text, etc.)
is welcome. The goal is twofold: (a) confirm that the top of V6's ranked list
is mostly real intertexts, and (b) generate a precision number we can report
in the article.

---

"""
    lines = [header]
    for i, r in enumerate(results, start=1):
        bible_ref = r['source']['ref'].strip()
        bible_text = (r['source']['text'] or '').strip()
        shen_ref = r['target']['ref'].strip()
        shen_text = (r['target']['text'] or '').strip()
        score = r.get('fused_score', 0.0)
        channels = r.get('channels') or []
        features = r.get('features') or {}
        run_len = features.get('quotation_run_length', '')
        ch_label = ', '.join(channels[:6])
        if run_len:
            ch_label += f" (quotation run = {run_len} tokens)"
        lines.append(f"### {i}. score {score:.2f}  —  channels: {ch_label}\n")
        lines.append(f"**Bible** (source): `{bible_ref}`\n")
        lines.append(f"> {bible_text}\n")
        lines.append(f"**Shenoute** (target): `{shen_ref}`\n")
        lines.append(f"> {shen_text}\n")
        lines.append(f"**Label:** _____   **Notes:** \n")
        lines.append("\n---\n")
    return '\n'.join(lines)


def write_csv(results, csv_path):
    fieldnames = [
        'rank', 'score', 'channels', 'quotation_run_tokens',
        'bible_ref', 'bible_text', 'shenoute_ref', 'shenoute_text',
        'label', 'notes',
    ]
    with open(csv_path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for i, r in enumerate(results, start=1):
            features = r.get('features') or {}
            w.writerow({
                'rank': i,
                'score': round(r.get('fused_score', 0.0), 2),
                'channels': ', '.join(r.get('channels') or []),
                'quotation_run_tokens': features.get('quotation_run_length', ''),
                'bible_ref': r['source']['ref'].strip(),
                'bible_text': (r['source']['text'] or '').strip(),
                'shenoute_ref': r['target']['ref'].strip(),
                'shenoute_text': (r['target']['text'] or '').strip(),
                'label': '',
                'notes': '',
            })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=50,
                    help='Number of top results to include (default: 50)')
    ap.add_argument('--out-md', default='research/languages/coptic/becky_abraham_parallels.md')
    ap.add_argument('--out-csv', default='research/languages/coptic/becky_abraham_parallels.csv')
    args = ap.parse_args()

    print(f"[setup] generating top {args.top} parallels")
    results = run_fusion(args.top)
    print(f"[done] {len(results)} results")

    md = format_markdown(results, args.top)
    md_path = os.path.join('/home/ncoffee/tesserae-v6-dev', args.out_md)
    with open(md_path, 'w') as f:
        f.write(md)
    print(f"[wrote] {md_path}")

    csv_path = os.path.join('/home/ncoffee/tesserae-v6-dev', args.out_csv)
    write_csv(results, csv_path)
    print(f"[wrote] {csv_path}")


if __name__ == '__main__':
    main()
