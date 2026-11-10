"""article_key and the merge of one article held by several citation indexes,
and the per-index cut in citation_index. All titles are invented."""
from backend import scholarship as S


def row(title, year, source='citation_index', **kw):
    d = {'title': title, 'year': year, 'authors': ['A'], 'venue': 'Journal', 'source': source,
         'url': None, 'url_jstor': None, 'url_ia': None, 'doi': None, 'snippet': None, 'pages': []}
    d.update(kw)
    return d


def test_key_prefers_stable_id_then_doi_then_title_and_year():
    both = row('The Fall of Troy', 1901, url_jstor='https://www.jstor.org/stable/12345', doi='10.9999/X')
    assert S.article_key(both) == ('id', '12345')
    assert S.article_key(row('x', 1, url='https://www.jstor.org/stable/777?seq=4')) == ('id', '777')
    assert S.article_key(row('x', 1, url='https://www.jstor.org/stable/10.2307/888?seq=2')) == ('id', '888')
    assert S.article_key(row('x', 1, url_jstor='https://www.jstor.org/stable/10.2307/888')) == ('id', '888')
    assert S.article_key(row('x', 1, url='https://www.jstor.org/stable/10.5555/abc')) == ('id', '10.5555/abc')
    assert S.article_key(row('x', 1, jstor_id='ABC9')) == ('id', 'abc9')
    assert S.article_key(row('x', 1, doi='10.2307/555')) == ('id', '555')
    assert S.article_key(row('The Fall of Troy', 1901, doi='10.1353/AJP.1')) == ('doi', '10.1353/ajp.1')
    k = S.article_key(row('The Fall of Troy!', 1901))
    assert k == ('title', 'falloftroy', 1901)
    assert S.article_key(row('Fall of  Troy', 1901)) == k
    assert S.article_key(row('Der Fall Trojas', 1901)) == ('title', 'falltrojas', 1901)
    assert S.article_key(row('Éloge de Troie', 1901)) == S.article_key(row('Eloge de Troie', 1901))


def test_different_dois_with_one_stable_id_merge(monkeypatch):
    a = row('Troy Revisited Again', 1950, source='jstor', doi='10.2307/42', url='https://www.jstor.org/stable/42?seq=3')
    b = row('Troy Revisited Again', 1950, source='muse', doi='10.1353/tap.42', url='https://doi.org/10.1353/tap.42')
    c = row('Troy Revisited Again', 1950, source='jstor', doi='10.5555/other', url='https://www.jstor.org/stable/42?seq=9')
    assert S.article_key(a) == S.article_key(c)
    monkeypatch.setattr(S, 'passage_names', lambda w, s, e=None: {'work': w})
    monkeypatch.setattr(S, 'citation_index', lambda a_, limit=40: {'available': True, 'note': '', 'results': [a, b, c]})
    out = S.citing_articles('w', [('1.1', None)])
    assert out['total'] == 1 and out['results'][0]['source'] == 'muse'


def test_ejc_and_jstor_rows_merge_into_one_ejc_item(monkeypatch):
    jst = row('On the Shield of Achilles', 1905, source='jstor', url='https://www.jstor.org/stable/9001?seq=2',
              url_jstor='https://www.jstor.org/stable/9001?seq=2')
    ejc = row('On the Shield of Achilles', 1905, url_jstor='https://www.jstor.org/stable/9001', snippet='An invented sentence.')
    other = row('A Different Study of Epic', 1960, source='jstor', url='https://www.jstor.org/stable/9002')
    monkeypatch.setattr(S, 'passage_names', lambda w, s, e=None: {'work': w})
    monkeypatch.setattr(S, 'citation_index', lambda a, limit=40: {'available': True, 'note': 'n', 'results': [jst, ejc, other]})
    out = S.citing_articles('w', [('1.1', None), ('1.5', None)])
    assert out['total'] == 2
    merged = [r for r in out['results'] if r['title'] == 'On the Shield of Achilles'][0]
    assert merged['source'] == 'ejc' and merged['url'] == 'https://www.jstor.org/stable/9001'
    assert merged['cites'] == ['1.1', '1.5']
    assert merged['sentences'] == [{'ref': '1.1', 'text': 'An invented sentence.'},
                                   {'ref': '1.5', 'text': 'An invented sentence.'}]
    assert [r for r in out['results'] if r['source'] == 'jstor'][0]['sentences'] == []


def test_muse_and_jstor_twins_merge_by_title_and_year(monkeypatch):
    m = row('Hexameter and Memory in Latin Verse', 1999, source='muse', doi='10.1353/ajp.1')
    j = row('Hexameter and memory in Latin verse', 1999, source='jstor', doi='10.2307/31', url='https://www.jstor.org/stable/31')
    short_a = row('Notes', 1999, source='muse', doi='10.1353/n.1')
    short_b = row('Notes', 1999, source='jstor', doi='10.2307/32', url='https://www.jstor.org/stable/32')
    monkeypatch.setattr(S, 'passage_names', lambda w, s, e=None: {'work': w})
    monkeypatch.setattr(S, 'citation_index', lambda a, limit=40: {'available': True, 'note': '', 'results': [m, j, short_a, short_b]})
    out = S.citing_articles('w', [('1.1', None)])
    assert out['total'] == 3   # the long title merges; two articles called "Notes" stay apart


def test_citation_index_lists_up_to_limit_from_each_index(tmp_path, monkeypatch):
    for name in ('ejc.db', 'muse.db', 'jstor.db'):
        (tmp_path / name).write_bytes(b'')
    monkeypatch.setattr(S, 'CITATION_INDEX', str(tmp_path / 'ejc.db'))
    monkeypatch.setenv(S.CITATIONS_EXTRA_ENV, str(tmp_path / 'muse.db'))
    monkeypatch.setenv(S.CITATIONS_JSTOR_ENV, str(tmp_path / 'jstor.db'))

    def fake(path, source, *args):
        base = {'citation_index': 1900, 'muse': 2000, 'jstor': 1960}[source]
        return {f'{source}{i}': row(f'{source} article {i}', base + (i % 20), source=source) for i in range(50)}
    monkeypatch.setattr(S, '_index_articles', fake)
    out = S.citation_index({'work': 'vergil.aeneid', 'lo': '1.1', 'hi': '1.1'})
    assert len(out['results']) == 120 and out['total'] == 150
    ejc = [r for r in out['results'] if r['source'] == 'citation_index']
    assert len(ejc) == 40 and len([r for r in out['results'] if r['source'] == 'muse']) == 40
    years = [r['year'] for r in out['results']]
    assert years == sorted(years, reverse=True)
