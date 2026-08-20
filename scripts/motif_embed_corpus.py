"""Embed the whole corpus at motif grain with BGE-M3, into one shared multilingual
space, for the motif tracer. Overlapping multi-line windows within each text.
Throttled to run alongside the live site on Marvin; resumable (skips finished
texts); float16 to keep the index small.

  venv:  /home/ncoffee/venv_embed
  out:   backend/embeddings_bge_motif/{lang}/{stem}.npy  + {stem}.jsonl
  run:   nohup .../python scripts/motif_embed_corpus.py > <log> 2>&1 &

Window: W consecutive line-units, stride S (overlap), never crossing a text.
"""
import os, re, glob, json, time, sys

# --- throttle BEFORE importing torch: leave most cores for production (CPU only) ---
THREADS = int(os.environ.get("MOTIF_THREADS", "6"))
os.environ["OMP_NUM_THREADS"] = str(THREADS)
os.environ["MKL_NUM_THREADS"] = str(THREADS)
# offline by default (Marvin has the model cached); the GPU box sets MOTIF_ONLINE=1
# so it can download BGE-M3 from HuggingFace on first load.
if os.environ.get("MOTIF_ONLINE") != "1":
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
import numpy as np
import torch
torch.set_num_threads(THREADS)

# Auto-detect device: GPU when present (rented box), else CPU (Marvin). On GPU we
# push a much larger batch; on CPU keep it modest.
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ROOT: env override lets the GPU box point at a fresh git clone instead of Marvin's path.
ROOT = os.environ.get("MOTIF_ROOT", "/var/www/tesseraev6_flask")
TEXTS = os.path.join(ROOT, "texts")
OUT = os.environ.get("MOTIF_OUT", os.path.join(ROOT, "backend", "embeddings_bge_motif"))
MODEL = "BAAI/bge-m3"
# Motif windows are sized by WORDS, not lines: a "line" in prose is a whole
# paragraph, so line-windows blow up on prose and mis-size the motif. Two scales:
#   coarse  ~ a developed motif / type-scene (arming scene, worked-out metaphor)
#   fine    ~ a sense-beat, a sentence or two (close thematic similarity; the grain
#             that also feeds the fusion semantic layer)
# (budget_words, stride_words). ~50% overlap so a scene isn't split at a boundary.
SCALES = {
    "coarse": (150, 75),
    "fine":   (50, 25),
}
BATCH = int(os.environ.get("MOTIF_BATCH", "256" if DEVICE == "cuda" else "24"))
LANG_ORDER = ["en", "la", "grc", "cop"]   # English first: it has no embeddings today
# restrict to specific languages via MOTIF_LANGS (comma-separated), e.g. "fa" to
# embed only Persian from the persian-ship branch. Empty = all of LANG_ORDER.
_only = [x.strip() for x in os.environ.get("MOTIF_LANGS", "").split(",") if x.strip()]
if _only:
    LANG_ORDER = [l for l in (_only) if l]
# data parallelism: run N processes, each takes files where idx % SHARD_COUNT == SHARD_ID.
# BGE-M3 on CPU scales poorly past ~4 intra-op threads, so many-small-processes beats
# one-big-process. Each worker should set a modest MOTIF_THREADS (e.g. 4).
SHARD_ID = int(os.environ.get("SHARD_ID", "0"))
SHARD_COUNT = int(os.environ.get("SHARD_COUNT", "1"))
TAG_RE = re.compile(r"^<([^>]*)>\s*(.*)$")
SMOKE = "--smoke" in sys.argv

def log(msg):
    t = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{t}] {msg}"
    print(line, flush=True)

def read_units(fp):
    """returns list of (tag, text) for non-empty tagged line-units."""
    units = []
    with open(fp, encoding="utf-8") as fh:
        for ln in fh:
            m = TAG_RE.match(ln.strip())
            if m and m.group(2).strip():
                units.append((m.group(1).strip(), m.group(2).strip()))
    return units

def tokenize(units):
    """flatten a text's units into a stream of (word, tag) so windows can be sized by
    words while still reporting which line/section each window spans. Long prose
    paragraphs and short verse lines are handled uniformly."""
    stream = []
    for tag, text in units:
        for w in text.split():
            stream.append((w, tag))
    return stream

def windows(units, budget, stride):
    """yield (start_tag, end_tag, n_words, joined_text) for word-budget windows.
    Splits oversize prose units and merges short verse lines; ~budget words each,
    advancing by `stride` words (overlap = budget - stride)."""
    stream = tokenize(units)
    n = len(stream)
    if n == 0:
        return
    step = max(1, stride)
    i = 0
    while i < n:
        chunk = stream[i:i + budget]
        if not chunk:
            break
        yield (chunk[0][1], chunk[-1][1], len(chunk), " ".join(w for w, _ in chunk))
        if i + budget >= n:      # last window reached the end
            break
        i += step

def main():
    os.makedirs(OUT, exist_ok=True)
    log(f"loading {MODEL} on {DEVICE} (threads={THREADS}, batch={BATCH}) ...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL, device=DEVICE)
    log("model loaded.")

    files = []
    for lang in LANG_ORDER:
        fs = sorted(glob.glob(os.path.join(TEXTS, lang, "*.tess")))
        files += [(lang, f) for f in fs]
    if SMOKE:
        files = [(l, f) for (l, f) in files if l == "en"][:1]
        log(f"SMOKE: {files}")
    if SHARD_COUNT > 1:
        files = [pair for k, pair in enumerate(files) if k % SHARD_COUNT == SHARD_ID]
        log(f"SHARD {SHARD_ID}/{SHARD_COUNT}: {len(files)} files assigned to this worker")

    def outpaths(scale, lang, stem):
        odir = os.path.join(OUT, scale, lang)
        os.makedirs(odir, exist_ok=True)
        return os.path.join(odir, stem + ".npy"), os.path.join(odir, stem + ".jsonl")

    t0 = time.time()
    # scale-major: finish the whole corpus at the coarse (motif) scale FIRST -- it's
    # the usable-on-its-own index -- then the fine scale. SCALES is ordered coarse->fine.
    for scale, (budget, stride) in SCALES.items():
        done_texts = done_win = skipped = 0
        log(f"=== scale '{scale}' (budget={budget}, stride={stride}) over {len(files)} files ===")
        for lang, fp in files:
            stem = os.path.splitext(os.path.basename(fp))[0]
            npy, jsonl = outpaths(scale, lang, stem)
            if os.path.exists(npy) and os.path.getsize(npy) > 0:
                skipped += 1
                continue
            units = read_units(fp)
            wins = list(windows(units, budget, stride))
            if not wins:
                np.save(npy, np.zeros((0, 1024), dtype=np.float16))
                open(jsonl, "w").close()
                continue
            vecs = model.encode([w[3] for w in wins], batch_size=BATCH,
                                normalize_embeddings=True, show_progress_bar=False)
            np.save(npy, np.asarray(vecs, dtype=np.float16))
            with open(jsonl, "w", encoding="utf-8") as jh:
                for k, w in enumerate(wins):
                    jh.write(json.dumps({"i": k, "scale": scale, "start": w[0],
                                         "end": w[1], "n": w[2], "text": w[3][:200]},
                                        ensure_ascii=False) + "\n")
            done_texts += 1
            done_win += len(wins)
            if done_texts % 25 == 0 or SMOKE:
                rate = done_win / max(1e-9, time.time() - t0)
                log(f"[{scale}] {lang} {stem}: {len(wins)} win | {done_texts} texts, "
                    f"{done_win} win, {skipped} skipped, {rate:.1f} win/s")
            time.sleep(0.02)   # yield to the live site
        log(f"=== scale '{scale}' DONE: {done_texts} texts, {done_win} windows, "
            f"{skipped} already-present. elapsed {(time.time()-t0)/3600:.2f}h ===")

    log(f"ALL DONE. elapsed {(time.time()-t0)/3600:.2f}h")

if __name__ == "__main__":
    main()
