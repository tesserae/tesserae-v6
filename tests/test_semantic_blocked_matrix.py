"""The semantic channel computes similarity in blocks of rows (2026-10-03): a
9,502 x 157,780 pair built a 6 GB matrix twice over and killed the demo
server. The blocked computation must return the same pairs as the full
matrix did."""
import numpy as np

from backend.semantic_similarity import top_pairs_by_block


def _full_matrix_pairs(src, tgt, top_n, min_score):
    sim = np.dot(src, tgt.T)
    sim = sim / (np.linalg.norm(src, axis=1, keepdims=True) @ np.linalg.norm(tgt, axis=1, keepdims=True).T + 1e-8)
    out = []
    for i in range(src.shape[0]):
        row = sim[i]
        count = 0
        for j in np.argsort(row)[::-1][:top_n * 2]:
            if row[j] >= min_score:
                out.append((i, int(j), round(float(row[j]), 5)))
                count += 1
                if count >= top_n:
                    break
    return out


def test_blocked_pairs_equal_full_matrix_pairs():
    rng = np.random.default_rng(3)
    src = rng.normal(size=(1300, 16)).astype(np.float32)
    tgt = rng.normal(size=(2100, 16)).astype(np.float32)
    got = top_pairs_by_block(src, tgt, 3, 0.5, block_rows=512)
    exp = _full_matrix_pairs(src, tgt, 3, 0.5)
    # the same pairs in the same order; scores agree to float32 precision
    assert [(a, b) for a, b, _ in got] == [(a, b) for a, b, _ in exp]
    assert max(abs(g[2] - e[2]) for g, e in zip(got, exp)) < 1e-4
    assert got, 'the random case should produce some pairs above 0.5'


def test_small_target_and_a_floor_nothing_passes():
    rng = np.random.default_rng(4)
    src = rng.normal(size=(5, 8)).astype(np.float32)
    tgt = rng.normal(size=(2, 8)).astype(np.float32)
    pairs = top_pairs_by_block(src, tgt, 5, -1.0)
    assert len(pairs) == 10 and {j for _, j, _ in pairs} == {0, 1}
    assert top_pairs_by_block(src, tgt, 5, 2.0) == []
