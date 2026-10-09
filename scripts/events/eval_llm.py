#!/usr/bin/env python3
"""Agreement of the LLM judge with hand labels, and precision at 20 of a fused_llm dossier set.

Usage: eval_llm.py DOSSIER_DIR LABELS.json [LABELS2.json ...]
LABELS: {event: {window_id: yes|mention|no}} (my hand reading). The judgements are read from
DOSSIER_DIR/llm_judgements.sqlite. Prints the confusion matrix (hand label by model label), the
3-class and the binary (yes+mention against no) agreement, and for each event the precision at 20
of the dossier's top 20 by hand labels and by the model's labels.
"""
import collections, json, os, sqlite3, sys


def main(d, *label_files):
    mine = collections.defaultdict(dict)
    for f in label_files:
        for ev, m in json.load(open(f)).items():
            mine[ev].update(m)
    db = sqlite3.connect(os.path.join(d, "llm_judgements.sqlite"))
    J = {(e, w): l for e, w, l in db.execute("SELECT event, window_id, label FROM judgements")}
    cm = collections.Counter()
    for ev, m in mine.items():
        for w, l in m.items():
            if (ev, w) in J:
                cm[(l, J[(ev, w)])] += 1
    labs = ("yes", "mention", "no")
    print("hand label (rows) by model label (columns yes, mention, no)")
    for a in labs:
        print("  %-8s" % a, [cm[(a, b)] for b in labs])
    n = sum(cm.values())
    print("passages compared", n, "3-class agreement", round(sum(v for (a, b), v in cm.items() if a == b) / n, 3),
          "binary agreement", round(sum(v for (a, b), v in cm.items() if (a != "no") == (b != "no")) / n, 3))
    tp = sum(v for (a, b), v in cm.items() if a != "no" and b != "no")
    print("model yes+mention: precision against hand", round(tp / sum(v for (a, b), v in cm.items() if b != "no"), 3),
          "recall", round(tp / sum(v for (a, b), v in cm.items() if a != "no"), 3))
    hp, mp = [], []
    for ev in mine:
        ps = json.load(open(os.path.join(d, ev + ".json")))["literary"]["passages"][:20]
        h = [mine[ev].get(p["window_id"]) for p in ps]
        hp.append(sum(1 for x in h if x in ("yes", "mention")) / 20 if None not in h else None)
        mp.append(sum(1 for p in ps if J.get((ev, p["window_id"])) in ("yes", "mention")) / 20)
        print("%-22s hand P@20 %s   model P@20 %.2f" % (ev, "n/a" if hp[-1] is None else "%.2f" % hp[-1], mp[-1]))
    ok = [x for x in hp if x is not None]
    print("mean hand P@20 (%d events)" % len(ok), round(sum(ok) / len(ok), 3), " mean model P@20", round(sum(mp) / len(mp), 3))


if __name__ == "__main__":
    main(*sys.argv[1:])
