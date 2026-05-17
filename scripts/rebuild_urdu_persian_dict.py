#!/usr/bin/env python3
"""
Rebuild Urdu-Persian dictionary from lemmatized index data + English pivot.

Run AFTER Persian index is built (so we have lemmatized Persian forms).

Three sources:
1. Lemma overlap: normalized lemmas appearing in both Urdu and Persian indexes
2. Surface overlap: normalized surface tokens (catches proper nouns, Arabic loanwords)
3. English pivot: Steingass Persian-English + Platts Urdu-English via shared English glosses
   (if available; falls back to FarsNet/Urdu WordNet if we can find them)
"""

import csv, json, os, re, sys, unicodedata, sqlite3
from collections import Counter, defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

def normalize(text):
    text = re.sub(r'[\u0617-\u061A\u064B-\u0652\u0670]', '', text)
    text = re.sub(r'[أإآٱ]', 'ا', text)
    text = text.replace('\u06CC', '\u064A')
    text = text.replace('ى', 'ي')
    text = text.replace('\u06A9', '\u0643')
    text = text.replace('\u200C', '')
    text = text.replace('\u0640', '')
    return text.strip()

def get_index_lemmas(db_path):
    """Get all unique lemmas from an inverted index."""
    lemmas = Counter()
    if not os.path.exists(db_path):
        return lemmas
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT lemma FROM postings')
    for (lemma,) in c.fetchall():
        if lemma and len(lemma) > 1:
            lemmas[normalize(lemma)] += 1
    conn.close()
    return lemmas

def get_surface_tokens(texts_dir):
    """Get normalized surface tokens from .tess files."""
    vocab = Counter()
    for f in os.listdir(texts_dir):
        if not f.endswith('.tess'): continue
        with open(os.path.join(texts_dir, f), 'r', encoding='utf-8') as fh:
            for line in fh:
                m = re.match(r'^<[^>]+>\t(.+)$', line.strip())
                if not m: continue
                tokens = re.findall(r'[\u0600-\u06FF\u0750-\u077F\u200C]+', m.group(1))
                for t in tokens:
                    n = normalize(t)
                    if n and len(n) > 1:
                        vocab[n] += 1
    return vocab

def main():
    fa_index = os.path.join(PROJECT_ROOT, 'data', 'inverted_index', 'fa_index.db')
    ur_index = os.path.join(PROJECT_ROOT, 'data', 'inverted_index', 'ur_index.db')
    fa_texts = os.path.join(PROJECT_ROOT, 'texts', 'fa')
    ur_texts = os.path.join(PROJECT_ROOT, 'texts', 'ur')

    # Source 1: Lemma overlap from indexes
    print("Loading Persian index lemmas...")
    fa_lemmas = get_index_lemmas(fa_index)
    print(f"  Persian lemmas: {len(fa_lemmas)}")

    print("Loading Urdu index lemmas...")
    ur_lemmas = get_index_lemmas(ur_index)
    print(f"  Urdu lemmas: {len(ur_lemmas)}")

    lemma_overlap = set(fa_lemmas.keys()) & set(ur_lemmas.keys())
    lemma_pairs = set()
    for word in lemma_overlap:
        if fa_lemmas[word] >= 2 and ur_lemmas[word] >= 2:
            lemma_pairs.add((word, word))
    print(f"  Lemma overlap (freq>=2 both sides): {len(lemma_pairs)}")

    # Source 2: Surface token overlap
    print("Loading Persian surface tokens...")
    fa_surface = get_surface_tokens(fa_texts)
    print(f"  Persian surface forms: {len(fa_surface)}")

    print("Loading Urdu surface tokens...")
    ur_surface = get_surface_tokens(ur_texts)
    print(f"  Urdu surface forms: {len(ur_surface)}")

    surface_overlap = set(fa_surface.keys()) & set(ur_surface.keys())
    surface_pairs = set()
    for word in surface_overlap:
        if fa_surface[word] >= 2 and ur_surface[word] >= 2:
            surface_pairs.add((word, word))
    print(f"  Surface overlap (freq>=2 both sides): {len(surface_pairs)}")

    # Source 3: Curated literary vocabulary
    literary = {
        # Ghazal terminology
        'غزل', 'قصيده', 'رباعي', 'مثنوي', 'ديوان', 'بيت', 'مصرع', 'رديف', 'قافيه',
        # Nature imagery
        'گل', 'بلبل', 'باغ', 'چمن', 'صحرا', 'دريا', 'بحر', 'كوه', 'دشت',
        'شمع', 'پروانه', 'آتش', 'آب', 'خاك', 'باد', 'هوا',
        'آسمان', 'زمين', 'ماه', 'ستاره', 'شب', 'روز', 'صبح', 'شام', 'بهار', 'خزان',
        # Emotions
        'عشق', 'محبت', 'غم', 'شادي', 'اشك', 'خنده', 'درد', 'فراق', 'وصال',
        'آرزو', 'اميد', 'حسرت', 'حيرت',
        # Body/beauty
        'نگاه', 'چشم', 'لب', 'رخ', 'زلف', 'قد', 'قامت', 'ابرو', 'خال',
        # Wine/tavern
        'ساقي', 'مي', 'جام', 'ميخانه', 'شراب', 'مستي', 'خمار', 'پيمانه',
        # Religious/Sufi
        'خدا', 'رسول', 'نبي', 'فرشته', 'جنت', 'دوزخ', 'صوفي', 'عارف', 'معرفت',
        'حقيقت', 'مجاز', 'فنا', 'بقا', 'توحيد', 'ذكر',
        # Social
        'سلطان', 'شاه', 'وزير', 'درويش', 'فقير', 'رند', 'زاهد',
        # Abstract
        'عقل', 'علم', 'حكمت', 'خيال', 'فكر', 'روح', 'نفس',
        'مرگ', 'زندگي', 'حيات', 'وطن', 'آزادي', 'قيامت',
    }
    literary_pairs = set()
    for word in literary:
        n = normalize(word)
        if n and len(n) > 1:
            literary_pairs.add((n, n))
    print(f"  Curated literary vocabulary: {len(literary_pairs)}")

    # Source 4: English pivot via Wiktionary (CC BY-SA)
    # Persian-English and Urdu-English from Kaikki/Wiktionary extracts
    pivot_pairs = set()
    fa_wikt = '/tmp/wikt_persian_english.jsonl'
    ur_wikt = '/tmp/wikt_urdu_english.jsonl'

    if os.path.exists(fa_wikt) and os.path.exists(ur_wikt):
        print("Building English pivot from Wiktionary data...")

        ENGLISH_STOPS = {
            'the','a','an','and','or','but','in','on','at','to','for','of','with',
            'by','from','is','are','was','were','be','been','have','has','had',
            'do','does','did','will','would','could','should','may','might',
            'not','no','this','that','it','its','he','she','they','them',
            'his','her','their','my','your','our','who','which','what',
            'also','more','some','such','only','very','just','about',
            'used','form','plural','past','verb','noun','adjective',
        }

        def extract_glosses(jsonl_path):
            """Extract word -> set of English gloss words from Wiktionary JSONL."""
            word_glosses = defaultdict(set)
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        d = json.loads(line)
                    except:
                        continue
                    word = d.get('word', '')
                    if not word:
                        continue
                    word_norm = normalize(word)
                    if not word_norm or len(word_norm) < 2:
                        continue
                    for sense in d.get('senses', []):
                        for gloss in sense.get('glosses', []):
                            # Extract individual English words from the gloss
                            for eng in re.split(r'[,;/\s()\[\]"]+', gloss.lower()):
                                eng = re.sub(r'[^a-z]', '', eng)
                                if eng and len(eng) > 3 and eng not in ENGLISH_STOPS:
                                    word_glosses[word_norm].add(eng)
            return word_glosses

        fa_glosses = extract_glosses(fa_wikt)
        ur_glosses = extract_glosses(ur_wikt)
        print(f"  Persian words with English glosses: {len(fa_glosses)}")
        print(f"  Urdu words with English glosses: {len(ur_glosses)}")

        # Build reverse maps
        eng_to_fa = defaultdict(set)
        for fa_word, eng_set in fa_glosses.items():
            for eng in eng_set:
                eng_to_fa[eng].add(fa_word)

        eng_to_ur = defaultdict(set)
        for ur_word, eng_set in ur_glosses.items():
            for eng in eng_set:
                eng_to_ur[eng].add(ur_word)

        # Pivot: Urdu-Persian pairs sharing an English gloss
        # Specificity filter: English word maps to <= 10 words on each side
        for eng in eng_to_ur:
            if eng in eng_to_fa:
                ur_words = eng_to_ur[eng]
                fa_words = eng_to_fa[eng]
                if len(ur_words) <= 10 and len(fa_words) <= 10:
                    for ur in ur_words:
                        for fa in fa_words:
                            pivot_pairs.add((ur, fa))

        print(f"  English-pivot pairs: {len(pivot_pairs)}")
    else:
        print("Wiktionary data not found, skipping English pivot")
        print(f"  Expected: {fa_wikt} and {ur_wikt}")

    # Merge all sources
    merged = lemma_pairs | surface_pairs | literary_pairs | pivot_pairs
    print(f"\nMerged dictionary: {len(merged)}")
    print(f"  From lemma overlap: {len(lemma_pairs)}")
    print(f"  From surface overlap: {len(surface_pairs)} ({len(surface_pairs - lemma_pairs)} new)")
    print(f"  From literary curation: {len(literary_pairs)} ({len(literary_pairs - lemma_pairs - surface_pairs)} new)")
    print(f"  From English pivot: {len(pivot_pairs)} ({len(pivot_pairs - lemma_pairs - surface_pairs - literary_pairs)} new)")

    # Write
    out = os.path.join(PROJECT_ROOT, 'backend', 'synonymy', 'v6_additions', 'urdu_persian.csv')
    with open(out, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for u, p in sorted(merged):
            writer.writerow([u, p])
    print(f"Written to {out}")

    # Sample high-value pairs (by combined frequency, excluding function words)
    fa_stops = {'از', 'در', 'را', 'بر', 'تا', 'با', 'ز', 'كه', 'چو', 'چون', 'اين', 'ان', 'او', 'من', 'تو', 'ما', 'شما', 'است', 'بود', 'شد', 'نه', 'هم', 'يا', 'اگر', 'مگر'}
    content_pairs = [(w, fa_surface.get(w,0) + ur_surface.get(w,0)) for w, _ in merged if w not in fa_stops]
    content_pairs.sort(key=lambda x: -x[1])
    print(f"\nTop content-word pairs:")
    for w, freq in content_pairs[:20]:
        print(f"  {w:20s} (combined freq: {freq})")

if __name__ == '__main__':
    main()
