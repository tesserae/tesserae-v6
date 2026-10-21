"""Tessa's Help extract keeps the whole of a long paragraph (2026-10-20)."""
import backend.assistant.site_help as H


def test_a_long_paragraph_is_split_not_cut(tmp_path):
    sentences = [f'Sentence number {i} explains one more rule of the page in some detail.' for i in range(40)]
    src = '<div><h3>Events</h3><p>' + ' '.join(sentences) + '</p></div>'
    f = tmp_path / 'Help.jsx'
    f.write_text(src, encoding='utf-8')
    chunks = H._extract(str(f))
    joined = ' '.join(chunks)
    for s in sentences:
        assert s in joined
    assert len(chunks) > 1
    assert all(c.startswith('Events: ') for c in chunks)
    assert all(len(c) <= H.CHUNK_MAX for c in chunks)


def test_the_event_scholarship_order_reaches_a_chunk():
    chunks = H._extract(H.HELP_SOURCE)
    assert any('then by how many of' in c for c in chunks)
