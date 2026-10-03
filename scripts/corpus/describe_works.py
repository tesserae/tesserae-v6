#!/usr/bin/env python3
"""One-off batch: write a per-text blurb for every work that has none.

data/text_descriptions.json maps language -> work id -> blurb (Browse Corpus,
the Reader). ~698 Latin, 843 Greek, 42 English works have none. GLM 5.3 Flash
writes each blurb from the work's opening lines and source record; Qwen 3.8
checks it for contradictions against the same inputs; only checked-ok
blurbs get merged. Run from ~/tesserae-blurbs, never /var/www.
Key: ~/.config/tesserae/bullsai.env, never written out. Modes (resume-safe
over their own JSONL log under ~/tesserae-backups/jobs/blurbs_2026-09-30/):
  (no flag)  write blurbs -> blurbs.jsonl   [--lang en|la|grc] [--limit N]
  --check    Qwen flags contradictions -> checks.jsonl   [--limit N]
  --merge    NEW data/text_descriptions.json, new blurbs sorted after the rest, kept only where checked ok

Run 2026-09-30; counts and checks are in CHANGELOG.md and DATA_OPERATIONS.md.
"""
import argparse, difflib, json, os, re, sys, threading, time  # noqa: E401
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from backend.utils import format_display_name  # noqa: E402
from backend.work_names import base_work  # noqa: E402

GATEWAY = 'https://gateway.bullsai.buffalo.edu/v1/chat/completions'
WRITE_MODEL = 'zai-org/GLM-5.3-Flash'
CHECK_MODEL = 'Qwen/Qwen3.8-27B-FP8'
FIRST_RUN_DIR = os.path.expanduser('~/tesserae-backups/jobs/blurbs_2026-09-30')
# Second pass (2026-10-01): BLURBS_JOB_DIR points the logs at a new folder, BLURBS_OPENING_LINES and
# BLURBS_OPENING_CHARS give the writer a longer excerpt, and --second-pass restricts the work set to
# the blurbs the first run's check held back.
JOB_DIR = os.environ.get('BLURBS_JOB_DIR', FIRST_RUN_DIR)
OPENING_LINES = int(os.environ.get('BLURBS_OPENING_LINES', '40'))
OPENING_CHARS = int(os.environ.get('BLURBS_OPENING_CHARS', '3000'))
SAMPLE_WHOLE = os.environ.get('BLURBS_SAMPLE_WHOLE') == '1'
# BLURBS_WHOLE=1: the complete text of the work goes to the model (every part file, in order),
# up to BLURBS_WHOLE_CHARS; a longer work is cut to equal thirds from its start, middle and end.
WHOLE = os.environ.get('BLURBS_WHOLE') == '1'
WHOLE_CHARS = int(os.environ.get('BLURBS_WHOLE_CHARS', '450000'))
BLURBS_PATH = os.path.join(JOB_DIR, 'blurbs.jsonl')
CHECKS_PATH = os.path.join(JOB_DIR, 'checks.jsonl')
LANGS = ['en', 'la', 'grc']

SYS_WRITE = (
    "You write short orientation blurbs for a corpus of classical and literary texts used by scholars "
    "hunting textual parallels. Given a work's language, author, title, source record, genre/era/meter "
    "if known, its opening lines, total line count and number of book files, write two to four sentences "
    "of plain scholarly English saying what the text is, roughly when and by whom, and what it contains "
    "as a whole, in proportion: at most one sentence on how it opens, the rest on the work's full course and contents. "
    "Describe, do not recommend: say nothing about who should read it, why anyone would care, what it "
    "offers readers or scholars, or its value for any purpose; no sentence about intertexts, parallels, "
    "allusion-hunting or comparison. Do not name the edition, editor or line count unless the work's "
    "identity depends on it. Rules: no first person; never call it 'this text'; no hedging "
    "like 'it is believed'; no bullet points; no citations of modern scholarship; never invent a specific "
    "date or author fact the inputs do not give -- where the date or author is uncertain in the inputs, "
    "say so plainly ('of uncertain date', 'attributed to') or leave it out. Use British or American "
    "spelling consistently within the blurb. Reply with JSON only: {\"blurb\": \"...\"}")
SYS_CHECK = (
    "You fact-check a short orientation blurb for a classical-text corpus against the inputs it was written "
    "from: the opening excerpt, the author and title from the source record, the language, era, and genre "
    "row. Does the blurb CONTRADICT any of those inputs, or state something a reference work would not say "
    "about this text? List only contradictions and implausible specifics: a wrong author or title, a wrong "
    "language or century, a plot or contents claim at odds with the opening, an invented companion work. A "
    "true detail beyond the excerpt, of the kind a reference entry gives, is NOT a flag. Reply with JSON "
    "only: {\"unsupported\": [\"...\"], \"ok\": true or false}")

def api_key():
    for line in open(os.path.expanduser('~/.config/tesserae/bullsai.env'), encoding='utf-8'):
        if line.startswith('BULLSAI_API_KEY='):
            return line.split('=', 1)[1].strip()
    raise SystemExit('no BullsAI key found')
KEY = api_key()

def ask(model, system, user, max_tokens, extra=None):  # one call; parsed JSON object, or None to retry
    body = {'model': model, 'max_tokens': max_tokens,
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}], **(extra or {})}
    req = urllib.request.Request(GATEWAY, data=json.dumps(body).encode('utf-8'), headers={
        'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as r:  # nosec B310
        content = json.loads(r.read())['choices'][0]['message'].get('content') or ''
    m = re.search(r'\{.*\}', content.strip(), re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except ValueError:
        return None

def ask_with_retries(model, system, user, max_tokens, extra=None, tries=3):
    for i in range(tries):  # a retry gets more room: reasoning sometimes eats the token budget
        try:
            obj = ask(model, system, user, max_tokens + i * 1000, extra)
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', 'replace')[:300] if hasattr(e, 'read') else ''
            if e.code == 429 and 'udget' in body:
                sys.stderr.write(f'STOP: quota exhausted: {body}\n')
                os._exit(3)  # the key's daily budget is spent; nothing more will succeed today
            obj = None
        except Exception:  # noqa: BLE001
            obj = None
        if obj is not None:
            return obj
        time.sleep(2)
    return None

def norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', (s or '').lower()).strip()
TAG_RE = re.compile(r'^<[^>]*>\s*')  # citation tag: tab-delimited in some corpora, space-delimited in others
def strip_tag(line):
    return TAG_RE.sub('', line.rstrip('\n'), count=1)
def count_lines(path):
    return sum(1 for _ in open(path, encoding='utf-8', errors='replace'))

def load_text_sources():
    entries = [e for e in json.load(open(os.path.join(ROOT, 'backend', 'text_sources.json'), encoding='utf-8'))
               if isinstance(e, dict)]
    by_author, by_pair = {}, {}
    for e in entries:
        a, w = norm(e.get('author', '')), norm(e.get('work', ''))
        by_author.setdefault(a, []).append(e)
        by_pair.setdefault((a, w), []).append(e)
    return by_pair, by_author

def match_source(by_pair, by_author, author_disp, work_disp):
    a, w = norm(author_disp), norm(work_disp)
    if (a, w) in by_pair:
        return by_pair[(a, w)][0]
    cands = by_author.get(a, [])
    if len(cands) == 1:
        return cands[0]
    if cands:
        best = max(cands, key=lambda e: difflib.SequenceMatcher(None, w, norm(e.get('work', ''))).ratio())
        if difflib.SequenceMatcher(None, w, norm(best.get('work', ''))).ratio() >= 0.55:
            return best
    return None

def load_genres():
    rows = {}
    with open(os.path.join(ROOT, 'data', 'text_genres.csv'), encoding='utf-8') as fh:
        header = fh.readline().strip().split(',')
        for line in fh:
            row = dict(zip(header, line.rstrip('\n').split(',')))
            rows[row.get('filename', '')] = row
    return rows

def part_n(fn, work):
    m = re.match(re.escape(work) + r'\.part\.(\d+)', fn)
    return int(m.group(1)) if m else 10**9

def build_input(lang, work, work_files, genres, by_pair, by_author):
    d = os.path.join(ROOT, 'texts', lang)
    whole = f'{work}.tess'
    parts = sorted((f for f in work_files if '.part.' in f), key=lambda f: part_n(f, work))
    if whole in work_files:
        primary, total_lines = whole, count_lines(os.path.join(d, whole))
    elif parts:
        primary = parts[0]
        total_lines = sum(count_lines(os.path.join(d, f)) for f in parts)
    else:
        primary = sorted(work_files)[0]
        total_lines = count_lines(os.path.join(d, primary))
    lines, chars = [], 0  # cap by chars too: a prose "line" can be a whole paragraph
    with open(os.path.join(d, primary), encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            text = strip_tag(raw).strip()
            if text:
                lines.append(text)
                chars += len(text)
            if len(lines) >= OPENING_LINES or chars >= OPENING_CHARS:
                break
    if WHOLE:
        order = parts if parts else [primary]
        full = []
        for f in order:
            full.extend(t for t in (strip_tag(r).strip() for r in open(os.path.join(d, f), encoding='utf-8', errors='replace')) if t)
        text_all = '\n'.join(full)
        if len(text_all) > WHOLE_CHARS:
            third = WHOLE_CHARS // 3; mid = len(text_all) // 2
            text_all = (text_all[:third] + '\n[... omitted ...]\n' + text_all[mid - third // 2: mid + third // 2]
                        + '\n[... omitted ...]\n' + text_all[-third:])
        lines = text_all.split('\n')
    elif SAMPLE_WHOLE:
        # The opening alone makes the model describe the opening (2026-10-02,
        # a fifth of blurb sentences were about it): add a slice from the
        # middle and one from the end of the work's last file, marked.
        last = parts[-1] if parts else primary
        all_lines = [strip_tag(r).strip() for r in open(os.path.join(d, last), encoding='utf-8', errors='replace')]
        all_lines = [t for t in all_lines if t]
        mid_src = [strip_tag(r).strip() for r in open(os.path.join(d, parts[len(parts) // 2] if parts else primary), encoding='utf-8', errors='replace')]
        mid_src = [t for t in mid_src if t]
        half = max(OPENING_LINES // 4, 10)
        mid = mid_src[len(mid_src) // 2: len(mid_src) // 2 + half]
        end = all_lines[-half:]
        lines = lines[:OPENING_LINES // 2] + ['[... from the middle of the work ...]'] + mid + ['[... the end of the work ...]'] + end
    author_raw = work.split('.')[0]
    author_disp = format_display_name(author_raw)
    work_disp = format_display_name(work[len(author_raw) + 1:] if '.' in work else work)
    source = match_source(by_pair, by_author, author_disp, work_disp) or {}
    genre_row = genres.get(primary) or next((genres[f] for f in work_files if f in genres), None)
    return {'language': lang, 'work': work, 'author': author_disp, 'title': work_disp,
            'print_source': source.get('print_source'), 'genre_row': genre_row,
            'opening_lines': lines, 'total_lines': total_lines, 'num_book_files': len(parts)}

def render_user_prompt(inp):
    g = inp.get('genre_row') or {}
    lines = [f"Language: {inp['language']}", f"Author (from filename): {inp['author']}",
             f"Title (from filename): {inp['title']}"]
    if inp.get('print_source'):
        lines.append(f"Print source / edition: {inp['print_source']}")
    if g:
        lines.append(f"Era: {g.get('era', '')}; meter: {g.get('meter', '')}; genre: {g.get('genre', '')}")
    lines.append(f"Total lines in the work: {inp['total_lines']}")
    lines.append(f"Number of book files: {inp['num_book_files']}")
    if WHOLE:
        lines.append("The complete text (cut to its beginning, middle and end where marked):\n" + '\n'.join(inp['opening_lines']))
    else:
        label = "Excerpts (the opening, a passage from the middle, the end):" if SAMPLE_WHOLE else "Opening lines:"
        lines.append(label + "\n" + '\n'.join(inp['opening_lines'][:OPENING_LINES + 2 + 2 * max(OPENING_LINES // 4, 10)]))
    return '\n'.join(lines)

def scope_for_lang(lang, existing_works):
    d = os.path.join(ROOT, 'texts', lang)
    works = {}
    for f in os.listdir(d):
        if f.endswith('.tess'):
            works.setdefault(base_work(f), []).append(f)
    return [w for w in sorted(works) if w not in existing_works], works

def jsonl_latest(path, key_field):
    latest = {}
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if key_field in r:
                latest[(r['language'], r['work'])] = r
    return latest

def run_pool(todo, worker, out_path, concurrency, tally):
    """Map worker over todo, appending JSONL to out_path; tally(rec) names the outcome bucket to count."""
    lock, counts, t0 = threading.Lock(), Counter(), time.time()
    with open(out_path, 'a', encoding='utf-8') as fh, ThreadPoolExecutor(concurrency) as ex:
        for k, rec in enumerate(ex.map(worker, todo), 1):
            with lock:
                fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
                fh.flush()
                counts[tally(rec)] += 1
                if k % 20 == 0 or k == len(todo):
                    rate = k / (time.time() - t0)
                    print(f'[{k}/{len(todo)}] {dict(counts)} {rate:.2f}/s', flush=True)
    print(f'DONE: {dict(counts)}, {(time.time()-t0)/60:.1f} min', flush=True)

def describe_one(inp):
    t0 = time.time()
    obj = ask_with_retries(WRITE_MODEL, SYS_WRITE, render_user_prompt(inp), int(os.environ.get("BLURBS_WRITE_TOKENS", "2500")))
    base = {'language': inp['language'], 'work': inp['work'], 'author': inp['author'], 'title': inp['title']}
    if obj and obj.get('blurb'):
        return {**base, 'blurb': obj['blurb'].strip(), 'model': WRITE_MODEL, 'ms': int((time.time() - t0) * 1000)}
    return {**base, 'error': 'no parseable blurb', 'model': WRITE_MODEL}

def cmd_write(args):
    os.makedirs(JOB_DIR, exist_ok=True)
    existing = json.load(open(os.path.join(ROOT, 'data', 'text_descriptions.json'), encoding='utf-8'))
    done = set(jsonl_latest(BLURBS_PATH, 'blurb'))
    genres = load_genres()
    by_pair, by_author = load_text_sources()
    held = None
    if getattr(args, 'rewrite_all', False):
        # Every work in scope, with or without a blurb: the neutral rewrite of 2026-10-02.
        existing = {lang: {} for lang in LANGS}
    if getattr(args, 'only_file', None):
        # A retry over named works: lines of "<lang>\t<work>" (the neutral rewrite's flagged and missing ones).
        held = {tuple(l.rstrip('\n').split('\t')) for l in open(args.only_file, encoding='utf-8') if '\t' in l}
        existing = {lang: {} for lang in LANGS}
        print(f'retry: {len(held)} works listed', flush=True)
    if getattr(args, 'second_pass', False):
        first = jsonl_latest(os.path.join(FIRST_RUN_DIR, 'checks.jsonl'), 'ok')
        held = {k for k, r in first.items() if not r.get('ok')}
        print(f'second pass: {len(held)} works held back by the first run', flush=True)
    todo = []
    for lang in ([args.lang] if args.lang else LANGS):
        works_todo, works = scope_for_lang(lang, existing.get(lang, {}))
        for work in works_todo:
            if (lang, work) in done:
                continue
            if held is not None and (lang, work) not in held:
                continue
            inp = build_input(lang, work, works[work], genres, by_pair, by_author)
            if not inp['opening_lines']:
                print(f'SKIP (empty text): {lang} {work}', flush=True)
                continue
            todo.append(inp)
    todo = todo[:args.limit] if args.limit else todo
    print(f'{len(todo)} works to describe ({len(done)} already done)', flush=True)
    run_pool(todo, describe_one, BLURBS_PATH, args.concurrency, lambda r: 'blurb' if 'blurb' in r else 'error')

def check_one(rec, genres, by_pair, by_author):
    d = os.path.join(ROOT, 'texts', rec['language'])
    files = [f for f in os.listdir(d) if f.endswith('.tess') and base_work(f) == rec['work']]
    inp = build_input(rec['language'], rec['work'], files, genres, by_pair, by_author)
    user = render_user_prompt(inp) + f"\n\nBlurb to check:\n{rec['blurb']}"
    obj = ask_with_retries(CHECK_MODEL, SYS_CHECK, user, 400,
                            extra={'chat_template_kwargs': {'enable_thinking': False}})
    base = {'language': rec['language'], 'work': rec['work']}
    if obj is not None and 'ok' in obj:
        return {**base, 'unsupported': obj.get('unsupported') or [], 'ok': bool(obj['ok'])}
    return {**base, 'unsupported': [], 'ok': False, 'error': 'no parseable check'}

def cmd_check(args):
    blurbs = jsonl_latest(BLURBS_PATH, 'blurb')
    checked = set(jsonl_latest(CHECKS_PATH, 'ok'))
    genres = load_genres()
    by_pair, by_author = load_text_sources()
    todo = [rec for key, rec in blurbs.items() if key not in checked]
    todo = todo[:args.limit] if args.limit else todo
    print(f'{len(blurbs)} blurbs, {len(checked)} already checked, {len(todo)} to check', flush=True)
    tally = lambda r: 'error' if r.get('error') else ('ok' if r['ok'] else 'flagged')  # noqa: E731
    run_pool(todo, lambda r: check_one(r, genres, by_pair, by_author), CHECKS_PATH, args.concurrency, tally)

def cmd_merge(args):
    out_path = os.path.join(ROOT, 'data', 'text_descriptions.json')
    existing = json.load(open(out_path, encoding='utf-8'))
    blurbs, checks = jsonl_latest(BLURBS_PATH, 'blurb'), jsonl_latest(CHECKS_PATH, 'ok')
    added, held_back = {}, []
    replace = getattr(args, 'replace_existing', False)
    for (lang, work), rec in blurbs.items():
        if work in existing.get(lang, {}) and not replace:
            continue
        chk = checks.get((lang, work))
        if chk and chk.get('ok') and not chk.get('error'):
            added.setdefault(lang, {})[work] = rec['blurb']
        else:
            reason = 'no ok check' if not chk else 'flagged: ' + '; '.join(chk.get('unsupported', []))
            held_back.append((lang, work, reason))
    for lang, new_works in added.items():
        existing.setdefault(lang, {})
        for work in sorted(new_works):
            existing[lang][work] = new_works[work]
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(existing, indent=1, ensure_ascii=False) + '\n')
    print('\n'.join(f'{lang}: added {len(added.get(lang, {}))}' for lang in LANGS))
    print(f'held back: {len(held_back)}')
    print('\n'.join(f'  {h}' for h in held_back[:30]))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lang', choices=LANGS)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--concurrency', type=int, default=16)
    for flag in ('--check', '--merge', '--second-pass', '--rewrite-all', '--replace-existing'):
        ap.add_argument(flag, action='store_true')
    ap.add_argument('--only-file')
    args = ap.parse_args()
    (cmd_merge if args.merge else cmd_check if args.check else cmd_write)(args)

if __name__ == '__main__':
    main()
