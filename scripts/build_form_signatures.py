"""Count, across a whole language's corpus, how many poems carry each
refrain-and-rhyme signature (radif, qafia), for the form channel's
corpus-wide rarity (backend/poetics.py: load_form_signatures,
corpus_form_factor).

Writes data/poetics/form_signatures_<lang>.json:
    {"language": "ur", "built": "...", "texts": [...], "total_poems": n,
     "signatures": {"radif tokens|qafia": poems}, "radifs": {"radif tokens": poems}}

Whole-work files are counted; a .part. file is skipped when its whole work
exists, so no poem is counted twice. Units come from the lemma cache
(cache/lemmas/<lang>/), the same units the search uses, falling back to the
text processor for an uncached file.

Usage:
    python scripts/build_form_signatures.py ur fa
"""
import datetime
import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.lemma_cache import get_cached_units          # noqa: E402
from backend.poetics import segment_poems, poem_signature, signature_key  # noqa: E402


def whole_work_files(lang_dir):
    names = sorted(f for f in os.listdir(lang_dir) if f.endswith('.tess'))
    wholes = {n for n in names if '.part.' not in n}
    keep = []
    for n in names:
        if '.part.' in n:
            whole = re.sub(r'\.part\.[^.]+\.tess$', '.tess', n)
            if whole in wholes:
                continue
        keep.append(n)
    return keep


def units_for(filename, lang, lang_dir):
    cached = get_cached_units(filename, lang)
    if cached and 'units_line' in cached:
        return cached['units_line']
    from backend.text_processor import TextProcessor
    return TextProcessor().process_file(os.path.join(lang_dir, filename), lang, 'line')


def build(lang):
    lang_dir = os.path.join(ROOT, 'texts', lang)
    sigs, radifs = Counter(), Counter()
    total = 0
    texts = []
    for fn in whole_work_files(lang_dir):
        units = units_for(fn, lang, lang_dir)
        poems = segment_poems(units, lang)
        n_sig = 0
        for poem in poems:
            radif, qafia, _ = poem_signature(poem, lang)
            if not radif:
                continue
            n_sig += 1
            sigs[signature_key(radif, qafia)] += 1
            radifs[' '.join(radif)] += 1
        total += len(poems)
        texts.append({'file': fn, 'poems': len(poems), 'with_refrain': n_sig})
        print(f"  {fn}: {len(poems)} poems, {n_sig} with a refrain", flush=True)
    out = {
        'language': lang,
        'built': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
        'texts': texts,
        'total_poems': total,
        'signatures': dict(sigs.most_common()),
        'radifs': dict(radifs.most_common()),
    }
    path = os.path.join(ROOT, 'data', 'poetics', f'form_signatures_{lang}.json')
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=0)
    print(f"{lang}: {len(texts)} texts, {total} poems, {len(sigs)} signatures, {len(radifs)} refrains -> {path}")
    print("  most common signatures:", sigs.most_common(5))
    print("  most common refrains:", radifs.most_common(5))


if __name__ == '__main__':
    for lang in sys.argv[1:] or ['fa', 'ur']:
        build(lang)
