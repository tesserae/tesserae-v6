# ruff: noqa: E402, E741  (a run-once script: imports follow its path setup)
"""One Similar Passages and one Theme Search request answered offline from the staged copies (scratch root of symlinks).
The query is encoded by a local CPU model in this process, not by the live embed service. usage: offline_requests.py SCRATCH_ROOT"""

import os
import sys

root = sys.argv[1]
sys.path.insert(0, root)
os.chdir(root)
from sentence_transformers import SentenceTransformer
from backend import passage_index as pi

assert pi._DATA_DIR.startswith(root), pi._DATA_DIR
m = SentenceTransformer("intfloat/multilingual-e5-large", device="cpu")
pi._embed_query_uncached = lambda t: m.encode(
    "query: " + t, normalize_embeddings=True
).astype("float32")
pi._ensure_loaded()
print("loaded", pi._state["ok"], len(pi._ids), "windows", pi._emb.shape)
r = pi.find_similar_to_window("acts.pilate:fine:0", limit=5)
print(
    "SIMILAR to acts.pilate:fine:0:",
    [
        (
            x.get("id") or x.get("window_id"),
            round(x.get("score", x.get("similarity", 0)), 3),
        )
        for x in r["results"]
    ][:5],
    "keys",
    sorted(r)[:8],
)
t = pi.find_by_text(
    "the crowd demands that a criminal be released and the innocent man be crucified",
    limit=10,
)
print("THEME keys", sorted(t)[:10])
res = t.get("results", [])
print(
    "THEME top:", [(x.get("id") or x.get("window_id"), x.get("work")) for x in res][:10]
)
print(
    "new-work hits in top 10:",
    [x.get("work") for x in res if x.get("work") in ("acts.pilate", "thomas.gospel")],
)
