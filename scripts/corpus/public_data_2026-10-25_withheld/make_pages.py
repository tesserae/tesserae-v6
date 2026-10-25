import json, os, re, hashlib
S = os.path.expanduser('~/tesserae-backups/public_data_2026-10-25_withheld')
P = '/var/www/tesseraev6_flask/public_data/'
led = {n: json.load(open(f'{S}/work/pack_{k}.json')) for n, k in (('la_index.db.tar.gz', 'la'), ('window_texts.db.tar.gz', 'wt'), ('passage_index_la.tar.gz', 'pi'))}
mb = lambda n: f"{round(led[n]['archive_bytes'] / 1e6):d} MB"
h = open(P + 'index.html', encoding='utf-8').read()
def sub(old, new):
    global h
    assert h.count(old) == 1, old
    h = h.replace(old, new)
# la_index
sub('''<td><a href="la_index.db.tar.gz">la_index.db.tar.gz</a></td>
            <td>567 MB</td>
            <td>2026-10-19</td>
            <td>Latin inverted index (the live search index, rebuilt 18 October 2026 after the Latin lemma corrections)</td>''',
f'''<td><a href="la_index.db.tar.gz">la_index.db.tar.gz</a></td>
            <td>{mb('la_index.db.tar.gz')}</td>
            <td>2026-10-25</td>
            <td>Latin inverted index (the live search index, rebuilt 18 October 2026 after the Latin lemma corrections), republished 25 October 2026 with the works from Musisque Deoque, Corpus Thomisticum and augustinus.it left out (1,783 texts of 1,889). The archive holds LICENSE.txt and README.txt.</td>''')
sub('''<td><a href="passage_index_la.tar.gz">passage_index_la.tar.gz</a></td>
            <td>497 MB</td>
            <td>2026-10-19</td>
            <td>Passage window index, Latin slice: ids, descriptions and vectors behind Theme Search and Similar Passages. Public Domain / CC BY-SA 4.0 where Perseus TEI is involved.</td>''',
f'''<td><a href="passage_index_la.tar.gz">passage_index_la.tar.gz</a></td>
            <td>{mb('passage_index_la.tar.gz')}</td>
            <td>2026-10-25</td>
            <td>Passage window index, Latin slice: ids, descriptions and vectors behind Theme Search and Similar Passages. Public Domain / CC BY-SA 4.0 where Perseus TEI is involved. De doctrina christiana left out.</td>''')
sub('''<td>496 MB</td>
            <td>2026-10-19</td>
            <td>Text of 460,652 passage windows and the lines of each work. Republished 19 October 2026 without the Sahidica New Testament, the Arabic and Persian works and eleven Iqbal collections. License''',
f'''<td>{mb('window_texts.db.tar.gz')}</td>
            <td>2026-10-25</td>
            <td>Text of 446,704 passage windows and the lines of each work. Republished 19 October 2026 without the Sahidica New Testament, the Arabic and Persian works and eleven Iqbal collections, and on 25 October 2026 without the works from Musisque Deoque, Corpus Thomisticum and augustinus.it. License''')
open(S + '/index.html', 'w', encoding='utf-8').write(h)
j = json.load(open(P + 'index.json', encoding='utf-8'))
pi = led['passage_index_la.tar.gz']
j['la']['windows'] = 226480
j['la']['bytes'] = sum(v['bytes'] for v in pi['files'].values())
j['_other_archives']['window_texts.db.tar.gz']['bytes'] = led['window_texts.db.tar.gz']['archive_bytes']
j['_other_archives']['window_texts.db.tar.gz']['sha256'] = led['window_texts.db.tar.gz']['archive_sha256']
raw_old = open(P + 'index.json', encoding='utf-8').read()
raw = json.dumps(j, indent=1, ensure_ascii=False)
# keep the served file's exact formatting: it has no trailing newline
assert raw_old == json.dumps(json.load(open(P + 'index.json', encoding='utf-8')), indent=1, ensure_ascii=False), 'format differs'
open(S + '/index.json', 'w', encoding='utf-8').write(raw)
# checksums
lines = open(P + 'SHA256SUMS.txt', encoding='utf-8').read().split('\n')
out = []
new = {n: led[n]['archive_sha256'] for n in led}
new['index.json'] = hashlib.sha256(raw.encode('utf-8')).hexdigest()
seen = set()
for l in lines:
    if not l.strip():
        out.append(l); continue
    hh, name = l.split('  ', 1)
    if name in new:
        out.append(f'{new[name]}  {name}'); seen.add(name)
    else:
        out.append(l)
assert seen == set(new), seen
open(S + '/SHA256SUMS.txt', 'w', encoding='utf-8').write('\n'.join(out))
print('ok', {k: (v[:12]) for k, v in new.items()}, j['la'])
