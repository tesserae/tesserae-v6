"""The trained free reader model, as its own small service.

WHY THIS EXISTS

Theme Search's "reader at the top" re-ranking scores the query against up to
a hundred candidate passages with a small cross-encoder trained on paid
Sonnet-5 reads (see evaluation/theme_benchmark/distill_train/REPORT.md).
That model has to load torch and a checkpoint, which is the exact trade this
codebase already ruled against for the web application: Apache runs three
worker processes that recycle every 1000 requests, so a model loaded inside
the app would sit in memory three times over and reload on every recycle.

So the model runs here instead, once, in one process, with a hard memory
cap, and the web application asks it for scores over loopback -- the same
shape as services/embed_server.py, the query encoder behind Theme Search's
free-text box. If this service is down, Theme Search re-ranking is simply
skipped and the plain index order stands; nothing else on the site notices.

Unlike embed_server.py, this loads the checkpoint at STARTUP, not on first
request: a re-rank call is already on the clock for a live page load, and
the first request should not be the one that pays a cold load.
"""
import json
import logging
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

READER_MODEL_DIR = os.environ.get(
    'READER_MODEL_DIR',
    '/home/ncoffee/tesserae-v6-dev/evaluation/theme_benchmark/distill_train/runs/minilm/best')
READER_THREADS = int(os.environ.get('READER_THREADS', '8'))
HOST = os.environ.get('TESSERAE_READER_HOST', '127.0.0.1')
PORT = int(os.environ.get('TESSERAE_READER_PORT', '8091'))

BATCH_SIZE = 32
MAX_LENGTH = 512
# A malformed or hostile request should not turn into an unbounded scoring
# job on a shared machine; a hundred is the largest Theme Search actually
# asks for (THEME_READER_K), so this leaves real headroom above that.
MAX_PASSAGES = 400

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - reader - %(levelname)s - %(message)s')
log = logging.getLogger('reader')

_model = None
_tokenizer = None
_loaded_at = None


def load_model():
    """Load the checkpoint once, at process start. Not lazy: see the module
    docstring for why this differs from embed_server.py."""
    global _model, _tokenizer, _loaded_at
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    torch.set_num_threads(READER_THREADS)
    log.info('loading reader checkpoint from %s (torch threads=%d)',
             READER_MODEL_DIR, READER_THREADS)
    _tokenizer = AutoTokenizer.from_pretrained(READER_MODEL_DIR)
    _model = AutoModelForSequenceClassification.from_pretrained(READER_MODEL_DIR)
    _model.eval()
    _loaded_at = time.time()
    log.info('reader model ready')


def score_passages(query, passages):
    """passages: [{"id": str, "text": str}, ...]. Returns {id: float}."""
    import torch

    scores = {}
    with torch.no_grad():
        for i in range(0, len(passages), BATCH_SIZE):
            batch = passages[i:i + BATCH_SIZE]
            queries = [query] * len(batch)
            texts = [p.get('text') or '' for p in batch]
            enc = _tokenizer(queries, texts, truncation=True, max_length=MAX_LENGTH,
                             padding=True, return_tensors='pt')
            logits = _model(**enc).logits.view(-1)
            probs = torch.sigmoid(logits).tolist()
            for p, s in zip(batch, probs):
                scores[p['id']] = float(s)
    return scores


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def _send(self, code, payload):
        body = json.dumps(payload).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith('/health'):
            self._send(200, {'ok': True, 'model': READER_MODEL_DIR,
                             'loaded_at': _loaded_at})
        else:
            self._send(404, {'error': 'not found'})

    def do_POST(self):
        if not self.path.startswith('/score'):
            self._send(404, {'error': 'not found'})
            return
        try:
            n = int(self.headers.get('Content-Length') or 0)
            data = json.loads(self.rfile.read(n) or b'{}')
        except (ValueError, TypeError) as e:
            self._send(400, {'error': f'bad request: {e}'})
            return

        query = data.get('query')
        passages = data.get('passages')
        if not isinstance(query, str) or not query.strip():
            self._send(400, {'error': 'query must be a non-empty string'})
            return
        if not isinstance(passages, list) or not passages:
            self._send(400, {'error': 'passages must be a non-empty list'})
            return
        if len(passages) > MAX_PASSAGES:
            self._send(400, {'error': f'at most {MAX_PASSAGES} passages per call, '
                                      f'got {len(passages)}'})
            return
        for p in passages:
            if not isinstance(p, dict) or 'id' not in p or 'text' not in p:
                self._send(400, {'error': 'each passage needs an id and a text'})
                return

        t0 = time.time()
        try:
            scores = score_passages(query, passages)
        except Exception as e:                      # never take the service down
            log.exception('scoring failed')
            self._send(500, {'error': f'{type(e).__name__}: {e}'})
            return
        ms = int((time.time() - t0) * 1000)
        log.info('scored %d passages in %dms', len(passages), ms)
        self._send(200, {'scores': scores, 'ms': ms})

    def log_message(self, fmt, *args):
        log.info(fmt, *args)


def main():
    load_model()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    log.info('listening on %s:%s', HOST, PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
