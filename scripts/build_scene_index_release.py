#!/usr/bin/env python3
"""Split the scene index into per-language releases, each with its own licence.

WHY SPLIT
---------
The index is 603,594 windows and most of it derives from public-domain sources.
Several slices do not, and they differ from each other:

    Hebrew   5,372 windows, from BHSA, which is CC BY-NC
    Coptic  13,199 windows, from Coptic SCRIPTORIUM, which is CC BY
    Urdu     2,148 windows, from Rekhta, terms NOT established
    Arabic      32 windows, a demo, not a corpus at all

Publishing one bundle would force the most restrictive term onto everything, so
1.4% of the index would make the other 98.6% non-commercial. Splitting by
language costs a user a few extra clicks and costs the project nothing: every
record carries its language, and reassembly is concatenation, for which
`merge_index.py` already exists and checks its own invariants.

A commercial user can take Latin, Greek and English and have a working system.
Under a single NC bundle they could take nothing.

WHAT EACH SLICE CONTAINS
------------------------
The same three files the running system loads, so a slice is not a special
export format that then has to be converted:

    ids.json           window ids, in embedding row order
    embeddings.npy     float16 (N, 1024), row i belongs to ids[i]
    descriptions.jsonl one JSON record per window
    LICENCE.txt        what governs this slice and who to attribute
    MANIFEST.json      how it was built

The invariant that matters is that the three stay in lockstep. A slice whose ids
and rows disagree does not fail loudly, it returns the wrong passage for every
query, so it is checked before writing and verified after.
"""
import hashlib
import json
import os
import shutil
import sys
from collections import Counter

import numpy as np

INDEX = '/home/ncoffee/tesserae-scene/data/scene_index'
OUT = '/home/ncoffee/tesserae-scene/data/releases/scene_index'

# What actually governs each slice, and why. Written out per language rather than
# held in one blanket statement, because they genuinely differ.
LICENCES = {
    'la': ('Public Domain / CC BY-SA 4.0 where Perseus TEI is involved',
           'Source texts are public domain. Some are drawn from the Perseus\n'
           'Digital Library, whose TEI markup is CC BY-SA 4.0; where a description\n'
           'derives from a Perseus text, attribute Perseus Digital Library,\n'
           'Tufts University.'),
    'grc': ('Public Domain / CC BY-SA 4.0 where Perseus TEI is involved',
            'As Latin. Includes the SBL Greek New Testament (SBLGNT), used under\n'
            'the SBLGNT licence, and the Septuagint from the First1KGreek project.'),
    'en': ('Public Domain',
           'Source texts are public domain (World English Bible, and\n'
           'pre-1930 literary texts).'),
    'cop': ('CC BY 4.0',
            'Descriptions derive from Coptic SCRIPTORIUM texts and their English\n'
            'translation layer, CC BY 4.0. Attribute Coptic SCRIPTORIUM\n'
            '(copticscriptorium.org).\n\n'
            'IMPORTANT: no available model reads Coptic well enough to describe\n'
            'it. These descriptions were made from the ENGLISH TRANSLATIONS, not\n'
            'from the Coptic, and every record carries derived_from_translation.\n'
            'They are evidence at one remove and should be cited as such.'),
    'fa': ('Ganjoor data, freely available',
           'Texts from the Chronological Persian Poetry Dataset, based on\n'
           'Ganjoor (ganjoor.net), the standard free digital corpus of classical\n'
           'Persian poetry. Credit the Ganjoor Project and the Chronological\n'
           'Persian Poetry Dataset.\n\n'
           'NOTE ON WHAT THIS DOES AND DOES NOT CAPTURE: Persian poetic\n'
           'intertextuality works substantially through FORM. A javab or\n'
           'istiqbal answers a predecessor in the same metre, rhyme and radif,\n'
           'and can do so with almost no shared vocabulary. These descriptions\n'
           'capture content, not form, so that whole mode of response is\n'
           'invisible to them.'),
    'ur': ('Public Domain (descriptions of public-domain poetry)',
           'The underlying poetry is public domain: Ghalib died 1869, Mir 1810.\n'
           'The texts were parsed from Rekhta (rekhta.org), and Rekhta should be\n'
           'credited as the digitisation source.\n\n'
           'This slice contains NO URDU TEXT. It holds English descriptions,\n'
           'embeddings and reference tags; the only Arabic-script characters in a\n'
           'record are the radif letter inside a citation. So redistributing it\n'
           'does not redistribute anyone else digitisation.\n\n'
           'The same caution about form applies as for Persian: the Urdu ghazal\n'
           'tradition answers through shared radif and metre, which content\n'
           'descriptions do not see.'),
    # Arabic is deliberately NOT released. 32 windows from a six-text demo, four
    # of them Qur'an, and our own development record says Arabic is not ready as
    # an intertextuality tool. A language slice that is not a language invites
    # exactly the misreading a "demo" label tries to prevent.
    '_ar_withheld': ('DEMO ONLY -- not a corpus',
           'THIS IS NOT AN ARABIC CORPUS. It is 32 windows from a six-text demo,\n'
           'four of them Qur\'an, assembled to show a colleague. Our own\n'
           'development record states Arabic is not ready as an intertextuality\n'
           'tool until a real corpus is committed and validation passes.\n'
           'Publishing this as an "Arabic slice" would misrepresent it.'),
    'he': ('CC BY-NC 4.0  -- NON-COMMERCIAL',
           'Descriptions derive from the BHSA (Biblia Hebraica Stuttgartensia\n'
           'Amstelodamensis) morphology, which is CC BY-NC 4.0. That restriction\n'
           'passes to this slice. Do not use it commercially.\n'
           'Attribute the ETCBC, Vrije Universiteit Amsterdam.'),
}

BUILD = {
    'describer_model': 'Qwen/Qwen2.5-32B-Instruct (Apache-2.0)',
    'embedding_model': 'intfloat/multilingual-e5-large',
    'embedding_prefix': 'query: ',
    'window_geometry': {'fine': '12 lines, step 6', 'coarse': '30 lines, step 15',
                        'minimum_lines': 4, 'prompt_text_cap_chars': 1400},
    'description_fields': ['mode', 'setting', 'participants', 'action_steps',
                           'props', 'themes', 'imagery_tone', 'gist'],
    'mode_vocabulary': ['narrative', 'speech', 'lyric', 'argument', 'description',
                        'catalog', 'prayer', 'prophecy', 'dialogue'],
    'names_in_text_field': (
        'true/false/null. Whether the people the description names actually occur '
        'in the passage. Measured over the whole index AFTER a correction pass: '
        '99.9% true, 0.1% false (208 of 149,917 checkable descriptions). The '
        'first pass ran at 93.9%/6.1%; the 9,166 failures were re-described with '
        'the passage\'s actual proper names supplied as a constraint. '
        'null means the question could not be asked, either because no names were '
        'given or because the passage is not in Latin script, where an English '
        'name would never match literally. Treat false as "machine summary, '
        'unverified" rather than as an error to hide.'),
    'calibration_warning': (
        'MODERATE_COMBINED and STRONG_COMBINED in backend/scene_index.py were '
        'fitted to THIS corpus and are not a property of the method. If your '
        'index differs in size, languages or genre balance they will be wrong for '
        'you. Refit with evaluation/scripts/calibrate_confidence.py; see '
        'evaluation/probe_sets/README.md for how to build the probe set. This is '
        'the only calibrated constant in the system: the context channel measures '
        'its own baseline per text pair and needs nothing.'),
}


def sha256(path, cap=None):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    ids = json.load(open(os.path.join(INDEX, 'ids.json'), encoding='utf-8'))
    emb = np.load(os.path.join(INDEX, 'embeddings.npy'), mmap_mode='r')
    if emb.shape[0] != len(ids):
        raise SystemExit('source index is inconsistent; refusing to release it')

    recs = {}
    with open(os.path.join(INDEX, 'descriptions.jsonl'), encoding='utf-8') as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get('id'):
                recs[r['id']] = r
    print(f'source index: {len(ids):,} windows, dim {emb.shape[1]}')

    by_lang = Counter(recs.get(i, {}).get('language') for i in ids)
    print('by language:', dict(by_lang))

    os.makedirs(OUT, exist_ok=True)
    index_of = {}
    for lang in by_lang:
        if not lang or lang not in LICENCES:
            if lang:
                print(f'  {lang}: WITHHELD from the release (no licence entry)')
            continue
        rows = [n for n, i in enumerate(ids) if recs.get(i, {}).get('language') == lang]
        if not rows:
            continue
        d = os.path.join(OUT, lang)
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)

        slice_ids = [ids[n] for n in rows]
        json.dump(slice_ids, open(os.path.join(d, 'ids.json'), 'w'), ensure_ascii=False)
        np.save(os.path.join(d, 'embeddings.npy'),
                np.asarray(emb[rows], dtype=emb.dtype))
        with open(os.path.join(d, 'descriptions.jsonl'), 'w', encoding='utf-8') as fh:
            for i in slice_ids:
                fh.write(json.dumps(recs[i], ensure_ascii=False) + '\n')

        short, text = LICENCES.get(lang, ('Unknown', 'Licence not determined.'))
        with open(os.path.join(d, 'LICENCE.txt'), 'w', encoding='utf-8') as fh:
            fh.write(f'Tesserae V6 scene index -- {lang} slice\n')
            fh.write(f'Licence: {short}\n\n{text}\n\n')
            fh.write('The descriptions themselves were generated by an Apache-2.0\n'
                     'model. The terms above follow from the SOURCE TEXTS they\n'
                     'describe, since a description is a derivative of its source.\n')

        # Verify what was written rather than trusting what was intended.
        v_ids = json.load(open(os.path.join(d, 'ids.json'), encoding='utf-8'))
        v_emb = np.load(os.path.join(d, 'embeddings.npy'), mmap_mode='r')
        n_desc = sum(1 for _ in open(os.path.join(d, 'descriptions.jsonl'), encoding='utf-8'))
        if not (len(v_ids) == v_emb.shape[0] == n_desc):
            raise SystemExit(f'{lang}: slice is inconsistent '
                             f'({len(v_ids)} ids, {v_emb.shape[0]} rows, {n_desc} descriptions)')

        flagged = sum(1 for i in slice_ids
                      if (recs[i].get('desc') or {}).get('names_in_text') is False)
        manifest = dict(BUILD)
        manifest.update({
            'language': lang,
            'windows': len(v_ids),
            'embedding_dim': int(v_emb.shape[1]),
            'licence': short,
            'descriptions_with_unverified_names': flagged,
            'files': {f: {'bytes': os.path.getsize(os.path.join(d, f)),
                          'sha256': sha256(os.path.join(d, f))}
                      for f in ('ids.json', 'embeddings.npy', 'descriptions.jsonl')},
            'reassembly': ('Concatenate slices with scripts/merge_index.py, which '
                           'checks that ids and embedding rows stay in lockstep and '
                           'refuses to write if they do not.'),
        })
        json.dump(manifest, open(os.path.join(d, 'MANIFEST.json'), 'w'), indent=1)

        size = sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d))
        index_of[lang] = {'windows': len(v_ids), 'bytes': size, 'licence': short}
        print(f'  {lang}: {len(v_ids):,} windows, {size/1e6:.0f} MB, {short}')

    json.dump(index_of, open(os.path.join(OUT, 'index.json'), 'w'), indent=1)
    print(f'\nwritten: {OUT}')


if __name__ == '__main__':
    main()
