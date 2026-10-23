import json
import sys
import time
import urllib.request
import os

out = sys.argv[1]
cats = json.load(open(out + "/cats_poems.json"))
os.makedirs(out + "/poems", exist_ok=True)
n = 0
for c in cats:
    for p in c["poems"]:
        f = f"{out}/poems/{p['id']}.json"
        if os.path.exists(f):
            continue
        for t in range(5):
            try:
                r = urllib.request.urlopen(
                    f"https://api.ganjoor.net/api/ganjoor/poem/{p['id']}?catInfo=false&catPoems=false&rhymes=false&recitations=false&images=false&songs=false&comments=false&verseDetails=true&navigation=false",
                    timeout=40,
                ).read()
                break
            except Exception:
                time.sleep(3)
                r = None
        if r is None:
            print("FAIL", p["id"])
            continue
        open(f, "wb").write(r)
        n += 1
print("fetched", n)
