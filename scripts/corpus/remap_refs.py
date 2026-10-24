"""Rewrite one work's old running references to a new reference shape in every store.

rename_work.py swaps a work-id prefix and keeps the rest of each reference. This
script changes the shape of the reference itself, through a lookup table: for the
Shahnameh, old `ferdowsi.shahnameh.N` (N = 1 to 99218) becomes
`ferdowsi.shahnameh.S.C.H` (story, couplet, hemistich). The map comes from
scripts/translations/shahnameh_warner/old_to_new_refs.py.

Usage:
    remap_refs.py --map OLD_TO_NEW.json --work ferdowsi.shahnameh \
        --new-tess NEW.tess --root ROOT [--dry-run] [--production]

ROOT is laid out like the production checkout (data/, cache/, backend/embeddings/,
texts/). --dry-run counts what each store would change and exits non-zero if any
store holds a reference of the work that the map cannot translate. A real run does
the same scan first and refuses before writing anything. REMAP_REPORT.json is
written in the current folder with, per store, rows examined, changed and
untranslatable (up to ten samples) and the elapsed time.

Stores, in this order: (1) data/inverted_index/fa_index.db, (2) passage index
window_texts.db and descriptions.jsonl, (3) cache/passage_density files (deleted),
(4) embeddings meta line_refs, (5) entities.sqlite, (6) reuse_pairs/fa.db,
(7) every cache/connections_map/*.db, (8) the lemma cache, (9) the text file last,
so a store is never ahead of the text. After each store a check confirms that the
old shape is gone and the row count is unchanged; the run stops at the first failure.

desc_fts.sqlite is not touched: it keys on the size and mtime of descriptions.jsonl
and rebuilds itself on the next use.

Requires the Python standard library only.
"""

import argparse
import glob
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
LEMMA_SCRIPT = os.path.join(
    REPO, "scripts", "translations", "shahnameh_warner", "remap_lemma_cache.py"
)
PRODUCTION = "/var/www/tesseraev6_flask"
SAMPLE_LIMIT = 10


class Refuse(Exception):
    """A check failed or a ref cannot be translated: stop, say which store."""


class Ctx:
    def __init__(self, args):
        self.work = args.work
        self.root = os.path.realpath(args.root)
        self.dry = args.dry_run
        self.new_tess = args.new_tess
        with open(args.map, encoding="utf-8") as f:
            self.map = json.load(f)
        self.prefix = args.work + "."
        # full old ref -> full new ref
        self.full = {self.prefix + k: v for k, v in self.map.items()}
        self.new_values = set(self.full.values())
        self.old_re = re.compile(r"^" + re.escape(self.prefix) + r"\d+$")
        self.report = {}
        self.strays = []

    def path(self, *parts):
        return os.path.join(self.root, *parts)


# ---------------------------------------------------------------- report helpers


def new_entry(name):
    return {
        "store": name,
        "rows_examined": 0,
        "rows_changed": 0,
        "rows_untranslatable": 0,
        "untranslatable_samples": [],
        "tables": {},
        "elapsed_s": 0.0,
    }


def add_table(entry, table, examined, changed, bad, samples):
    entry["tables"][table] = {
        "rows_examined": examined,
        "rows_changed": changed,
        "rows_untranslatable": bad,
        "untranslatable_samples": samples[:SAMPLE_LIMIT],
    }
    entry["rows_examined"] += examined
    entry["rows_changed"] += changed
    entry["rows_untranslatable"] += bad
    for s in samples:
        if len(entry["untranslatable_samples"]) < SAMPLE_LIMIT:
            entry["untranslatable_samples"].append(f"{table}: {s}")


# ---------------------------------------------------------------- sqlite helpers


def open_db(path):
    if not os.path.exists(path):
        raise Refuse(f"missing store {path}")
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("PRAGMA temp_store=FILE")
    return conn


def load_map(conn, ctx):
    conn.execute(
        "CREATE TEMP TABLE IF NOT EXISTS ref_map (old TEXT PRIMARY KEY, new TEXT)"
    )
    n = conn.execute("SELECT count(*) FROM ref_map").fetchone()[0]
    if n == 0:
        conn.executemany("INSERT INTO ref_map VALUES (?, ?)", ctx.full.items())


def scan(conn, ctx, table, col, cond, params=(), allow=None):
    """Return (examined, translatable_rows, untranslatable_rows, samples, stray_rows).

    allow(ref) -> True marks a ref as a known stray row (kept, listed).
    """
    sql = f"SELECT {col}, count(*) FROM {table} WHERE {cond} GROUP BY {col}"
    examined = ok = bad = stray = 0
    samples = []
    for ref, n in conn.execute(sql, params):
        examined += n
        if ref in ctx.full:
            ok += n
        elif allow is not None and allow(ref):
            stray += n
        else:
            bad += n
            if len(samples) < SAMPLE_LIMIT:
                samples.append(ref)
    return examined, ok, bad, samples, stray


def check_after(
    conn, ctx, name, table, col, cond, params, expected_examined, allow=None
):
    examined, ok, bad, samples, stray = scan(conn, ctx, table, col, cond, params, allow)
    if examined != expected_examined:
        raise Refuse(
            f"{name}: {table}.{col} row count changed {expected_examined} -> {examined}"
        )
    if ok:
        raise Refuse(f"{name}: {table}.{col} still holds {ok} rows in the old shape")
    # every remaining value must be a new value (or a known stray)
    for (ref,) in conn.execute(
        f"SELECT DISTINCT {col} FROM {table} WHERE {cond}", params
    ):
        if ref in ctx.new_values:
            continue
        if allow is not None and allow(ref):
            continue
        raise Refuse(f"{name}: {table}.{col} holds a value outside the map: {ref!r}")
    old = [
        r
        for (r,) in conn.execute(
            f"SELECT DISTINCT {col} FROM {table} WHERE {cond}", params
        )
        if ctx.old_re.match(r)
    ]
    if old:
        raise Refuse(f"{name}: {table}.{col} old shape left: {old[:5]}")


class Plan:
    """One (table, column, condition) triple of an SQLite store."""

    def __init__(self, table, col, cond, params=(), allow=None, label=None):
        self.table, self.col, self.cond, self.params, self.allow = (
            table,
            col,
            cond,
            tuple(params),
            allow,
        )
        self.label = label or f"{table}.{col}"
        self.examined = 0
        self.ok = 0


def run_sqlite_store(ctx, name, path, plans_for, extra_after=None):
    """Scan then (unless dry) rewrite each plan in one transaction per table."""
    entry = new_entry(name)
    t0 = time.time()
    conn = open_db(path)
    try:
        load_map(conn, ctx)
        plans = plans_for(conn)
        for p in plans:
            examined, ok, bad, samples, stray = scan(
                conn, ctx, p.table, p.col, p.cond, p.params, p.allow
            )
            p.examined, p.ok = examined, ok
            add_table(entry, p.label, examined, ok, bad, samples)
            if stray:
                ctx.strays.append(f"{name} {p.label}: {stray} stray rows left alone")
            if bad:
                entry["elapsed_s"] = round(time.time() - t0, 1)
                ctx.report[name] = entry
                raise Refuse(
                    f"{name}: {p.label} holds {bad} refs the map cannot translate, e.g. {samples}"
                )
        if not ctx.dry:
            for p in plans:
                conn.execute("BEGIN")
                try:
                    cur = conn.execute(
                        f"UPDATE {p.table} SET {p.col} = (SELECT new FROM ref_map WHERE old = {p.table}.{p.col}) "
                        f"WHERE {p.cond} AND {p.col} IN (SELECT old FROM ref_map)",
                        p.params,
                    )
                    if cur.rowcount != p.ok:
                        raise Refuse(
                            f"{name}: {p.label} updated {cur.rowcount} rows, expected {p.ok}"
                        )
                    conn.execute("COMMIT")
                except BaseException:
                    conn.execute("ROLLBACK")
                    raise
            for p in plans:
                check_after(
                    conn,
                    ctx,
                    name,
                    p.table,
                    p.col,
                    p.cond,
                    p.params,
                    p.examined,
                    p.allow,
                )
            if extra_after:
                extra_after(conn, entry)
    finally:
        conn.close()
        entry["elapsed_s"] = round(time.time() - t0, 1)
        ctx.report[name] = entry


# ---------------------------------------------------------------- the stores


def store_inverted_index(ctx):
    path = ctx.path("data", "inverted_index", "fa_index.db")
    holder = {}

    def plans_for(conn):
        row = conn.execute(
            "SELECT text_id FROM texts WHERE filename = ?", (ctx.work + ".tess",)
        ).fetchone()
        if not row:
            raise Refuse(f"fa_index.db has no text {ctx.work}.tess")
        tid = row[0]
        holder["tid"] = tid
        return [
            Plan("lines", "ref", "text_id = ?", (tid,)),
            Plan("postings", "ref", "text_id = ?", (tid,)),
        ]

    def extra(conn, entry):
        tid = holder["tid"]
        for table in ("lines", "postings"):
            n = conn.execute(
                f"SELECT count(DISTINCT ref) FROM {table} WHERE text_id = ?", (tid,)
            ).fetchone()[0]
            entry.setdefault("distinct_refs_after", {})[table] = n
            if n != len(ctx.full):
                raise Refuse(
                    f"fa_index.db {table} has {n} distinct refs, expected {len(ctx.full)}"
                )

    run_sqlite_store(ctx, "fa_index.db", path, plans_for, extra)


def store_window_texts(ctx):
    path = ctx.path("data", "passage_index", "window_texts.db")

    def plans_for(conn):
        w = (ctx.work,)
        return [
            Plan("window_texts", "ref_start", "work = ?", w),
            Plan("window_texts", "ref_end", "work = ?", w),
            Plan("lines", "ref", "work = ?", w),
        ]

    def extra(conn, entry):
        n = conn.execute(
            "SELECT count(*) FROM window_texts WHERE work LIKE ? AND work != ?",
            (ctx.work + ".%", ctx.work),
        ).fetchone()[0]
        entry["stray_windows_untouched"] = n
        ctx.strays.append(
            f"window_texts.db: {n} windows of works named {ctx.work}.* left untouched"
        )

    run_sqlite_store(ctx, "window_texts.db", path, plans_for, extra)


def store_descriptions(ctx):
    name = "descriptions.jsonl"
    entry = new_entry(name)
    t0 = time.time()
    path = ctx.path("data", "passage_index", name)
    if not os.path.exists(path):
        raise Refuse(f"missing store {path}")
    key = f'"work": {json.dumps(ctx.work)}'
    re_start = re.compile(r'"ref_start": "((?:[^"\\]|\\.)*)"')
    re_end = re.compile(r'"ref_end": "((?:[^"\\]|\\.)*)"')

    def rewrite(line):
        """Return (new_line, bad_refs). Only the two ref fields change."""
        obj = json.loads(line)
        bad = []
        new = line
        for field, rx in (("ref_start", re_start), ("ref_end", re_end)):
            old = obj.get(field)
            if old not in ctx.full:
                bad.append(old)
                continue
            m = rx.search(new)
            if not m or json.loads('"' + m.group(1) + '"') != old:
                bad.append(f"{field} not found as text")
                continue
            new = (
                new[: m.start(1)]
                + json.dumps(ctx.full[old], ensure_ascii=False)[1:-1]
                + new[m.end(1) :]
            )
        if not bad:
            check = json.loads(new)
            expect = dict(
                obj,
                ref_start=ctx.full[obj["ref_start"]],
                ref_end=ctx.full[obj["ref_end"]],
            )
            if check != expect:
                bad.append("rewritten line differs beyond the refs")
        return new, bad

    total = changed = other = bad_n = 0
    samples = []
    tmp = path + ".remap.tmp"
    out = None if ctx.dry else open(tmp, "w", encoding="utf-8", newline="")
    try:
        with open(path, encoding="utf-8", newline="") as f:
            for line in f:
                total += 1
                if key in line and json.loads(line).get("work") == ctx.work:
                    new, bad = rewrite(line)
                    if bad:
                        bad_n += 1
                        if len(samples) < SAMPLE_LIMIT:
                            samples.append(str(bad))
                    else:
                        changed += 1
                        if out:
                            out.write(new)
                    continue
                other += 1
                if out:
                    out.write(line)
    finally:
        if out:
            out.close()
    add_table(entry, "descriptions.jsonl lines", total, changed, bad_n, samples)
    entry["other_lines_unchanged"] = other
    entry["desc_fts_note"] = (
        "desc_fts.sqlite keys on descriptions.jsonl size and mtime and rebuilds itself on next use; not rebuilt here"
    )
    entry["elapsed_s"] = round(time.time() - t0, 1)
    ctx.report[name] = entry
    if bad_n:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise Refuse(
            f"{name}: {bad_n} lines of the work hold refs the map cannot translate, e.g. {samples}"
        )
    if ctx.dry:
        return
    # checks on the new file before it replaces the old one
    n_lines = n_work = 0
    with open(tmp, encoding="utf-8", newline="") as f:
        for line in f:
            n_lines += 1
            if key in line:
                o = json.loads(line)
                if o.get("work") == ctx.work:
                    n_work += 1
                    for fld in ("ref_start", "ref_end"):
                        if o[fld] not in ctx.new_values:
                            raise Refuse(
                                f"{name}: new file holds a ref outside the map: {o[fld]!r}"
                            )
    if n_lines != total or n_work != changed:
        raise Refuse(
            f"{name}: line counts changed ({total} -> {n_lines}, work {changed} -> {n_work})"
        )
    os.replace(tmp, path)
    entry["lines_after"] = n_lines
    entry["work_lines_after"] = n_work
    entry["elapsed_s"] = round(time.time() - t0, 1)


def store_passage_density(ctx):
    name = "passage_density"
    entry = new_entry(name)
    t0 = time.time()
    files = sorted(
        glob.glob(ctx.path("cache", "passage_density", f"*.{ctx.work}.*.json"))
    )
    add_table(entry, "files", len(files), len(files), 0, [])
    entry["files_deleted"] = [os.path.basename(p) for p in files]
    if not ctx.dry:
        for p in files:
            os.remove(p)
        left = glob.glob(ctx.path("cache", "passage_density", f"*.{ctx.work}.*.json"))
        if left:
            raise Refuse(f"{name}: files left {left}")
    entry["elapsed_s"] = round(time.time() - t0, 1)
    ctx.report[name] = entry


def store_embeddings_meta(ctx):
    name = "embeddings_meta"
    entry = new_entry(name)
    t0 = time.time()
    path = ctx.path("backend", "embeddings", "fa", ctx.work + ".meta.json")
    if not os.path.exists(path):
        raise Refuse(f"missing store {path}")
    with open(path, encoding="utf-8") as f:
        meta = json.load(f)
    refs = meta["line_refs"]
    bad = [r for r in refs if r not in ctx.full]
    add_table(entry, "line_refs", len(refs), len(refs) - len(bad), len(bad), bad)
    entry["elapsed_s"] = round(time.time() - t0, 1)
    ctx.report[name] = entry
    if bad:
        raise Refuse(
            f"{name}: {len(bad)} line_refs the map cannot translate, e.g. {bad[:SAMPLE_LIMIT]}"
        )
    if ctx.dry:
        return
    new_refs = [ctx.full[r] for r in refs]
    tags = tess_tags(ctx.new_tess)
    if new_refs != tags:
        raise Refuse(f"{name}: new line_refs differ from the tags of {ctx.new_tess}")
    meta["line_refs"] = new_refs
    tmp = path + ".remap.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    os.replace(tmp, path)
    with open(path, encoding="utf-8") as f:
        again = json.load(f)["line_refs"]
    if again != tags or len(again) != len(refs):
        raise Refuse(f"{name}: written line_refs failed the re-read")
    entry["elapsed_s"] = round(time.time() - t0, 1)


def store_entities(ctx):
    path = ctx.path("data", "entity_index", "entities.sqlite")
    win = "wid IN (SELECT wid FROM windows WHERE work = ?)"

    def plans_for(conn):
        w = (ctx.work,)
        return [
            Plan("windows", "ref_start", "work = ?", w),
            Plan("windows", "ref_end", "work = ?", w),
            Plan("mention_rows", "line_ref", win, w),
        ]

    run_sqlite_store(ctx, "entities.sqlite", path, plans_for)


def store_reuse(ctx):
    path = ctx.path("cache", "reuse_pairs", "fa.db")

    def plans_for(conn):
        w = (ctx.work,)
        return [
            Plan("pairs", "line_a_ref", "work_a = ?", w),
            Plan("pairs", "line_b_ref", "work_b = ?", w),
            Plan("line_counts", "line_ref", "work = ?", w),
        ]

    run_sqlite_store(ctx, "reuse_pairs/fa.db", path, plans_for)


def store_connections_maps(ctx):
    paths = sorted(glob.glob(ctx.path("cache", "connections_map", "*.db")))
    if not paths:
        raise Refuse("no cache/connections_map/*.db found")
    stray_prefix = ctx.work + ".part."

    for p in paths:
        name = "connections_map/" + os.path.basename(p)
        # windows of the work whose id is the work's own (the stray part.N windows keep their refs)
        cond = "work = ? AND id NOT LIKE ?"
        params = (ctx.work, stray_prefix + "%")

        def plans_for(conn, cond=cond, params=params):
            return [
                Plan("windows", "ref_start", cond, params),
                Plan("windows", "ref_end", cond, params),
            ]

        def extra(conn, entry, name=name):
            n = conn.execute(
                "SELECT count(*) FROM windows WHERE work = ? AND id LIKE ?",
                (ctx.work, stray_prefix + "%"),
            ).fetchone()[0]
            entry["stray_windows_untouched"] = n
            ctx.strays.append(
                f"{name}: {n} windows with id {stray_prefix}* left untouched"
            )

        run_sqlite_store(ctx, name, p, plans_for, extra)


def lemma_module():
    spec = importlib.util.spec_from_file_location("remap_lemma_cache", LEMMA_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def store_lemma_cache(ctx):
    name = "lemma_cache"
    entry = new_entry(name)
    t0 = time.time()
    found = glob.glob(ctx.path("cache", "lemmas", "fa", ctx.work + "-*.json"))
    if len(found) != 1:
        raise Refuse(f"{name}: expected one lemma cache for {ctx.work}, found {found}")
    path = found[0]
    with open(path, encoding="utf-8") as f:
        cache = json.load(f)
    mod = lemma_module()
    bad = []
    n_line = len(cache["units_line"])
    n_phrase = len(cache.get("units_phrase", []))
    for u in cache["units_line"]:
        try:
            mod.new_ref(u["ref"], ctx.map)
        except SystemExit as e:
            bad.append(str(e))
    for u in cache.get("units_phrase", []):
        for r in [*u["ref"].split("-", 1), *u.get("line_refs", [])]:
            try:
                mod.new_ref(r, ctx.map)
            except SystemExit as e:
                bad.append(str(e))
    add_table(
        entry,
        "units_line + units_phrase",
        n_line + n_phrase,
        n_line + n_phrase - len(bad),
        len(bad),
        bad,
    )
    entry["units_line"] = n_line
    entry["units_phrase"] = n_phrase
    entry["elapsed_s"] = round(time.time() - t0, 1)
    ctx.report[name] = entry
    if bad:
        raise Refuse(
            f"{name}: refs the map cannot translate, e.g. {bad[:SAMPLE_LIMIT]}"
        )
    if ctx.dry:
        return
    del cache
    tmp = path + ".remap.tmp"
    import subprocess

    done = subprocess.run(
        [sys.executable, LEMMA_SCRIPT, path, ctx.new_tess, ctx.map_path, tmp],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        raise Refuse(
            f"{name}: remap_lemma_cache.py failed: {done.stdout[-300:]} {done.stderr[-300:]}"
        )
    with open(tmp, encoding="utf-8") as f:
        new = json.load(f)
    tags = tess_tags(ctx.new_tess)
    if [u["ref"] for u in new["units_line"]] != tags:
        raise Refuse(f"{name}: units_line refs differ from the new file's tags")
    if len(new.get("units_phrase", [])) != n_phrase:
        raise Refuse(f"{name}: units_phrase count changed")
    shape = re.compile(re.escape(ctx.work) + r"\.\d+\.\d+\.[12]$")
    for u in new["units_phrase"]:
        for r in [*u["ref"].split("-", 1), *u.get("line_refs", [])]:
            if not shape.match(r):
                raise Refuse(f"{name}: phrase ref not in the new shape: {r!r}")
    with open(ctx.new_tess, "rb") as f:
        md5 = hashlib.md5(f.read()).hexdigest()  # nosec B324: cache key, not security
    if new["file_hash"] != md5:
        raise Refuse(f"{name}: file_hash is not the md5 of the new text")
    os.replace(tmp, path)
    entry["file_hash"] = md5
    entry["elapsed_s"] = round(time.time() - t0, 1)


def store_text(ctx):
    name = "text_file"
    entry = new_entry(name)
    t0 = time.time()
    dest = ctx.path("texts", "fa", ctx.work + ".tess")
    if not os.path.exists(dest):
        raise Refuse(f"missing {dest}")
    n_old = len(tess_tags(dest))
    n_new = len(tess_tags(ctx.new_tess))
    add_table(entry, "lines", n_old, n_old, 0, [])
    ctx.report[name] = entry
    if n_old != n_new:
        raise Refuse(f"{name}: line count differs ({n_old} old, {n_new} new)")
    if not ctx.dry:
        tmp = dest + ".remap.tmp"
        shutil.copyfile(ctx.new_tess, tmp)
        os.replace(tmp, dest)
        with open(dest, "rb") as a, open(ctx.new_tess, "rb") as b:
            if hashlib.md5(a.read()).digest() != hashlib.md5(b.read()).digest():
                raise Refuse(f"{name}: installed file differs from the new file")
    entry["elapsed_s"] = round(time.time() - t0, 1)


def tess_tags(path):
    with open(path, encoding="utf-8") as f:
        return [line.split("\t", 1)[0].strip("<>") for line in f if line.strip()]


# ---------------------------------------------------------------- main

STORES = [
    store_inverted_index,
    store_window_texts,
    store_descriptions,
    store_passage_density,
    store_embeddings_meta,
    store_entities,
    store_reuse,
    store_connections_maps,
    store_lemma_cache,
    store_text,
]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--map", required=True, help="old_to_new_refs.json")
    ap.add_argument("--work", required=True)
    ap.add_argument("--new-tess", required=True, help="the re-tagged .tess file")
    ap.add_argument("--root", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--production",
        action="store_true",
        help="required when ROOT is the production checkout",
    )
    args = ap.parse_args(argv)
    ctx = Ctx(args)
    ctx.map_path = os.path.abspath(args.map)
    if (
        os.path.realpath(ctx.root).startswith(PRODUCTION)
        and not args.production
        and not args.dry_run
    ):
        print(
            "refusing: ROOT is the production checkout and --production was not given",
            file=sys.stderr,
        )
        return 2
    t0 = time.time()
    rc = 0
    failed = None
    # pass 1: scan every store (nothing written); pass 2 (unless dry): write in order
    phases = ["scan"] if ctx.dry else ["scan", "write"]
    try:
        for phase in phases:
            ctx.dry_saved = ctx.dry
            ctx.dry = phase == "scan" or args.dry_run
            for fn in STORES:
                print(f"[{phase}] {fn.__name__}", flush=True)
                fn(ctx)
            if phase == "scan":
                for k, v in ctx.report.items():
                    print(
                        f"  {k}: examined {v['rows_examined']}, would change {v['rows_changed']}, untranslatable {v['rows_untranslatable']}"
                    )
                scan_report = {k: dict(v) for k, v in ctx.report.items()}
                ctx.report = {}
        if not ctx.dry_saved:
            ctx.report["_scan_before_writing"] = scan_report
    except Refuse as e:
        failed = str(e)
        rc = 1
        print(f"STOP: {failed}", file=sys.stderr)
    out = {
        "work": ctx.work,
        "root": ctx.root,
        "dry_run": args.dry_run,
        "ok": failed is None,
        "failure": failed,
        "notes": ctx.strays,
        "elapsed_s": round(time.time() - t0, 1),
        "stores": ctx.report,
    }
    with open("REMAP_REPORT.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"done in {out['elapsed_s']} s, ok={out['ok']}; REMAP_REPORT.json written")
    return rc


if __name__ == "__main__":
    sys.exit(main())
