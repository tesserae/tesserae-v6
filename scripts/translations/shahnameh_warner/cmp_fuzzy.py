import json,sys,difflib,unicodedata
base=sys.argv[1]
seq=json.load(open(base+'/ganjoor_seq.json'))
ours=[l.rstrip('\n').split('\t',1)[1] for l in open(__import__('os').environ.get('OLD_TESS','/var/www/tesseraev6_flask/texts/fa/ferdowsi.shahnameh.tess'),encoding='utf-8')]
def n(s):
    s=unicodedata.normalize('NFKD',s)
    s=''.join(c for c in s if unicodedata.category(c) not in('Mn','Po','Pd','Ps','Pe','Cf','Zs','Cc'))
    for a,b in (('ي','ی'),('ك','ک'),('ۀ','ه'),('ئ','ی'),('ؤ','و'),('أ','ا'),('إ','ا'),('آ','ا'),('ء',''),('ا',''),('و','')):
        s=s.replace(a,b)
    return s
A=[n(x[5]) for x in seq];B=[n(x) for x in ours]
def sim(a,b): return difflib.SequenceMatcher(None,a,b,autojunk=False).ratio()
i=j=0;pairs=[];events=[]
while i<len(A) and j<len(B):
    s=sim(A[i],B[j])
    if s>=0.6: pairs.append((i,j,s));i+=1;j+=1;continue
    # lookahead for resync
    best=None
    for di in range(0,6):
        for dj in range(0,6):
            if di==dj==0: continue
            if i+di+2<len(A) and j+dj+2<len(B):
                sc=sum(sim(A[i+di+k],B[j+dj+k])>=0.6 for k in range(3))
                if sc==3 and (best is None or di+dj<best[0]): best=(di+dj,di,dj)
    if best is None: events.append(('unresolved-replace',i,j,seq[i][5],ours[j]));pairs.append((i,j,s));i+=1;j+=1
    else:
        _,di,dj=best;events.append(('gap',i,j,di,dj,[x[5] for x in seq[i:i+di]],ours[j:j+dj]));i+=di;j+=dj
print('aligned',len(pairs),'of',len(A),len(B),'tail',len(A)-i,len(B)-j)
import statistics
print('mean sim',statistics.mean(p[2] for p in pairs))
print('events',len(events))
for e in events[:60]: print(e)
json.dump({'pairs':[(p[0],p[1]) for p in pairs],'events':events},open(base+'/fuzzy_align.json','w'),ensure_ascii=False)
