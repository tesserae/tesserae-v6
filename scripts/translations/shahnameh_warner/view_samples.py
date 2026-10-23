import json,sys,random,collections
base=sys.argv[1];mode=sys.argv[2]
d=json.load(open(base+'/outputs/fa__ferdowsi.shahnameh.json'))
tess=[l.rstrip('\n').split('\t',1) for l in open(base+'/ferdowsi.shahnameh.new.tess',encoding='utf-8')]
st=json.load(open(base+'/stories_raw.json'))
lines=collections.OrderedDict((t.strip('<>'),x) for t,x in tess)
r2u=d['ref_to_unit'];units=d['units']
u2refs=collections.defaultdict(list)
for r,u in r2u.items(): u2refs[u].append(r)
def show(u,maxp=900):
    rs=sorted(u2refs[u],key=lambda r:[int(x) for x in r.split('.')[2:]])
    s=int(rs[0].split('.')[2]);cs=[int(r.split('.')[3]) for r in rs]
    print(f"--- unit {u}: story {s} ({st[s-1]['title_fa'][:40]}) couplets {min(cs)}-{max(cs)} of {st[s-1]['n_couplets']}")
    for r in rs[:12]: print('   ',r.split('ferdowsi.shahnameh.')[1],lines[r])
    if len(rs)>12: print('    ... (+%d lines)'%(len(rs)-12))
    print('  EN:',units[u][:maxp].replace('\n\n',' || '))
if mode=='random':
    random.seed(1023)
    cand=sorted(set(r2u.values()))
    # sample 40 translated couplets uniformly (by couplet), then show their unit
    refs=[r for r in lines if r in r2u and r.endswith('.1')]
    pick=random.sample(refs,40)
    json.dump(pick,open(base+'/sample40.json','w'))
    for k,r in enumerate(pick,1):
        print('=== SAMPLE',k,r); show(r2u[r])
else:
    a,b=int(sys.argv[3]),int(sys.argv[4])
    seen=set()
    for r in lines:
        s=int(r.split('.')[2])
        if a<=s<=b and r in r2u and r2u[r] not in seen:
            seen.add(r2u[r]);show(r2u[r],int(sys.argv[5]) if len(sys.argv)>5 else 700)
