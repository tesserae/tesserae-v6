#!/usr/bin/env python3
"""Rewrite stale `image_url` rows in a documents metadata.db.

  fix_image_urls.py --dry-run --db PATH   report rows per rule and rows left on dead hosts
  fix_image_urls.py --apply   --db PATH   back PATH up to PATH.bak-<date>, then rewrite
"""
from __future__ import annotations

import argparse
import collections
import datetime
import os
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from image_url_rules import host_of, is_dead, load_dead_hosts, rule_for  # noqa: E402


def scan(con):
    changes = []  # (rowid, old, new, rule)
    per_rule = collections.Counter()
    dead = collections.Counter()
    dead_hosts = load_dead_hosts()
    for rowid, value in con.execute(
            "SELECT rowid, value FROM display WHERE field='image_url'"):
        hit = rule_for(value)
        if hit:
            changes.append((rowid, value, hit[1], hit[0]))
            per_rule[hit[0]] += 1
        elif is_dead(value, dead_hosts):
            dead[host_of(value) or "(no host: bare file name)"] += 1
    return changes, per_rule, dead


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    con = sqlite3.connect(a.db)
    changes, per_rule, dead = scan(con)
    print("rows that would change, by rule:")
    for name, n in sorted(per_rule.items()):
        print(f"  {name}: {n}")
    print(f"  total: {len(changes)}")
    print(f"rows on dead hosts with no rule: {sum(dead.values())}")
    for h, n in dead.most_common():
        print(f"  {h}: {n}")
    if a.apply:
        bak = f"{a.db}.bak-{datetime.date.today().isoformat()}"
        con.close()
        shutil.copy2(a.db, bak)
        con = sqlite3.connect(a.db)
        with con:
            con.executemany("UPDATE display SET value=? WHERE rowid=?",
                            [(new, rid) for rid, _o, new, _r in changes])
        print(f"applied {len(changes)} rewrites; backup at {bak}")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
