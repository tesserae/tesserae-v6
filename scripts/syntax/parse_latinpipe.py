"""Parse Latin lines with a LOCAL LatinPipe (latin-evalatin24-240520), in resumable chunks.

Input: a JSONL todo file, one object per line: {"id": N, "text": "..."}.
Output: a JSONL file, one object per parsed line:
  {"id": N, "tokens": [...], "lemmas": [...], "upos": [...], "heads": [...],
   "deprels": [...], "feats": [...]}
Lines already in the output are skipped, so each call continues where the last
stopped. A call stops after --budget seconds of parsing (checked between
batches) so it fits inside one foreground job.

A line the tokenizer splits into several sentences is stored as one row: the
sentences are joined in order. Heads stay sentence-local, as in the February
2026 build. --shift-heads makes them line-wide instead (a root keeps head 0).

  python parse_latinpipe.py --repo DIR --todo todo.jsonl --out out.jsonl --budget 420
"""

import argparse
import contextlib
import json
import os
import sys
import time
import unicodedata


def conllu_sentences(text):
    sents, cur = [], []
    for line in text.split("\n"):
        if not line.strip():
            if cur:
                sents.append(cur)
                cur = []
            continue
        if line.startswith("#"):
            continue
        p = line.split("\t")
        if len(p) >= 10 and p[0].isdigit():
            cur.append(
                {
                    "form": p[1],
                    "lemma": p[2].lower() if p[2] else "",
                    "upos": p[3],
                    "feats": p[5] if p[5] != "_" else "_",
                    "head": int(p[6]) if p[6] != "_" else 0,
                    "deprel": p[7] if p[7] != "_" else "",
                }
            )
    if cur:
        sents.append(cur)
    return sents


def join_sentences(sents, shift=False):
    toks, off = [], 0
    for s in sents:
        for t in s:
            t = dict(t)
            if t["head"] and shift:
                t["head"] += off
            toks.append(t)
        off += len(s)
    return toks


def row_of(i, toks):
    return {
        "id": i,
        "tokens": [t["form"] for t in toks],
        "lemmas": [t["lemma"] for t in toks],
        "upos": [t["upos"] for t in toks],
        "heads": [t["head"] for t in toks],
        "deprels": [t["deprel"] for t in toks],
        "feats": [t["feats"] for t in toks],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--repo",
        required=True,
        help="evalatin2024-latinpipe checkout with the model unpacked in it",
    )
    ap.add_argument("--model", default="latinpipe-evalatin24-240520")
    ap.add_argument("--todo", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--budget", type=float, default=420)
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--sentences-per-call", type=int, default=256)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument(
        "--shard",
        default="0/1",
        help="i/n: parse only lines whose id mod n is i, so n jobs can share one todo file",
    )
    ap.add_argument(
        "--shift-heads",
        action="store_true",
        help="shift the heads of later sentences of a line (the February build did not)",
    )
    a = ap.parse_args()
    t_start = time.time()

    done = set()
    failed_path = a.out + ".failed"
    for path in (a.out, failed_path):
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        done.add(json.loads(line)["id"])
                    except ValueError:
                        pass
    si, sn = map(int, a.shard.split("/"))
    todo = []
    with open(a.todo, encoding="utf-8") as fh:
        for line in fh:
            o = json.loads(line)
            if o["id"] not in done and o["id"] % sn == si:
                todo.append(o)
    if a.limit:
        todo = todo[: a.limit]
    print(f"todo {len(todo)} lines, {len(done)} already done", flush=True)
    if not todo:
        return

    sys.path.insert(0, a.repo)
    os.chdir(a.repo)
    import torch

    torch.set_num_threads(a.threads)
    torch.set_num_interop_threads(max(1, a.threads // 4))
    import latinpipe_evalatin24_server as srv
    from latinpipe_evalatin24 import UDDataset

    sys.modules[
        "__main__"
    ].UDDataset = (
        UDDataset  # the model's mappings.pkl was pickled from the server's __main__
    )
    mdir = os.path.join(a.repo, a.model)
    sargs = argparse.Namespace(
        default_model=a.model,
        models=[a.model, mdir, "la_evalatin24", "LatinPipe"],
        preload_models=["all"],
        batch_size=32,
        optional_semaphore=contextlib.nullcontext(),
    )
    models = srv.Models(sargs)
    model = models.models_by_names[a.model]
    writer = model.create_writer("conllu")
    print(f"model loaded after {time.time() - t_start:.0f}s", flush=True)

    out = open(a.out, "a", encoding="utf-8")
    failed = open(failed_path, "a", encoding="utf-8")

    def note_failed(lid, why):
        failed.write(json.dumps({"id": lid, "why": why}) + "\n")
        failed.flush()

    t0 = time.time()
    n_done = n_tok = 0
    pos = 0
    while pos < len(todo) and time.time() - t_start < a.budget:
        # gather lines until about sentences-per-call sentences
        batch, sents, counts = [], [], []
        while pos < len(todo) and len(sents) < a.sentences_per_call:
            o = todo[pos]
            pos += 1
            text = unicodedata.normalize("NFC", o["text"])
            try:
                ss = model.tokenize(text, "")
            except Exception as e:
                note_failed(
                    o["id"], "tokenizer: " + type(e).__name__
                )  # e.g. a sentence over 1000 words
                continue
            if not ss:
                note_failed(o["id"], "no sentences")
                continue
            batch.append(o["id"])
            counts.append(len(ss))
            sents.extend(ss)
        if not sents:
            continue
        try:
            parsed = conllu_sentences(model.predict(sents, True, True, writer))
            if len(parsed) != len(sents):
                raise RuntimeError("sentence count mismatch")
        except Exception:
            # One sentence longer than the model's 512 subword positions breaks a whole batch.
            # Parse the sentences one by one and give up on the lines that still fail.
            parsed = []
            for sent in sents:
                try:
                    one = conllu_sentences(model.predict([sent], True, True, writer))
                    parsed.append(one[0] if len(one) == 1 else None)
                except Exception:
                    parsed.append(None)
        k = 0
        for lid, c in zip(batch, counts):
            part = parsed[k : k + c]
            k += c
            if any(x is None for x in part):
                note_failed(lid, "model: sentence too long for the 512 subword limit")
                continue
            toks = join_sentences(part, a.shift_heads)
            if toks:
                out.write(json.dumps(row_of(lid, toks), ensure_ascii=False) + "\n")
                n_done += 1
                n_tok += len(toks)
        out.flush()
    dt = time.time() - t0
    print(
        f"parsed {n_done} lines, {n_tok} tokens in {dt:.0f}s: {n_done / max(dt, 1e-9):.1f} lines/s; "
        f"{len(todo) - pos} lines still to do",
        flush=True,
    )


if __name__ == "__main__":
    main()
