"""Keep the assistant's questions and answers for review.

Nothing else checks what the assistant says to real readers: the guards catch
an invented citation or figure, but a wrong date offered as background, or a
recommendation of the wrong search, passes them. So every answer is kept, one
JSON line per exchange, in a file per day under logs/assistant/ on the server,
and a sample is read each week (scripts/assistant_record_review.py) so that
failures become graded test items.

What is kept: the time, the route, the question, the answer, which model
answered, the guards' verdicts and the background check's. What is never kept:
an address, a cookie, a session or user identifier. The record stays on the
server; nothing here sends it anywhere.

TESSERAE_ASSISTANT_RECORD names the directory, or "0" turns the record off.
"""
import json
import os
import threading
import time

from backend.logging_config import get_logger

logger = get_logger('assistant.record')

_DEFAULT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'logs', 'assistant')
_lock = threading.Lock()


def record_dir():
    env = os.environ.get('TESSERAE_ASSISTANT_RECORD')
    if env is not None and env.strip() == '0':
        return None
    return (env or '').strip() or _DEFAULT_DIR


def record(kind, question, answer, **extra):
    """Append one exchange. Returns True when a line was written."""
    d = record_dir()
    if not d:
        return False
    row = {'ts': time.strftime('%Y-%m-%dT%H:%M:%S'), 'kind': kind,
           'question': (question or '')[:2000], 'answer': (answer or '')[:6000]}
    row.update({k: v for k, v in extra.items() if v is not None})
    try:
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, time.strftime('%Y-%m-%d') + '.jsonl')
        with _lock, open(path, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')
        return True
    except OSError as e:
        logger.info('[ASSISTANT] record not written: %s', e)
        return False
