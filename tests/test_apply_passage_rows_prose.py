"""apply_passage_rows.py --mode append takes prose rows (scale and the extra fields)."""
import json
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'corpus'))
import apply_passage_rows as apr  # noqa: E402


def test_append_keeps_prose_fields(tmp_path, monkeypatch):
    idx = tmp_path / 'idx'
    idx.mkdir()
    json.dump(['a:fine:0'], open(idx / 'ids.json', 'w'))
    np.save(idx / 'embeddings.npy', np.zeros((1, 4), dtype=np.float32))
    (idx / 'descriptions.jsonl').write_text(json.dumps({'id': 'a:fine:0', 'scale': 'fine'}) + '\n')
    row = {'id': 'a:prose:0', 'work': 'a', 'scale': 'prose', 'language': 'la',
           'ref_start': 'r 1', 'ref_end': 'r 1', 'sub': 2, 'char_start': 10, 'char_end': 90,
           'desc': {'gist': 'g', 'themes': ['t']}}
    side = tmp_path / 'side.jsonl'
    side.write_text(json.dumps(row) + '\n')
    monkeypatch.setattr(apr, 'embed_all', lambda blobs: [[1.0, 0.0, 0.0, 0.0] for _ in blobs])
    monkeypatch.setattr(sys, 'argv', ['x', '--index', str(idx), '--sidecar', str(side),
                                      '--mode', 'append', '--tag', 't'])
    apr.main()
    assert json.load(open(idx / 'ids.json')) == ['a:fine:0', 'a:prose:0']
    assert np.load(idx / 'embeddings.npy').shape == (2, 4)
    last = [json.loads(l) for l in open(idx / 'descriptions.jsonl')][-1]
    assert last['scale'] == 'prose' and last['sub'] == 2 and last['char_end'] == 90


def test_append_with_precomputed_vectors_does_not_call_the_embed_service(tmp_path, monkeypatch):
    idx = tmp_path / 'idx'
    idx.mkdir()
    json.dump(['a:fine:0'], open(idx / 'ids.json', 'w'))
    np.save(idx / 'embeddings.npy', np.zeros((1, 4), dtype=np.float32))
    (idx / 'descriptions.jsonl').write_text(json.dumps({'id': 'a:fine:0'}) + '\n')
    rows = [{'id': f'a:prose:{n}', 'scale': 'prose', 'desc': {'gist': 'g'}} for n in range(2)]
    side = tmp_path / 'side.jsonl'
    side.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    np.save(tmp_path / 'v.npy', np.array([[0, 1, 0, 0], [0, 0, 1, 0]], dtype=np.float32))
    json.dump(['a:prose:1', 'a:prose:0'], open(tmp_path / 'vids.json', 'w'))

    def boom(blobs):
        raise AssertionError('embed service called')
    monkeypatch.setattr(apr, 'embed_all', boom)
    monkeypatch.setattr(sys, 'argv', ['x', '--index', str(idx), '--sidecar', str(side), '--mode',
                                      'append', '--tag', 't', '--vectors', str(tmp_path / 'v.npy'),
                                      '--vector-ids', str(tmp_path / 'vids.json')])
    apr.main()
    emb = np.load(idx / 'embeddings.npy')
    assert emb.shape == (3, 4)
    assert emb[1].tolist() == [0, 0, 1, 0] and emb[2].tolist() == [0, 1, 0, 0]
