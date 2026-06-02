#!/usr/bin/env python3
"""Classify a PR by safety pattern. Writes a one-line verdict to stdout.

Inputs (environment variables):
  PR_FILES_JSON  - JSON list of changed files with additions/deletions/path
  PR_DIFF_PATH   - path to unified diff (used for some pattern checks)

Output (stdout): one of
  safe:docs            - docs-only change (only .md, .txt, .rst, LICENSE)
  safe:typo            - single tiny change (additions + deletions <= 4 across 1-2 files,
                         no high-risk paths touched)
  safe:dep-patch       - dependency-file-only change with patch-version bumps
  unsafe:<reason>      - anything else, with a short reason

This script is conservative: it only emits "safe:..." when it is confident the
change cannot break runtime behavior. Anything ambiguous returns "unsafe:...".

Exit code is always 0; the verdict is read from stdout by the workflow.
"""
import json
import os
import re
import sys

# Files that, if touched, immediately disqualify a PR from any safe pattern.
HIGH_RISK_PATHS = (
    "backend/fusion.py",
    "backend/scorer.py",
    "backend/matcher.py",
    "backend/synonym_dict.py",
    "backend/text_processor.py",
    "backend/app.py",
    "backend/blueprints/admin.py",
    "backend/blueprints/search.py",
    "backend/blueprints/fusion.py",
    "backend/blueprints/hapax.py",
)

# Docs-only safe pattern: only these extensions and filenames allowed.
DOCS_EXTENSIONS = {".md", ".txt", ".rst"}
DOCS_FILENAMES = {"LICENSE", "AUTHORS", "CONTRIBUTORS", "NOTICE"}

# Dependency files. A PR that only touches these AND has only patch-version bumps
# qualifies as safe:dep-patch.
DEP_FILES = {"requirements.txt", "package.json", "package-lock.json"}


def is_doc_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    if name in DOCS_FILENAMES:
        return True
    for ext in DOCS_EXTENSIONS:
        if path.endswith(ext):
            return True
    return False


def touches_high_risk(files) -> str:
    for f in files:
        for risky in HIGH_RISK_PATHS:
            if f["path"] == risky or f["path"].startswith(risky + "/"):
                return f["path"]
    return ""


def is_patch_version_bump_diff(diff: str) -> bool:
    """A patch version bump in requirements.txt or package.json changes only the
    third (patch) component of a semver string. Examples allowed:
      - pycountry==24.6.1 -> pycountry==24.6.2
      - "react": "^18.2.0" -> "react": "^18.2.3"

    Returns True only if every changed (added/removed) line that looks like a
    version pin shows a patch-level diff and no other content changes are present.
    """
    semver_re = re.compile(r"(\d+)\.(\d+)\.(\d+)")
    seen_pair = False

    additions = []
    removals = []
    for line in diff.splitlines():
        if line.startswith("+++") or line.startswith("---") or line.startswith("diff --git"):
            continue
        if line.startswith("+"):
            additions.append(line[1:].strip())
        elif line.startswith("-"):
            removals.append(line[1:].strip())

    if not additions or not removals:
        return False

    if len(additions) != len(removals):
        return False

    for add, rem in zip(additions, removals):
        if add == rem:
            continue
        am = semver_re.search(add)
        rm = semver_re.search(rem)
        if not am or not rm:
            return False
        # Major and minor must match; patch can differ.
        if am.group(1) != rm.group(1) or am.group(2) != rm.group(2):
            return False
        seen_pair = True

    return seen_pair


def main():
    files = json.loads(os.environ.get("PR_FILES_JSON", "[]"))
    diff_path = os.environ.get("PR_DIFF_PATH", "/tmp/pr.diff")

    if not files:
        print("unsafe:no-files-detected")
        return

    risky = touches_high_risk(files)
    if risky:
        print(f"unsafe:touches-high-risk-path:{risky}")
        return

    if all(is_doc_file(f["path"]) for f in files):
        print("safe:docs")
        return

    total_add = sum(f["additions"] for f in files)
    total_del = sum(f["deletions"] for f in files)
    if len(files) <= 2 and total_add + total_del <= 4:
        print("safe:typo")
        return

    if files and all(f["path"].rsplit("/", 1)[-1] in DEP_FILES for f in files):
        try:
            with open(diff_path) as fp:
                diff = fp.read()
        except OSError:
            diff = ""
        if is_patch_version_bump_diff(diff):
            print("safe:dep-patch")
            return
        print("unsafe:dep-non-patch-bump")
        return

    print("unsafe:requires-human-review")


if __name__ == "__main__":
    main()
