"""Tests for apply_text_list_filters — the server-side author/limit/offset/
compact filtering behind GET /texts (added so an AI-agent client can request
e.g. one author's texts instead of the whole language, which overflowed a
ChatGPT Custom GPT Action response)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.utils import apply_text_list_filters


def _corpus():
    return [
        {"id": "vergil.aeneid.part.1.tess", "author": "Vergil", "work": "Aeneid",
         "title": "Aeneid, Book 1", "part": "Book 1", "language": "la", "year": -19},
        {"id": "vergil.georgics.tess", "author": "Vergil", "work": "Georgics",
         "title": "Georgics", "part": None, "language": "la", "year": -29},
        {"id": "ovid.metamorphoses.part.1.tess", "author": "Ovid", "work": "Metamorphoses",
         "title": "Metamorphoses, Book 1", "part": "Book 1", "language": "la", "year": 8},
        {"id": "lucan.bellum_civile.part.1.tess", "author": "Lucan", "work": "Bellum Civile",
         "title": "Bellum Civile, Book 1", "part": "Book 1", "language": "la", "year": 61},
    ]


class Args(dict):
    """Minimal stand-in for request.args (a plain mapping with .get)."""


def test_no_params_returns_full_list_unchanged():
    texts = _corpus()
    out = apply_text_list_filters(texts, Args())
    assert out == texts  # existing callers (web app) get the full list


def test_author_filter_vergil():
    out = apply_text_list_filters(_corpus(), Args(author="Vergil"))
    assert {t["id"] for t in out} == {"vergil.aeneid.part.1.tess", "vergil.georgics.tess"}


def test_author_filter_is_case_insensitive_and_substring():
    out = apply_text_list_filters(_corpus(), Args(author="ovid"))
    assert [t["author"] for t in out] == ["Ovid"]


def test_contains_alias_matches_work_title_and_id():
    # 'aeneid' appears in work/title/id, not the author field
    out = apply_text_list_filters(_corpus(), Args(contains="aeneid"))
    assert [t["id"] for t in out] == ["vergil.aeneid.part.1.tess"]


def test_author_filter_no_match_returns_empty():
    assert apply_text_list_filters(_corpus(), Args(author="Homer")) == []


def test_limit_caps_results():
    out = apply_text_list_filters(_corpus(), Args(limit="2"))
    assert len(out) == 2


def test_offset_and_limit_paginate():
    page2 = apply_text_list_filters(_corpus(), Args(offset="2", limit="2"))
    assert [t["id"] for t in page2] == ["ovid.metamorphoses.part.1.tess",
                                        "lucan.bellum_civile.part.1.tess"]


def test_compact_returns_only_essential_fields():
    out = apply_text_list_filters(_corpus(), Args(author="Vergil", compact="true"))
    for t in out:
        assert set(t.keys()) == {"id", "author", "work", "title", "part", "language"}
        assert "year" not in t


def test_bad_limit_is_ignored_not_crashing():
    out = apply_text_list_filters(_corpus(), Args(limit="not-a-number"))
    assert len(out) == len(_corpus())
