import json,sys,re,collections
base=sys.argv[1]
cats=json.load(open(base+'/downloads/ganjoor_meta/cats_poems.json'))
seq=json.load(open(base+'/ganjoor_seq.json'))
fz=json.load(open(base+'/fuzzy_align.json'))
import os
src=os.environ.get('OLD_TESS','/var/www/tesseraev6_flask/texts/fa/ferdowsi.shahnameh.tess')  # the running-number file as installed
ours=[l.rstrip('\n').split('\t',1) for l in open(src,encoding='utf-8')]
# story index per ganjoor line
stories=[];gstory=[]
for c in cats:
    for p in c['poems']:
        d=json.load(open(f"{base}/downloads/ganjoor_meta/poems/{p['id']}.json"))
        t=re.sub(r'^بخش\s*[۰-۹0-9]+\s*[-–]\s*','',d['title']).strip()
        stories.append({'number':len(stories)+1,'poem_id':p['id'],'reign_cat_id':c['catId'],'reign_title_fa':c['title'],'title_fa':t,'ganjoor_title':d['title'],'n_ganjoor_lines':len(d['verses'])})
        gstory+= [len(stories)-1]*len(d['verses'])
assert len(gstory)==len(seq)
j2i={j:i for i,j in fz['pairs']}
ostory=[None]*len(ours)
last=0
for j in range(len(ours)):
    if j in j2i: last=gstory[j2i[j]]
    ostory[j]=last
# check monotone
assert all(ostory[k]<=ostory[k+1] for k in range(len(ostory)-1))
cnt=collections.Counter(ostory)
odd=[(s+1,n) for s,n in cnt.items() if n%2]
print('stories with lines',len(cnt),'of',len(stories),'odd',odd)
new=[];o2n={}
pos=collections.Counter()
for j,(tag,txt) in enumerate(ours):
    s=ostory[j];k=pos[s];pos[s]+=1
    nt=f"ferdowsi.shahnameh.{s+1}.{k//2+1}.{k%2+1}"
    new.append((nt,txt));o2n[tag.strip('<>').split('.')[-1]]=nt
    stories[s].setdefault('first',f"{k//2+1}");
for s,st in enumerate(stories):
    n=cnt.get(s,0); st['n_lines']=n; st['n_couplets']=n//2
    st['first_couplet']=1 if n else None; st['last_couplet']=n//2 if n else None
    st.pop('first',None)
with open(base+'/ferdowsi.shahnameh.new.tess','w',encoding='utf-8') as f:
    for t,x in new: f.write(f"<{t}>\t{x}\n")
json.dump(o2n,open(base+'/old_to_new_refs.json','w'),ensure_ascii=False)
json.dump(stories,open(base+'/stories_raw.json','w'),ensure_ascii=False,indent=1)
print(len(new),len(o2n),sum(1 for s in stories if s['n_lines']==0))
