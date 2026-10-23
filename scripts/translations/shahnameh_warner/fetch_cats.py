import json
import sys
import time
import urllib.request

out = sys.argv[1]
d = json.load(open(out + "/cat33.json"))
res = []
for ch in d["cat"]["children"]:
    for t in range(4):
        try:
            r = urllib.request.urlopen(
                f"https://api.ganjoor.net/api/ganjoor/cat/{ch['id']}?poems=true",
                timeout=30,
            ).read()
            break
        except Exception:
            time.sleep(2)
    c = json.loads(r)["cat"]
    res.append(
        {
            "catId": ch["id"],
            "title": ch["title"],
            "nchildren": len(c["children"]),
            "poems": [
                {"id": p["id"], "title": p["title"], "slug": p["urlSlug"]}
                for p in c["poems"]
            ],
        }
    )
json.dump(res, open(out + "/cats_poems.json", "w"), ensure_ascii=False)
print(len(res), sum(len(x["poems"]) for x in res), sum(x["nchildren"] for x in res))
