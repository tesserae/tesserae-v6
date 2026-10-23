import json,sys,collections
base=sys.argv[1]
cats=json.load(open(base+'/downloads/ganjoor_meta/cats_poems.json'))
seq=[];pos=collections.Counter()
for c in cats:
    for p in c['poems']:
        d=json.load(open(f"{base}/downloads/ganjoor_meta/poems/{p['id']}.json"))
        for v in d['verses']:
            pos[v['versePosition']]+=1
            seq.append((len(seq),p['id'],v['vOrder'],v['coupletIndex'],v['versePosition'],v['text']))
print(len(seq),pos)
json.dump(seq,open(base+'/ganjoor_seq.json','w'),ensure_ascii=False)
ours=[l.rstrip('\n').split('\t',1)[1] for l in open(__import__('os').environ.get('OLD_TESS','/var/www/tesseraev6_flask/texts/fa/ferdowsi.shahnameh.tess'),encoding='utf-8')]
print(len(ours))
import re
def n(s): return re.sub(r'[‌‍ً-ْ\s]','',s).replace('ي','ی').replace('ك','ک')
same=sum(1 for a,b in zip(seq,ours) if a[5]==b); same2=sum(1 for a,b in zip(seq,ours) if n(a[5])==n(b))
print('exact',same,'normalized',same2)
bad=[(i,a[5],b) for i,(a,b) in enumerate(zip(seq,ours)) if n(a[5])!=n(b)]
print(len(bad),bad[:10])
