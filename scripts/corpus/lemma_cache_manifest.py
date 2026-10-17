#!/usr/bin/env python3
"""Write and check a version manifest for a lemma cache folder.

A lemma cache file records the hash of its text but nothing about the lemma
tables or the tokenizer that produced it, so a cache built before a table
change looks exactly like a current one (2026-10-17: 697 Latin caches predated
the last table change and nobody could tell without rebuilding). This script
writes MANIFEST.json beside the language folders (la/, grc/ ...) and later
compares it with the tables and tokenizer in a checkout.

  write:  python scripts/corpus/lemma_cache_manifest.py write CACHE_DIR \\
              --builder scripts/rebuild_lemma_cache.py [--repo ROOT] \\
              [--interpreter PATH] [--fallbacks none] [--differing-share la=11.68 grc=4.79]
  check:  python scripts/corpus/lemma_cache_manifest.py --check CACHE_DIR [--repo ROOT]
          prints "in step" (exit 0) or "stale: <reasons>" (exit 1)

It is standalone. No shared stale-stores check exists yet to attach it to.
It reads and hashes files and writes only MANIFEST.json in CACHE_DIR.
"""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MANIFEST_NAME = 'MANIFEST.json'
TABLES = ('data/lemma_tables/latin_lemmas.json',
          'data/lemma_tables/greek_lemmas.json',
          'data/lemma_tables/greek_koine_lemmas.json',
          'data/lemma_tables/greek_classical_lemmas.json')
TOKENIZER = 'backend/text_processor.py'


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def describe_file(repo, rel):
    path = os.path.join(repo, rel)
    if not os.path.exists(path):
        return {'path': rel, 'sha256': None, 'modified': None}
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec='seconds')
    return {'path': rel, 'sha256': sha256_of(path), 'modified': mtime}


def count_files(cache_dir):
    """Cache files (*.json) in each language folder under cache_dir."""
    counts = {}
    for name in sorted(os.listdir(cache_dir)):
        sub = os.path.join(cache_dir, name)
        if os.path.isdir(sub) and not name.startswith('.'):
            counts[name] = len([f for f in os.listdir(sub) if f.endswith('.json')])
    return counts


def git_commit(repo):
    try:
        return subprocess.run(['git', '-C', repo, 'rev-parse', 'HEAD'], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def build_manifest(cache_dir, repo=DEFAULT_REPO, builder=None, interpreter=None,
                   fallbacks=None, differing_share=None):
    return {
        'built': datetime.datetime.now().isoformat(timespec='seconds'),
        'builder': builder,
        'code_commit': git_commit(repo),
        'tables': [describe_file(repo, rel) for rel in TABLES],
        'tokenizer': describe_file(repo, TOKENIZER),
        'interpreter': interpreter or sys.executable,
        'fallbacks': fallbacks,
        'file_counts': count_files(cache_dir),
        'differing_share_percent_of_lines': differing_share or {},
    }


def write_manifest(cache_dir, **kwargs):
    manifest = build_manifest(cache_dir, **kwargs)
    path = os.path.join(cache_dir, MANIFEST_NAME)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write('\n')
    return path


def check_manifest(cache_dir, repo=DEFAULT_REPO):
    """Return a list of reasons the cache is stale (empty list means in step)."""
    path = os.path.join(cache_dir, MANIFEST_NAME)
    if not os.path.exists(path):
        return ['no %s in %s' % (MANIFEST_NAME, cache_dir)]
    with open(path, encoding='utf-8') as f:
        manifest = json.load(f)
    reasons = []
    recorded = [manifest.get('tokenizer') or {}] + list(manifest.get('tables') or [])
    for entry in recorded:
        rel = entry.get('path')
        if not rel:
            continue
        now = describe_file(repo, rel)
        if now['sha256'] != entry.get('sha256'):
            reasons.append('%s changed since the build (built against %s, now %s)'
                           % (rel, (entry.get('sha256') or 'missing')[:12], (now['sha256'] or 'missing')[:12]))
    return reasons


def count_notes(cache_dir, manifest):
    """Informational only: how the file counts moved since the build. A corpus that grows
    adds cache files built under the same tables, which is not staleness, so a count
    difference is reported beside the verdict and never turns it."""
    counts = count_files(cache_dir)
    notes = []
    for lang, n in (manifest.get('file_counts') or {}).items():
        if counts.get(lang) != n:
            notes.append('%s holds %s cache files, %s at the build' % (lang, counts.get(lang), n))
    return notes


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--check', action='store_true', help='compare the manifest in CACHE_DIR with the current tables and tokenizer')
    ap.add_argument('args', nargs='+', help='write CACHE_DIR, or with --check: CACHE_DIR')
    ap.add_argument('--repo', default=DEFAULT_REPO)
    ap.add_argument('--builder')
    ap.add_argument('--interpreter')
    ap.add_argument('--fallbacks')
    ap.add_argument('--differing-share', nargs='*', default=[], metavar='LANG=PERCENT')
    ns = ap.parse_args(argv)
    if ns.check:
        if len(ns.args) != 1:
            ap.error('usage: --check CACHE_DIR')
        cache_dir = ns.args[0]
        reasons = check_manifest(cache_dir, ns.repo)
        manifest_path = os.path.join(cache_dir, MANIFEST_NAME)
        notes = []
        if os.path.exists(manifest_path):
            with open(manifest_path, encoding='utf-8') as f:
                notes = count_notes(cache_dir, json.load(f))
        if reasons:
            print('stale: ' + '; '.join(reasons))
            return 1
        print('in step' + ('; ' + '; '.join(notes) if notes else ''))
        return 0
    if ns.args[0] != 'write' or len(ns.args) != 2:
        ap.error('usage: write CACHE_DIR [options], or --check CACHE_DIR')
    shares = {}
    for item in ns.differing_share:
        lang, _, pct = item.partition('=')
        shares[lang] = float(pct)
    print(write_manifest(ns.args[1], repo=ns.repo, builder=ns.builder, interpreter=ns.interpreter,
                         fallbacks=ns.fallbacks, differing_share=shares))
    return 0


if __name__ == '__main__':
    sys.exit(main())
