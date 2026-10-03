#!/usr/bin/env python3
"""Create the upload folder and token for a job, and print the token once.

    venv/bin/python scripts/jobs/new_upload_token.py <job-name>

The token goes to data/job_uploads/<job>/.token (mode 600) and is printed so
it can be passed to the job's command line. It is not stored anywhere else.
"""
import os
import re
import secrets
import sys

ROOT = os.environ.get('TESSERAE_JOB_UPLOADS', os.path.join('data', 'job_uploads'))


def main():
    if len(sys.argv) != 2 or not re.match(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$', sys.argv[1]):
        raise SystemExit('usage: new_upload_token.py <job-name>')
    folder = os.path.join(ROOT, sys.argv[1])
    os.makedirs(folder, exist_ok=True)
    token = secrets.token_urlsafe(32)
    path = os.path.join(folder, '.token')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(token + '\n')
    os.chmod(path, 0o600)
    print(token)


if __name__ == '__main__':
    main()
