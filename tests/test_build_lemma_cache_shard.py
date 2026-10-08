"""Tests for scripts/documents/build_lemma_cache_shard.py's file-splitting
logic (the part safe to unit test without a real multi-minute run)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.documents.build_lemma_cache_shard import count_lines, shard_files


def test_shard_files_covers_every_file_exactly_once(tmp_path):
    lang_dir = tmp_path / "la"
    lang_dir.mkdir()
    names = [f"bucket_{i:02d}.tess" for i in range(7)]
    for n in names:
        (lang_dir / n).write_text("x\n")

    num_shards = 3
    all_assigned = []
    for shard_index in range(num_shards):
        all_assigned.extend(shard_files(str(lang_dir), num_shards, shard_index))

    assert sorted(all_assigned) == sorted(names)
    assert len(all_assigned) == len(names)


def test_shard_files_is_deterministic_across_repeated_calls(tmp_path):
    lang_dir = tmp_path / "grc"
    lang_dir.mkdir()
    for i in range(5):
        (lang_dir / f"f{i}.tess").write_text("x\n")

    first = shard_files(str(lang_dir), 2, 0)
    second = shard_files(str(lang_dir), 2, 0)
    assert first == second


def test_count_lines(tmp_path):
    p = tmp_path / "a.tess"
    p.write_text("<x.1>\ta\n<x.2>\tb\n<x.3>\tc\n")
    assert count_lines(str(p)) == 3
