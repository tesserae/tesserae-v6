#!/usr/bin/env python3
"""Where the corpus is thin: summary of the dossier SQLite written by build_all_dossiers.py.

Usage: summarize_dossiers.py DOSSIERS.sqlite
Prints events completed, requests and tokens, the distribution of yes-labelled passages per event
(0, 1 to 5, 6 to 20, more), the same by era and by candidate source, the 20 events with the most
yes passages and 20 with none (the ones with the most 'mention' passages first, the near misses).
"""
import sqlite3, sys


def era(y):
    if y is None:
        return "no date"
    return "800-301 BC" if y <= -301 else "300-31 BC" if y <= -31 else "30 BC-AD 300" if y <= 300 else "AD 301-600"


def main(path):
    db = sqlite3.connect(path)
    n_ok, n_err = db.execute("SELECT sum(status='ok'), sum(status!='ok') FROM events").fetchone()
    print("events ok", n_ok, "errors", n_err)
    r = db.execute("SELECT count(*), sum(seconds), sum(prompt_tokens), sum(completion_tokens), sum(status!='ok'), min(ts), max(ts) FROM requests").fetchone()
    print("requests", r[0], "failed", r[4], "prompt tokens", r[2], "completion tokens", r[3], "first-to-last request s", round(r[6] - r[5]))
    print("judgements", db.execute("SELECT count(*) FROM judgements").fetchone()[0],
          "passages", db.execute("SELECT count(*) FROM passages").fetchone()[0],
          "documents", db.execute("SELECT count(*) FROM documents").fetchone()[0],
          "scholarship rows", db.execute("SELECT count(*) FROM scholarship").fetchone()[0])
    rows = db.execute("SELECT id,label,type,date_start,candidate_source,n_candidates,n_yes,n_mention FROM events WHERE status='ok'").fetchall()
    bins = lambda y: "0" if y == 0 else "1-5" if y <= 5 else "6-20" if y <= 20 else "more than 20"
    order = ("0", "1-5", "6-20", "more than 20")

    def dist(sel, title):
        c = {k: 0 for k in order}
        for r_ in sel:
            c[bins(r_[6])] += 1
        print(title, c, "total", len(sel))

    dist(rows, "yes passages per event")
    for e in ("800-301 BC", "300-31 BC", "30 BC-AD 300", "AD 301-600"):
        dist([r_ for r_ in rows if era(r_[3]) == e], "  " + e)
    for s in ("names+theme", "theme"):
        dist([r_ for r_ in rows if r_[4] == s], "  source " + s)
    for t in ("battle", "siege", "military campaign", "treaty"):
        dist([r_ for r_ in rows if t in r_[2].split(",")], "  type " + t)
    print("\n20 events with the most yes passages")
    for r_ in sorted(rows, key=lambda x: (-x[6], x[1]))[:20]:
        print("  %-12s %-52s %5s yes %3d mention %3d  (%s)" % (r_[0], r_[1][:52], r_[3], r_[6], r_[7], r_[4]))
    print("\n20 events with no yes passage (most mentions first)")
    for r_ in sorted([x for x in rows if x[6] == 0], key=lambda x: (-x[7], x[1]))[:20]:
        print("  %-12s %-52s %5s yes %3d mention %3d  cand %3d (%s)" % (r_[0], r_[1][:52], r_[3], r_[6], r_[7], r_[5], r_[4]))


if __name__ == "__main__":
    main(sys.argv[1])
