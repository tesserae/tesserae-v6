"""End-to-end Persian search validation: Sa'di Bustan vs Ferdowsi Shahnameh.
Expect the famous opening echo: 'به نام خداوند جان ...' (In the name of the Lord of life...)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# register Persian
import backend.persian
backend.persian.register()

from backend.text_processor import TextProcessor
from backend.matcher import Matcher
from backend.scorer import Scorer
from backend.fusion import run_fusion_search

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = os.path.join(BASE, 'texts/fa/saadi.bustan.part.1.tess')
tgt = os.path.join(BASE, 'texts/fa/ferdowsi.shahnameh.part.1.tess')

tp, matcher, scorer = TextProcessor(), Matcher(), Scorer()
su = tp.process_file(src, 'fa', 'line')
tu = tp.process_file(tgt, 'fa', 'line')
print(f'source units: {len(su)}  target units: {len(tu)}')

results = run_fusion_search(su, tu, matcher, scorer,
                            'saadi.bustan.part.1.tess', 'ferdowsi.shahnameh.part.1.tess',
                            language='fa', max_results=10)
print(f'total results: {len(results)}\n')
for i, r in enumerate(results[:5], 1):
    st = (r.get('source_text') or r.get('source') or '')[:60]
    tt = (r.get('target_text') or r.get('target') or '')[:60]
    sc = r.get('score') or r.get('fusion_score') or r.get('final_score')
    ch = r.get('channels') or r.get('channel') or r.get('matched_channels')
    print(f'#{i} score={sc}  channels={ch}')
    print(f'   S: {st}')
    print(f'   T: {tt}')
echo_found = any('خداوند' in ((r.get('source_text') or '') + (r.get('target_text') or '')) for r in results)
print(f'\n>>> opening echo (خداوند / "Lord") found in results: {echo_found}')
