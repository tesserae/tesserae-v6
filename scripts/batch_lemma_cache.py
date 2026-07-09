#!/usr/bin/env python3
"""
Rebuild lemma cache for all texts — fast version.

Skips POS tagging (which takes 5-10 min per text via CLTK tag_tnt) and sets
POS tags to 'UNK'. Core matching uses only tokens + lemmas, so this is safe.
POS tags are only used for optional feature boosts in scoring.

Uses the fast lookup tables for lemmatization with CLTK fallback only for
novel words not in the tables.

Usage:
    python scripts/batch_lemma_cache.py          # all languages
    python scripts/batch_lemma_cache.py la        # just Latin
    python scripts/batch_lemma_cache.py --force   # rebuild even if cached
"""
import sys
import os
import re
import time
import resource

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['TESSERAE_DIRECT_SERVER'] = '1'

from backend.lemma_cache import (
    get_file_hash, save_cached_units,
    get_cached_units, get_cache_stats, TEXTS_DIR
)


class FastTextProcessor:
    """Lightweight text processor that skips POS tagging for speed."""

    def __init__(self):
        from backend.text_processor import (
            get_latin_lemma_table, get_greek_lemma_table, _init_nlp_models,
            _cltk_latin_lemmatizer, _cltk_greek_lemmatizer
        )

        # Load lookup tables (fast)
        print("  Loading lemma lookup tables...")
        self.latin_table = get_latin_lemma_table()
        self.greek_table = get_greek_lemma_table()
        print(f"  Latin table: {len(self.latin_table)} entries, Greek table: {len(self.greek_table)} entries")

        # Load CLTK lemmatizers (for words not in lookup tables)
        print("  Loading CLTK lemmatizers (no POS taggers)...")
        try:
            from cltk.lemmatize.lat import LatinBackoffLemmatizer
            self.latin_lemmatizer = LatinBackoffLemmatizer()
            print("  CLTK LatinBackoffLemmatizer loaded")
        except Exception as e:
            self.latin_lemmatizer = None
            print(f"  CLTK Latin not available: {e}")

        try:
            from cltk.lemmatize.grc import GreekBackoffLemmatizer
            self.greek_lemmatizer = GreekBackoffLemmatizer()
            print("  CLTK GreekBackoffLemmatizer loaded")
        except Exception as e:
            self.greek_lemmatizer = None
            print(f"  CLTK Greek not available: {e}")

        try:
            import nltk
            nltk.download('wordnet', quiet=True)
            nltk.download('omw-1.4', quiet=True)
            from nltk.stem import WordNetLemmatizer
            self.english_lemmatizer = WordNetLemmatizer()
            print("  NLTK English lemmatizer loaded")
        except Exception as e:
            self.english_lemmatizer = None
            print(f"  NLTK English not available: {e}")

        self.lemma_cache = {}

    def tokenize_latin(self, text):
        original_text = re.sub(r'[^a-zA-Z\s]', '', text)
        original_tokens = original_text.split()
        text = text.lower().replace('j', 'i').replace('v', 'u')
        text = re.sub(r'[^a-z\s]', '', text)
        tokens = text.split()
        return original_tokens, tokens

    def tokenize_greek(self, text):
        original_text = re.sub(r'[^\u0300-\u036f\u0370-\u03ff\u1f00-\u1fff\s]', '', text)
        original_tokens = original_text.split()
        text = text.lower()
        text = re.sub(r'[^\u0300-\u036f\u0370-\u03ff\u1f00-\u1fff\s]', '', text)
        tokens = text.split()
        return original_tokens, tokens

    def tokenize_english(self, text):
        original_text = re.sub(r'[^a-zA-Z\'\s]', '', text)
        original_tokens = original_text.split()
        text = text.lower()
        text = re.sub(r'[^a-z\'\s]', '', text)
        tokens = text.split()
        return original_tokens, tokens

    def latin_lemmatize(self, tokens):
        lemmas = []
        for token in tokens:
            cache_key = f"la:{token}"
            if cache_key in self.lemma_cache:
                lemmas.append(self.lemma_cache[cache_key])
                continue

            norm = token.lower().replace('j', 'i').replace('v', 'u')
            lemma = None
            stripped_base = None

            if norm in self.latin_table:
                lemma = self.latin_table[norm]
            else:
                for enclitic in ['que', 'ne', 'ue']:
                    if norm.endswith(enclitic) and len(norm) > len(enclitic) + 1:
                        base = norm[:-len(enclitic)]
                        stripped_base = base
                        if base in self.latin_table:
                            lemma = self.latin_table[base]
                        elif base + 'm' in self.latin_table:
                            lemma = self.latin_table[base + 'm']
                        break

            if lemma is None and self.latin_lemmatizer:
                try:
                    # Try the FULL form first; the enclitic-stripped base is a
                    # heuristic that mangles words like lanugine -> lanugi.
                    result = self.latin_lemmatizer.lemmatize([token])
                    lemma = result[0][1] if result else None
                    if (lemma is None or lemma == token or lemma == norm) and stripped_base:
                        result = self.latin_lemmatizer.lemmatize([stripped_base])
                        alt = result[0][1] if result else None
                        if alt and alt != stripped_base:
                            lemma = alt
                    if lemma is None:
                        lemma = norm
                except Exception:
                    lemma = norm

            if lemma is None:
                # No CLTK: keep the full normalized form. A raw form is honest;
                # an unvalidated stripped stem is garbage (lanugine -> lanugi).
                lemma = norm

            self.lemma_cache[cache_key] = lemma
            lemmas.append(lemma)
        return lemmas

    def greek_lemmatize(self, tokens):
        lemmas = []
        for token in tokens:
            cache_key = f"grc:{token}"
            if cache_key in self.lemma_cache:
                lemmas.append(self.lemma_cache[cache_key])
                continue

            lemma = None
            if token in self.greek_table:
                lemma = self.greek_table[token]
            elif token.lower() in self.greek_table:
                lemma = self.greek_table[token.lower()]

            if lemma is None and self.greek_lemmatizer:
                try:
                    result = self.greek_lemmatizer.lemmatize([token])
                    lemma = result[0][1] if result else token
                except Exception:
                    lemma = token

            if lemma is None:
                lemma = token

            self.lemma_cache[cache_key] = lemma
            lemmas.append(lemma)
        return lemmas

    def english_lemmatize(self, tokens):
        lemmas = []
        for token in tokens:
            cache_key = f"en:{token}"
            if cache_key in self.lemma_cache:
                lemmas.append(self.lemma_cache[cache_key])
                continue

            if self.english_lemmatizer:
                try:
                    lemma = self.english_lemmatizer.lemmatize(token.lower())
                except Exception:
                    lemma = token.lower()
            else:
                lemma = token.lower()

            self.lemma_cache[cache_key] = lemma
            lemmas.append(lemma)
        return lemmas

    def _ends_sentence(self, text, language):
        text = text.rstrip()
        if not text:
            return False
        if language == 'grc':
            return text[-1] in '.;\u00b7?!'
        return text[-1] in '.;?!'

    def process_file(self, filepath, language, unit_type):
        """Process a .tess file, returns list of unit dicts (no POS tagging)."""
        # Choose tokenizer + lemmatizer
        if language == 'grc':
            tokenize = self.tokenize_greek
            lemmatize = self.greek_lemmatize
        elif language == 'en':
            tokenize = self.tokenize_english
            lemmatize = self.english_lemmatize
        else:
            tokenize = self.tokenize_latin
            lemmatize = self.latin_lemmatize

        # Read raw lines
        raw_lines = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                match = re.match(r'^<([^>]+)>\s*(.+)$', line)
                if match:
                    raw_lines.append((match.group(1), match.group(2)))

        units = []
        if unit_type == 'phrase':
            buf_refs = []
            buf_texts = []
            for ref, text in raw_lines:
                buf_refs.append(ref)
                buf_texts.append(text)
                if self._ends_sentence(text, language):
                    combined = ' '.join(buf_texts)
                    combined_ref = buf_refs[0] if len(buf_refs) == 1 else f"{buf_refs[0]}-{buf_refs[-1]}"
                    original_tokens, tokens = tokenize(combined)
                    lemmas = lemmatize(tokens)
                    units.append({
                        'ref': combined_ref,
                        'text': combined,
                        'tokens': tokens,
                        'original_tokens': original_tokens,
                        'lemmas': lemmas,
                        'pos_tags': ['UNK'] * len(tokens),
                        'line_refs': list(buf_refs),
                    })
                    buf_refs = []
                    buf_texts = []
            # Flush remaining
            if buf_refs:
                combined = ' '.join(buf_texts)
                combined_ref = buf_refs[0] if len(buf_refs) == 1 else f"{buf_refs[0]}-{buf_refs[-1]}"
                original_tokens, tokens = tokenize(combined)
                lemmas = lemmatize(tokens)
                units.append({
                    'ref': combined_ref,
                    'text': combined,
                    'tokens': tokens,
                    'original_tokens': original_tokens,
                    'lemmas': lemmas,
                    'pos_tags': ['UNK'] * len(tokens),
                    'line_refs': list(buf_refs),
                })
        else:  # line
            for ref, text in raw_lines:
                original_tokens, tokens = tokenize(text)
                lemmas = lemmatize(tokens)
                units.append({
                    'ref': ref,
                    'text': text,
                    'tokens': tokens,
                    'original_tokens': original_tokens,
                    'lemmas': lemmas,
                    'pos_tags': ['UNK'] * len(tokens),
                })
        return units


def rebuild_language(tp, language, force=False):
    lang_dir = os.path.join(TEXTS_DIR, language)
    if not os.path.exists(lang_dir):
        print(f"  No texts directory for {language}")
        return

    text_files = sorted([f for f in os.listdir(lang_dir) if f.endswith('.tess')])
    total = len(text_files)

    already_cached = 0
    to_process = []
    for f in text_files:
        if not force:
            cached = get_cached_units(f, language)
            if cached is not None:
                already_cached += 1
                continue
        to_process.append(f)

    print(f"\n{'='*60}")
    print(f"  {language.upper()}: {total} texts, {already_cached} already cached, {len(to_process)} to process")
    print(f"{'='*60}")
    sys.stdout.flush()

    if not to_process:
        print("  Nothing to do!")
        return

    start = time.time()
    processed = 0
    errors = []

    for i, text_file in enumerate(to_process):
        filepath = os.path.join(lang_dir, text_file)
        if not os.path.exists(filepath):
            continue

        try:
            file_hash = get_file_hash(filepath)
            units_line = tp.process_file(filepath, language, 'line')
            units_phrase = tp.process_file(filepath, language, 'phrase')
            save_cached_units(text_file, language, units_line, units_phrase, file_hash)
            processed += 1

            if processed % 50 == 0 or processed == 1:
                elapsed = time.time() - start
                rate = processed / elapsed if elapsed > 0 else 0
                remaining = (len(to_process) - i - 1) / rate if rate > 0 else 0
                mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
                print(f"  [{i+1}/{len(to_process)}] {text_file} — {len(units_line)} lines "
                      f"({rate:.1f}/s, ~{remaining/60:.0f}m left, {mem_mb:.0f}MB)")
                sys.stdout.flush()

        except Exception as e:
            errors.append(f"{text_file}: {str(e)}")
            print(f"  ERROR: {text_file}: {e}")
            sys.stdout.flush()

    elapsed = time.time() - start
    print(f"\n  Done {language.upper()} in {elapsed:.0f}s: {processed} built, "
          f"{already_cached} already cached, {len(errors)} errors")
    if errors:
        print(f"  First 5 errors:")
        for e in errors[:5]:
            print(f"    {e}")
    sys.stdout.flush()


def main():
    force = '--force' in sys.argv
    languages = [a for a in sys.argv[1:] if a != '--force']
    if not languages:
        languages = ['la', 'grc', 'en']

    print("Lemma Cache Rebuild (fast — no POS tagging)")
    print(f"  Force rebuild: {force}")

    stats = get_cache_stats()
    print("\nBEFORE:")
    for lang, s in stats.items():
        print(f"  {lang}: {s['cached']}/{s['total']} ({s['coverage']})")
    sys.stdout.flush()

    print("\nLoading models...")
    load_start = time.time()
    tp = FastTextProcessor()
    print(f"Models loaded in {time.time() - load_start:.0f}s")
    sys.stdout.flush()

    for lang in languages:
        rebuild_language(tp, lang, force=force)

    stats = get_cache_stats()
    print("\nAFTER:")
    for lang, s in stats.items():
        print(f"  {lang}: {s['cached']}/{s['total']} ({s['coverage']})")

    print("\nDone!")
    sys.stdout.flush()


if __name__ == '__main__':
    main()
