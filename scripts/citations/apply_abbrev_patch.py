#!/usr/bin/env python3
"""Apply an abbreviation patch (data/citations/abbrev_patch_round*.json) to
the citation abbreviation table.

    apply_abbrev_patch.py PATCH TABLE            # dry run: prints what it would add
    apply_abbrev_patch.py PATCH TABLE --apply    # writes TABLE, backup beside it

The patch lists, per base_id, abbreviations to append to that work's record.
A `new_work` record is used only when the base_id is not in the table yet.

Rules:
- Idempotent: a form the work already carries (compared the way the
  recognizer compares them: lowercase, no periods, collapsed spaces) is
  skipped, so a second run adds nothing.
- Before writing, TABLE is copied beside itself as TABLE.bak-YYYYMMDD-HHMMSS
  (to the second, so a rerun never overwrites an earlier backup).
- Refuses (exit 2) when a form already resolves, in the table or in
  backend/citations/abbrev_aliases.json, to a work that is not in the patch
  for that same form, unless --force. A form the patch gives to several works
  (an intended ambiguity such as "Rust." for Varro and Columella) is not a
  conflict among them.
"""
import argparse
import json
import os
import shutil
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from backend.citations.abbrev_index import AbbrevIndex, normalize_abbr  # noqa: E402


def plan(patch, table_path):
    """Returns (additions, new_works, conflicts). additions: [(base_id,
    form)]; conflicts: [(form, base_id, existing_base_id)]."""
    with open(table_path, encoding="utf-8") as f:
        works = json.load(f)["works"]
    by_id = {w["base_id"]: w for w in works}
    idx = AbbrevIndex(table_path)
    patch_works = patch["works"]

    owners = {}  # normalized form -> base_ids the patch gives it to
    for base_id, spec in patch_works.items():
        for form in spec["abbreviations"]:
            owners.setdefault(normalize_abbr(form), set()).add(base_id)

    additions, new_works, conflicts = [], [], []
    for base_id, spec in patch_works.items():
        rec = by_id.get(base_id)
        if rec is None:
            if "new_work" not in spec:
                raise SystemExit("base_id %s is not in the table and the patch has no new_work for it" % base_id)
            new_works.append(base_id)
        have = set()
        if rec is not None:
            have = {normalize_abbr(x) for x in rec.get("abbreviations", [])}
        for form in spec["abbreviations"]:
            key = normalize_abbr(form)
            if key in have:
                continue
            have.add(key)
            for existing, _prio, _src in idx.index.get(key, []):
                if existing != base_id and existing not in owners[key]:
                    conflicts.append((form, base_id, existing))
            additions.append((base_id, form))
    return additions, new_works, conflicts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("patch")
    ap.add_argument("table")
    ap.add_argument("--apply", action="store_true", help="write the table (default: dry run)")
    ap.add_argument("--force", action="store_true", help="add forms that already resolve to another work")
    args = ap.parse_args()

    with open(args.patch, encoding="utf-8") as f:
        patch = json.load(f)
    additions, new_works, conflicts = plan(patch, args.table)

    for form, base_id, existing in conflicts:
        print("CONFLICT: %r for %s already resolves to %s" % (form, base_id, existing))
    if conflicts and not args.force:
        print("refusing: %d conflict(s); rerun with --force to add them anyway" % len(conflicts))
        return 2

    for base_id in new_works:
        print("new work:", base_id)
    for base_id, form in additions:
        print("add: %-48s %s" % (base_id, form))
    print("%d form(s) to add, %d new work(s)" % (len(additions), len(new_works)))
    if not args.apply:
        print("dry run: nothing written")
        return 0
    if not additions and not new_works:
        print("nothing to do")
        return 0

    with open(args.table, encoding="utf-8") as f:
        data = json.load(f)
    by_id = {w["base_id"]: w for w in data["works"]}
    for base_id in new_works:
        rec = dict(patch["works"][base_id]["new_work"])
        rec["abbreviations"] = []
        data["works"].append(rec)
        by_id[base_id] = rec
    for base_id, form in additions:
        by_id[base_id]["abbreviations"].append(form)

    backup = args.table + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
    if os.path.exists(backup):
        raise SystemExit("backup %s already exists; wait a second and rerun" % backup)
    shutil.copy2(args.table, backup)
    tmp = args.table + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, args.table)
    print("wrote %s (backup %s)" % (args.table, backup))
    return 0


if __name__ == "__main__":
    sys.exit(main())
