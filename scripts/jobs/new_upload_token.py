#!/usr/bin/env python3
"""Create the upload folder and token for a job, and print the token once.

    venv/bin/python scripts/jobs/new_upload_token.py <job-name>

The token goes to data/job_uploads/<job>/.token and is printed so it can be
passed to the job's command line. It is not stored anywhere else.

The web application runs as its own user, in the group that owns the data
folders, so the job folder is group-writable with the group inherited
(mode 2770) and the token is group-readable (mode 640). With 600 the first
real upload was refused as "no such job" (2026-10-03).
"""
import os
import re
import secrets
import sys

ROOT = os.environ.get('TESSERAE_JOB_UPLOADS', os.path.join('data', 'job_uploads'))


def main():
    if len(sys.argv) != 2 or not re.match(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$', sys.argv[1]):
        raise SystemExit('usage: new_upload_token.py <job-name>')
    os.makedirs(ROOT, exist_ok=True)
    folder = os.path.join(ROOT, sys.argv[1])
    os.makedirs(folder, exist_ok=True)
    gid = os.stat(os.path.dirname(os.path.abspath(ROOT))).st_gid
    for d in (ROOT, folder):
        try:
            os.chown(d, -1, gid)
        except OSError:
            pass
        os.chmod(d, 0o2770)
    token = secrets.token_urlsafe(32)
    path = os.path.join(folder, '.token')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(token + '\n')
    try:
        os.chown(path, -1, gid)
    except OSError:
        pass
    os.chmod(path, 0o640)
    print(token)


if __name__ == '__main__':
    main()
