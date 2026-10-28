#!/usr/bin/env python3
"""Windows for the 34 Coptic works that have none: same geometry as the live Coptic windows (fine 12/6, coarse 30/15,
min 4 lines, text newline-joined and uncapped), written one JSON object per line."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
import build_batch_windows as BW
from works import GAPS
out = sys.argv[1]
P = '/var/www/tesseraev6_flask/texts/cop/'
n = 0
with open(out, 'w', encoding='utf-8') as fh:
    for w in GAPS:
        ws = BW.windows_for(P + w + '.tess', 'cop', {}, {}, 0)
        print(w, len(ws), flush=True)
        for x in ws:
            fh.write(json.dumps(x, ensure_ascii=False) + '\n')
        n += len(ws)
print('total', n)
