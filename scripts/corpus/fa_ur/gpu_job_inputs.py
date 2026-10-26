#!/usr/bin/env python3
"""Inputs for the campus GPU encoder, and the assembly of its vectors into the staging layout.

The recipe (research/threads/GPU_JOB_RECIPE.md) reads `blobs.jsonl.gz` ({id, text}, the text already
carrying its prefix) from a job folder under public_data on the production checkout and returns
`vectors-NNN.npy` and `ids-NNN.json` parts. A staging run may not write under /var/www, so this script
only prepares the two blob files for the owner to place in a job folder, and assembles the parts after.

    gpu_job_inputs.py prepare STAGE_DIR OUT_DIR
        STAGE_DIR holds texts/ur/*.tess and descriptions/descriptions.jsonl.
        Writes OUT_DIR/lines/blobs.jsonl.gz (id = line reference, text = "passage: " + line, as
        encode_line_vectors.py) and OUT_DIR/passages/blobs.jsonl.gz (id = window id, text =
        apply_passage_rows.blob_for of the description, "query: " prefix).
    gpu_job_inputs.py assemble STAGE_DIR PARTS_LINES_DIR PARTS_PASSAGES_DIR
        Reads the parts the job returned, checks unit length and that the ids match the inputs in order,
        writes STAGE_DIR/embeddings/ur/<work>.npy and .meta.json (the shape of encode_line_vectors.py)
        and STAGE_DIR/passage_vectors/embeddings.npy and ids.json.
"""

import datetime
import glob
import gzip
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from apply_passage_rows import blob_for  # noqa: E402


def line_rows(stage):
    for path in sorted(glob.glob(os.path.join(stage, "texts", "ur", "*.tess"))):
        work = os.path.basename(path)[: -len(".tess")]
        for line in open(path, encoding="utf-8"):
            m = re.match(r"<([^>]+)>\t(.*)", line.rstrip("\n"))
            if m:
                yield work, m.group(1), m.group(2)


def passage_rows(stage):
    seen = {}
    for line in open(os.path.join(stage, "descriptions", "descriptions.jsonl"), encoding="utf-8"):
        r = json.loads(line)
        if r.get("desc"):
            seen[r["id"]] = r
    return list(seen.values())


def write_blobs(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for i, t in rows:
            f.write(json.dumps({"id": i, "text": t}, ensure_ascii=False) + "\n")


def read_parts(folder):
    vecs, ids = [], []
    for v in sorted(glob.glob(os.path.join(folder, "vectors-*.npy"))):
        vecs.append(np.load(v))
        ids += json.load(open(v.replace("vectors-", "ids-").replace(".npy", ".json"), encoding="utf-8"))
    return np.concatenate(vecs).astype(np.float32), ids


def prepare(stage, out):
    lines = [(ref, "passage: " + text) for _, ref, text in line_rows(stage)]
    write_blobs(os.path.join(out, "lines", "blobs.jsonl.gz"), lines)
    passages = [(r["id"], blob_for(r["desc"])) for r in passage_rows(stage)]
    write_blobs(os.path.join(out, "passages", "blobs.jsonl.gz"), passages)
    print(len(lines), "line blobs,", len(passages), "passage blobs")


def assemble(stage, parts_lines, parts_passages):
    arr, ids = read_parts(parts_lines)
    want = [ref for _, ref, _ in line_rows(stage)]
    assert ids == want, "line ids differ from the inputs"
    assert np.allclose(np.linalg.norm(arr, axis=1), 1.0, atol=1e-3), "line vectors not unit length"
    by_work = {}
    for k, (work, ref, _) in enumerate(line_rows(stage)):
        by_work.setdefault(work, []).append(k)
    out = os.path.join(stage, "embeddings", "ur")
    os.makedirs(out, exist_ok=True)
    for work, ix in by_work.items():
        np.save(os.path.join(out, work + ".npy"), arr[ix])
        json.dump(
            {
                "text_path": f"texts/ur/{work}.tess", "language": "ur", "n_lines": len(ix),
                "embedding_dim": int(arr.shape[1]), "model": "intfloat/multilingual-e5-large",
                "prefix": "passage: ", "precision": "float32 from the campus GPU job",
                "device": "campus GPU (BullsAI Run:ai)",
                "created": datetime.datetime.now().isoformat(timespec="seconds"),
                "line_refs": [want[k] for k in ix],
            },
            open(os.path.join(out, work + ".meta.json"), "w", encoding="utf-8"), ensure_ascii=False,
        )
    parr, pids = read_parts(parts_passages)
    pwant = [r["id"] for r in passage_rows(stage)]
    assert pids == pwant, "passage ids differ from the inputs"
    assert np.allclose(np.linalg.norm(parr, axis=1), 1.0, atol=1e-3), "passage vectors not unit length"
    os.makedirs(os.path.join(stage, "passage_vectors"), exist_ok=True)
    np.save(os.path.join(stage, "passage_vectors", "embeddings.npy"), parr)
    json.dump(pids, open(os.path.join(stage, "passage_vectors", "ids.json"), "w", encoding="utf-8"))
    print("assembled", len(want), "line vectors in", len(by_work), "works and", len(pids), "passage vectors")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "prepare":
        prepare(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 5 and sys.argv[1] == "assemble":
        assemble(*sys.argv[2:5])
    else:
        raise SystemExit(__doc__)
