#!/usr/bin/env python3
"""Measure the gateway request rate with realistic judge prompts.

Usage: gateway_probe.py DOSSIER_DIR WORKERS SECONDS OUT.json [seed]
Builds 10-passage judge prompts from the dossiers in DOSSIER_DIR (a nonce line keeps each prompt
unique), keeps WORKERS requests in flight for SECONDS and writes the completed count, the failures
and the token totals. Run two copies at once to see whether a second process raises the total rate.
"""
import glob, json, os, random, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm_judge as lj  # noqa: E402


def prompts(d, seed):
    rnd = random.Random(seed)
    out = []
    for f in sorted(glob.glob(os.path.join(d, "*.json"))):
        if f.endswith(".ranked.json"):
            continue
        j = json.load(open(f))
        ps = j["literary"]["passages"][:100]
        ev = {"name": j["event"]["label"], "date": "unknown", "place": "unknown", "participants": "", "intro": j["event"].get("description") or ""}
        for i in range(0, len(ps) - 9, 10):
            blocks = [lj.passage_block(k + 1, {"ref": p["ref_start"], "language": p["language"], "gist": p.get("gist"),
                                                "lines": [(h["ref"], h["snippet"]) for h in p.get("hit_lines", [])[:3] if h.get("ref")]})
                      for k, p in enumerate(ps[i:i + 10])]
            out.append(lj.event_header(ev) + "\n" + "\n\n".join(blocks))
    rnd.shuffle(out)
    return out


def main(d, workers, seconds, out, seed=0):
    workers, seconds = int(workers), float(seconds)
    j = lj.Judge.__new__(lj.Judge)
    j.model, j.key, j.timeout = lj.DEFAULT_MODEL, lj.load_key(), 240
    ps = prompts(d, int(seed))
    stop = time.time() + seconds
    res = {"done": 0, "failed": 0, "prompt_tokens": 0, "completion_tokens": 0, "latencies": []}
    lock = threading.Lock()
    idx = [0]

    def worker():
        while time.time() < stop:
            with lock:
                u = ps[idx[0] % len(ps)] + f"\n(nonce {seed}-{idx[0]}-{time.time()})"
                idx[0] += 1
            content, usage, secs, status = j._call(lj.SYSTEM, u)
            with lock:
                if status == "ok":
                    res["done"] += 1
                    res["prompt_tokens"] += usage.get("prompt_tokens", 0)
                    res["completion_tokens"] += usage.get("completion_tokens", 0)
                    res["latencies"].append(secs)
                else:
                    res["failed"] += 1

    t0 = time.time()
    ts = [threading.Thread(target=worker) for _ in range(workers)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    res["wall"] = time.time() - t0
    res["rate"] = res["done"] / res["wall"]
    res["mean_latency"] = sum(res["latencies"]) / max(1, len(res["latencies"]))
    del res["latencies"]
    json.dump(res, open(out, "w"))
    print(json.dumps(res))


if __name__ == "__main__":
    main(*sys.argv[1:6])
