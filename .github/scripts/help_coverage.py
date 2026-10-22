#!/usr/bin/env python3
"""Fail a pull request that changes what a visitor sees or gets without touching Help.

The project lead asked (2026-10-22) for a process, so that Help is updated with every change without a
reminder. A pull request passes when one of these holds:
  - it changes no file a visitor can see the effect of (only tests, scripts, docs, data records),
  - it changes the Help page (client/src/components/pages/HelpPage.jsx) or the per-search
    "What this search does" boxes (client/src/data/searchScope.js),
  - its description has a line beginning "Help: not needed" with a reason, which the reviewer reads.
Tessa reads the Help page for her answers (backend/assistant/site_help.py), so Help kept current also
keeps her current.

    help_coverage.py BASE_SHA HEAD_SHA        (the description is read from PR_BODY)
"""
import os
import re
import subprocess
import sys

HELP_FILES = ('client/src/components/pages/HelpPage.jsx', 'client/src/data/searchScope.js')
VISIBLE = (re.compile(r'^client/src/'), re.compile(r'^backend/'), re.compile(r'^services/'))
NOT_VISIBLE = (re.compile(r'(^|/)tests?/'), re.compile(r'\.test\.(js|jsx|ts|tsx)$'), re.compile(r'(^|/)__tests__/'),
               re.compile(r'^backend/synonymy/.*\.bak$'))
WAIVER = re.compile(r'^\s*Help:\s*not needed\b.{8,}', re.IGNORECASE | re.MULTILINE)


def visible(path):
    return any(p.search(path) for p in VISIBLE) and not any(p.search(path) for p in NOT_VISIBLE)


def check(changed, body):
    """(ok, message) for the changed paths and the pull request description."""
    shown = [p for p in changed if visible(p)]
    if not shown:
        return True, 'no visitor-facing file changed'
    if any(p in HELP_FILES for p in changed):
        return True, 'Help changed alongside the code'
    if WAIVER.search(body or ''):
        return True, 'description says Help is not needed: ' + WAIVER.search(body).group(0).strip()
    return False, ('This pull request changes visitor-facing code (' + ', '.join(shown[:6])
                   + (' ...' if len(shown) > 6 else '') + ') but not Help. Update '
                   + ' or '.join(HELP_FILES) + ', or add a line "Help: not needed, <reason>" to the description.')


def main(base, head):
    out = subprocess.run(['git', 'diff', '--name-only', f'{base}...{head}'], capture_output=True, text=True, check=True)
    ok, msg = check([p for p in out.stdout.splitlines() if p], os.environ.get('PR_BODY', ''))
    print(('PASS: ' if ok else 'FAIL: ') + msg)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2]))
