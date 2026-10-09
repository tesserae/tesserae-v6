#!/usr/bin/env python3
"""Dossiers for every Wikidata event, with the fused ranking reordered by the offline relevance
judge, written into ONE SQLite file (events, passages, documents, scholarship, judgements, requests).

Usage: build_all_dossiers.py --events E --labels L --countries C --pleiades P --intros I --out-sqlite F
                             [--workers 16] [--lookahead 8] [--limit-events N] [--model M]
One process: gathering for event N+1 runs while the gateway answers for event N (the judge requests of
`lookahead` events are in flight at once, `workers` requests at a time). Restartable: events already
in the file (or in --skip-from files) are skipped, --shard i/n splits the list between processes (each with
its own --out-sqlite, merged afterwards with merge_dossiers.py), and judgements are cached in the same file.
An event with no name that matches anything falls back to the Theme Search ranking alone
(candidate_source = 'theme'). The key is read from the environment or ~/.config/tesserae/bullsai.env.
"""
import argparse, json, os, sys, time, traceback
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_event_dossier as b  # noqa: E402
import llm_judge as lj  # noqa: E402

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, label TEXT, type TEXT, date_start INTEGER, date_end INTEGER,
  place TEXT, lat REAL, lon REAL, pleiades_id TEXT, participants TEXT, wikipedia_title TEXT, description TEXT,
  candidate_source TEXT, n_candidates INTEGER, n_yes INTEGER, n_mention INTEGER, n_no INTEGER, status TEXT, seconds REAL);
CREATE TABLE IF NOT EXISTS passages (event_id TEXT, rank INTEGER, work TEXT, ref_start TEXT, ref_end TEXT, score REAL,
  llm_label TEXT, names_matched TEXT, snippet TEXT, window_id TEXT);
CREATE TABLE IF NOT EXISTS documents (event_id TEXT, doc_id TEXT, date_start INTEGER, date_end INTEGER, place TEXT,
  distance_km REAL, text_snippet TEXT);
CREATE TABLE IF NOT EXISTS scholarship (event_id TEXT, kind TEXT, title TEXT, page_ref TEXT, url TEXT);
CREATE INDEX IF NOT EXISTS ix_pass_ev ON passages(event_id);
CREATE INDEX IF NOT EXISTS ix_doc_ev ON documents(event_id);
CREATE INDEX IF NOT EXISTS ix_sch_ev ON scholarship(event_id);
"""


def centres_of(rec, countries, points):
    cs, first = [], None
    for l in b.specific_locations(rec, countries):
        c = None
        if l.get("pleiades") and l["pleiades"] in points:
            c = points[l["pleiades"]][:2]
        elif l.get("coord") and b.parse_point(l["coord"]):
            c = b.parse_point(l["coord"])
        if c:
            cs.append(c)
            first = first or (c, l.get("pleiades"))
    return cs, first


def main():
    ap = argparse.ArgumentParser()
    for k in ("events", "labels", "countries", "pleiades", "intros", "out-sqlite"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--model", default=lj.DEFAULT_MODEL)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--lookahead", type=int, default=8)
    ap.add_argument("--limit-events", type=int)
    ap.add_argument("--shard", default="0/1", help="i/n: take the events whose position in qid order is i modulo n")
    ap.add_argument("--skip-from", action="append", default=[], help="another dossier SQLite whose finished events are skipped")
    a = ap.parse_args()
    events, labels, countries = b.load_jsonl(a.events), b.load_jsonl(a.labels), b.load_jsonl(a.countries)
    intros = json.load(open(a.intros))
    points, crosswalk = b.load_points(a.pleiades), b.load_crosswalk()
    prod, theme = b.Prod(), b.Theme()
    from backend import translations as tmod
    tmod._DIR = os.path.join(prod.root, "data", "translations")
    tmod._index = None
    judge = lj.Judge(a.model, a.out_sqlite, a.workers)
    with judge.lock:
        judge.db.executescript(SCHEMA)
        judge.db.execute("PRAGMA journal_mode=WAL")
        done = {r[0] for r in judge.db.execute("SELECT id FROM events WHERE status='ok'")}
    import sqlite3
    for other in a.skip_from:
        c = sqlite3.connect(other)
        done |= {r[0] for r in c.execute("SELECT id FROM events WHERE status='ok'")}
        c.close()
    i_sh, n_sh = (int(x) for x in a.shard.split("/"))
    todo = [e for k, (_, e) in enumerate(sorted(events.items())) if k % n_sh == i_sh and e["qid"] not in done]
    if a.limit_events:
        todo = todo[:a.limit_events]
    print(f"events {len(events)} done {len(done)} to do {len(todo)}", file=sys.stderr, flush=True)
    pool = ThreadPoolExecutor(a.workers)
    pending, t_start, n_ok, n_err = [], time.time(), 0, 0

    def finalize(item):
        nonlocal n_ok, n_err
        rec, span, ents, lit, ctx, plist, futs, source, t0 = item
        qid = rec["qid"]
        try:
            for f in futs:
                f.result()
            labels_ = judge.labels_for(qid, plist)
            head = lit["passages"][:100]
            new = lj.rerank(head, labels_)
            for i, p in enumerate(new, 1):
                p["rank"], p["llm_label"] = i, labels_.get(p["window_id"])
            cnt = {k: sum(1 for p in new if p["llm_label"] == k) for k in ("yes", "mention", "no")}
            centres, first = centres_of(rec, countries, points)
            docs = b.documents(prod, span, centres, points, crosswalk, sample_cap=50)
            prim = [p for p in new if p["llm_label"] == "yes"][:5] or new[:5]
            sch = []
            for p in prim:
                lo, hi = b.parse_ref(p["ref_start"]), b.parse_ref(p["ref_end"])
                for c in b.citing(prod, p["work"], lo, hi, limit=8):
                    sch.append(("article", c["title"], f"{c['authors'] or ''} {c['journal'] or ''} {c['year'] or ''}, p. {c['page']}; cites {c['cites']}".strip(), c["url"]))
                for c in b.commentary(prod, p["work"], lo, hi, limit=3):
                    sch.append(("commentary", f"{c['commentator']} on {p['work']}", c["ref"], ""))
            places = [l["label"] for l in b.specific_locations(rec, countries) if l.get("label")]
            with judge.lock:
                db = judge.db
                db.execute("DELETE FROM events WHERE id=?", (qid,))
                for t in ("passages", "documents", "scholarship"):
                    db.execute(f"DELETE FROM {t} WHERE event_id=?", (qid,))
                db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (qid, rec["label"], ",".join(rec["types"]), span[0] if span else None, span[1] if span else None,
                            ", ".join(places), first[0][0] if first else None, first[0][1] if first else None, first[1] if first else None,
                            json.dumps([x["label"] for x in rec["participants"]], ensure_ascii=False), rec.get("wikipedia_title"),
                            rec.get("description"), source, len(new), cnt["yes"], cnt["mention"], cnt["no"], "ok", time.time() - t0))
                for p in new:
                    snip = (p["hit_lines"][0]["snippet"] if p.get("hit_lines") else p["text"])[:300]
                    db.execute("INSERT INTO passages VALUES (?,?,?,?,?,?,?,?,?,?)",
                               (qid, p["rank"], p["work"], p["ref_start"], p["ref_end"], p["score"], p["llm_label"],
                                json.dumps(p["matched"], ensure_ascii=False), snip, p["window_id"]))
                for d in docs["items"]:
                    db.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?)",
                               (qid, d["id"], d["not_before"], d["not_after"], d["place"], d["distance_km"],
                                f"{d['text_type'] or ''} / {d['object_type'] or ''}; {d['edition'] or ''}"[:300]))
                for k, t, pr, u in sch:
                    db.execute("INSERT INTO scholarship VALUES (?,?,?,?,?)", (qid, k, t, pr, u))
                db.commit()
            n_ok += 1
        except Exception as e:  # keep going; the event is recorded as an error
            n_err += 1
            traceback.print_exc()
            with judge.lock:
                judge.db.execute("INSERT OR REPLACE INTO events (id, label, status) VALUES (?,?,?)", (qid, rec["label"], "error: " + str(e)[:200]))
                judge.db.commit()
        if (n_ok + n_err) % 10 == 0:
            st = judge.stats()
            print(f"{n_ok + n_err} events ok {n_ok} err {n_err} requests {st['requests']} failed {st['failed']} "
                  f"elapsed {time.time() - t_start:.0f}s", file=sys.stderr, flush=True)

    for rec in todo:
        t0 = time.time()
        try:
            span = b.event_span(rec)
            ents = b.build_entities(rec, labels, countries, ())
            intro = intros.get(rec["qid"], {}).get("query") or rec.get("description") or rec["label"]
            theme.prepare(intro)
            lit = b.literary(prod, ents, span, limit=100, ranking="fused", theme=theme)
            source = "names+theme"
            if not lit["passages"]:
                lit = b.literary(prod, ents, span, limit=100, ranking="theme", theme=theme)
                source = "theme"
            ctx = b.llm_context(rec, ents, span, intro, countries)
            plist = [b.llm_passage(prod, p, tmod) for p in lit["passages"][:100]]
            futs = judge.submit(pool, rec["qid"], ctx, plist)
            pending.append((rec, span, ents, lit, ctx, plist, futs, source, t0))
        except Exception as e:
            n_err += 1
            traceback.print_exc()
            with judge.lock:
                judge.db.execute("INSERT OR REPLACE INTO events (id, label, status) VALUES (?,?,?)", (rec["qid"], rec["label"], "error: " + str(e)[:200]))
                judge.db.commit()
        while len(pending) >= a.lookahead:
            finalize(pending.pop(0))
    while pending:
        finalize(pending.pop(0))
    st = judge.stats()
    print("DONE events ok", n_ok, "errors", n_err, "requests", st["requests"], "failed", st["failed"],
          "prompt_tokens", st["prompt_tokens"], "completion_tokens", st["completion_tokens"],
          "wall_s", round(time.time() - t_start), file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
