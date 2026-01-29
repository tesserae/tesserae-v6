#!/usr/bin/env python3
"""
Tesserae V6 - Local Connection Computation Script

This script computes text connections locally and outputs results to JSON/CSV
for later import into the Tesserae database.

USAGE:
    python compute_connections_local.py --language la --tier 1 --output connections_latin_t1.json
    python compute_connections_local.py --language grc --tier 2 --output connections_greek_t2.json
    python compute_connections_local.py --language la --authors vergil,ovid --output vergil_ovid.json

REQUIREMENTS:
    pip install cltk nltk

TIERS:
    1 = Major canonical authors only (~50 texts, ~1000 pairs)
    2 = Extended canonical + same-era texts (~200 texts, ~20000 pairs)  
    3 = All texts (1400+ Latin, 650+ Greek - millions of pairs, days to compute)
"""

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

TIER1_AUTHORS = {
    'la': [
        'vergil', 'ovid', 'horace', 'catullus', 'lucretius', 'propertius', 'tibullus',
        'lucan', 'statius', 'juvenal', 'martial', 'seneca', 'cicero', 'caesar',
        'livy', 'tacitus', 'sallust', 'pliny', 'suetonius', 'petronius', 'apuleius'
    ],
    'grc': [
        'homer', 'hesiod', 'pindar', 'aeschylus', 'sophocles', 'euripides',
        'aristophanes', 'herodotus', 'thucydides', 'xenophon', 'plato', 'aristotle',
        'demosthenes', 'apollonius', 'callimachus', 'theocritus'
    ],
    'en': [
        'shakespeare', 'milton', 'chaucer', 'spenser', 'donne', 'pope', 'dryden',
        'wordsworth', 'keats', 'shelley', 'byron', 'tennyson', 'browning'
    ]
}

TIER2_AUTHORS = {
    'la': TIER1_AUTHORS['la'] + [
        'plautus', 'terence', 'ennius', 'lucanus', 'valerius_flaccus', 'silius',
        'ausonius', 'claudian', 'prudentius', 'jerome', 'augustine', 'ambrose',
        'boethius', 'cassiodorus', 'isidore', 'bede', 'alcuin', 'einhard'
    ],
    'grc': TIER1_AUTHORS['grc'] + [
        'plutarch', 'lucian', 'galen', 'hippocrates', 'philo_judaeus',
        'diodorus', 'strabo', 'pausanias', 'athenaeus', 'diogenes_laertius'
    ],
    'en': TIER1_AUTHORS['en'] + [
        'marlowe', 'jonson', 'herbert', 'marvell', 'bunyan', 'defoe', 'swift',
        'fielding', 'sterne', 'johnson', 'blake', 'coleridge', 'scott'
    ]
}


def parse_text_id(filename):
    """Extract author and work from filename."""
    name = filename.replace('.tess', '')
    parts = name.split('.')
    author = parts[0] if parts else 'unknown'
    work = '.'.join(parts[1:]) if len(parts) > 1 else 'unknown'
    return author, work


def read_tess_file(filepath):
    """Read a .tess file and return list of (loc, text) tuples."""
    lines = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                match = re.match(r'<([^>]+)>\s*(.*)', line)
                if match:
                    loc, text = match.groups()
                    lines.append({'loc': loc, 'text': text})
    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
    return lines


def tokenize_latin(text):
    """Simple Latin tokenization."""
    text = text.lower()
    text = re.sub(r'[^a-z\s]', '', text)
    return text.split()


def tokenize_greek(text):
    """Simple Greek tokenization."""
    text = text.lower()
    text = re.sub(r'[^\u0370-\u03FF\u1F00-\u1FFF\s]', '', text)
    return text.split()


def tokenize_english(text):
    """Simple English tokenization."""
    text = text.lower()
    text = re.sub(r'[^a-z\s]', '', text)
    return text.split()


def get_tokenizer(language):
    """Get appropriate tokenizer for language."""
    if language == 'la':
        return tokenize_latin
    elif language == 'grc':
        return tokenize_greek
    else:
        return tokenize_english


def build_inverted_index(lines, tokenizer):
    """Build inverted index mapping tokens to line indices."""
    index = defaultdict(set)
    for i, line in enumerate(lines):
        tokens = tokenizer(line['text'])
        for token in tokens:
            index[token].add(i)
    return index


def find_shared_vocabulary(source_lines, target_lines, tokenizer, min_shared=2):
    """Find lines that share vocabulary between source and target."""
    source_index = build_inverted_index(source_lines, tokenizer)
    target_index = build_inverted_index(target_lines, tokenizer)
    
    shared_vocab = set(source_index.keys()) & set(target_index.keys())
    
    matches = []
    seen_pairs = set()
    
    for word in shared_vocab:
        for s_idx in source_index[word]:
            for t_idx in target_index[word]:
                pair_key = (s_idx, t_idx)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                
                s_tokens = set(tokenizer(source_lines[s_idx]['text']))
                t_tokens = set(tokenizer(target_lines[t_idx]['text']))
                shared = s_tokens & t_tokens & shared_vocab
                
                if len(shared) >= min_shared:
                    matches.append({
                        'source_idx': s_idx,
                        'target_idx': t_idx,
                        'source_loc': source_lines[s_idx]['loc'],
                        'target_loc': target_lines[t_idx]['loc'],
                        'shared_words': list(shared),
                        'score': len(shared)
                    })
    
    matches.sort(key=lambda x: x['score'], reverse=True)
    return matches[:500]


def compute_connection(source_path, target_path, language):
    """Compute connection between two texts."""
    tokenizer = get_tokenizer(language)
    
    source_lines = read_tess_file(source_path)
    target_lines = read_tess_file(target_path)
    
    if not source_lines or not target_lines:
        return None
    
    matches = find_shared_vocabulary(source_lines, target_lines, tokenizer)
    
    if not matches:
        return None
    
    gold = sum(1 for m in matches if m['score'] >= 10)
    silver = sum(1 for m in matches if 7 <= m['score'] < 10)
    bronze = sum(1 for m in matches if 5 <= m['score'] < 7)
    copper = sum(1 for m in matches if m['score'] < 5)
    
    strength = gold * 4 + silver * 3 + bronze * 2 + copper
    
    return {
        'total_parallels': len(matches),
        'gold_count': gold,
        'silver_count': silver,
        'bronze_count': bronze,
        'copper_count': copper,
        'connection_strength': strength,
        'top_matches': matches[:10]
    }


def get_texts_for_tier(texts_dir, language, tier, specific_authors=None):
    """Get list of text files for the specified tier."""
    lang_dir = os.path.join(texts_dir, language)
    if not os.path.exists(lang_dir):
        print(f"Error: Language directory not found: {lang_dir}", file=sys.stderr)
        return []
    
    all_texts = [f for f in os.listdir(lang_dir) if f.endswith('.tess')]
    
    if specific_authors:
        authors = [a.strip().lower() for a in specific_authors.split(',')]
        return [t for t in all_texts if parse_text_id(t)[0].lower() in authors]
    
    if tier == 1:
        tier_authors = TIER1_AUTHORS.get(language, [])
    elif tier == 2:
        tier_authors = TIER2_AUTHORS.get(language, [])
    else:
        return all_texts
    
    return [t for t in all_texts if parse_text_id(t)[0].lower() in tier_authors]


def main():
    parser = argparse.ArgumentParser(description='Compute Tesserae text connections locally')
    parser.add_argument('--language', '-l', default='la', choices=['la', 'grc', 'en'],
                        help='Language to process (la, grc, en)')
    parser.add_argument('--tier', '-t', type=int, default=1, choices=[1, 2, 3],
                        help='Author tier (1=major, 2=extended, 3=all)')
    parser.add_argument('--authors', '-a', default=None,
                        help='Specific authors (comma-separated, e.g., vergil,ovid)')
    parser.add_argument('--texts-dir', '-d', default='texts',
                        help='Path to texts directory')
    parser.add_argument('--output', '-o', default='connections.json',
                        help='Output file (JSON or CSV)')
    parser.add_argument('--resume', '-r', default=None,
                        help='Resume from checkpoint file')
    parser.add_argument('--checkpoint-interval', type=int, default=50,
                        help='Save checkpoint every N pairs')
    
    args = parser.parse_args()
    
    texts = get_texts_for_tier(args.texts_dir, args.language, args.tier, args.authors)
    
    if not texts:
        print("No texts found for the specified criteria.", file=sys.stderr)
        sys.exit(1)
    
    print(f"Found {len(texts)} texts for {args.language} tier {args.tier}")
    
    pairs = []
    seen = set()
    for s in texts:
        for t in texts:
            if s != t:
                pair_key = tuple(sorted([s, t]))
                if pair_key not in seen:
                    seen.add(pair_key)
                    pairs.append((s, t))
    
    print(f"Total pairs to compute: {len(pairs)}")
    
    completed_pairs = set()
    results = []
    
    if args.resume and os.path.exists(args.resume):
        print(f"Resuming from checkpoint: {args.resume}")
        with open(args.resume, 'r') as f:
            checkpoint = json.load(f)
            results = checkpoint.get('results', [])
            completed_pairs = set(tuple(p) for p in checkpoint.get('completed_pairs', []))
        print(f"Loaded {len(results)} existing results")
    
    lang_dir = os.path.join(args.texts_dir, args.language)
    start_time = time.time()
    
    for i, (source, target) in enumerate(pairs):
        pair_key = tuple(sorted([source, target]))
        if pair_key in completed_pairs:
            continue
        
        source_path = os.path.join(lang_dir, source)
        target_path = os.path.join(lang_dir, target)
        
        try:
            connection = compute_connection(source_path, target_path, args.language)
            
            if connection:
                source_author, source_work = parse_text_id(source)
                target_author, target_work = parse_text_id(target)
                
                result = {
                    'source_text_id': source,
                    'target_text_id': target,
                    'source_author': source_author,
                    'source_work': source_work,
                    'target_author': target_author,
                    'target_work': target_work,
                    'language': args.language,
                    **connection
                }
                del result['top_matches']
                results.append(result)
            
            completed_pairs.add(pair_key)
            
            if (i + 1) % 10 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                remaining = (len(pairs) - i - 1) / rate if rate > 0 else 0
                print(f"Progress: {i + 1}/{len(pairs)} ({rate:.1f}/s, ~{remaining/60:.1f}min remaining)")
            
            if (i + 1) % args.checkpoint_interval == 0:
                checkpoint_file = args.output.replace('.json', '_checkpoint.json')
                with open(checkpoint_file, 'w') as f:
                    json.dump({
                        'results': results,
                        'completed_pairs': [list(p) for p in completed_pairs],
                        'timestamp': datetime.now().isoformat()
                    }, f)
                print(f"Checkpoint saved: {checkpoint_file}")
                
        except Exception as e:
            print(f"Error processing {source} -> {target}: {e}", file=sys.stderr)
    
    if args.output.endswith('.csv'):
        import csv
        with open(args.output, 'w', newline='') as f:
            if results:
                writer = csv.DictWriter(f, fieldnames=results[0].keys())
                writer.writeheader()
                writer.writerows(results)
    else:
        with open(args.output, 'w') as f:
            json.dump({
                'language': args.language,
                'tier': args.tier,
                'total_connections': len(results),
                'computed_at': datetime.now().isoformat(),
                'connections': results
            }, f, indent=2)
    
    elapsed = time.time() - start_time
    print(f"\nCompleted! {len(results)} connections saved to {args.output}")
    print(f"Total time: {elapsed/60:.1f} minutes")


if __name__ == '__main__':
    main()
