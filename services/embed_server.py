"""The passage-index embedding model, as its own small service.

WHY THIS EXISTS

Theme Search takes a free-text description and has to turn it into a vector
before it can be compared against the index. That needs the embedding model.
Nothing else does: Similar Passages and the Reader gutter compare vectors that
were computed when the index was built, so they never load a model.

The obvious thing is to load the model inside the web application. On this
server that is a bad trade:

  - Apache runs THREE worker processes. Each one that served a Theme Search
    would hold its own copy of the model and the index, roughly 4-5 GB each.
  - Those workers recycle after 1000 requests, which is ordinary hygiene. Every
    recycle would throw the model away and reload it, about 22 seconds, so the
    feature would be fast and then randomly stall for 22 seconds forever.
  - It would put PyTorch permanently inside the web server, where a future
    upgrade of it could break the whole site rather than one feature.

So the model runs here instead, once, in one process, with a hard memory limit,
and the web application asks it for vectors over loopback. Same shape as the
assistant's model server, which already works this way.

If this service is down, Theme Search reports itself unavailable and every other
part of the site is unaffected. That is the point of the split.
"""
import json
import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# 8081 belongs to the assistant's llama-server. Anything here must pick a port
# that is actually free on this machine, and say which, because the two model
# services now sit side by side.
MODEL_NAME = os.environ.get('TESSERAE_EMBED_MODEL', 'intfloat/multilingual-e5-large')
HOST = os.environ.get('TESSERAE_EMBED_HOST', '127.0.0.1')
PORT = int(os.environ.get('TESSERAE_EMBED_PORT', '8090'))

# A single query is one short string. The cap stops a malformed or hostile
# request from turning into an unbounded encode job on a shared machine.
MAX_TEXTS = 32
MAX_CHARS = 2000

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - embed - %(levelname)s - %(message)s')
log = logging.getLogger('embed')

_model = None
_lock = threading.Lock()


def get_model():
    """Loaded once, on the first request rather than at import.

    Lazily, so the service answers /health immediately and systemd sees it as
    started rather than hanging for the twenty seconds the load takes.
    """
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer
            log.info('loading %s', MODEL_NAME)
            _model = SentenceTransformer(MODEL_NAME)
            log.info('model ready')
    return _model


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
            # Deliberately does NOT load the model: the caller wants to know the
            # service is reachable, and answering that should not cost 20s.
            self._send(200, {'ok': True, 'model': MODEL_NAME,
                             'loaded': _model is not None})
        else:
            self._send(404, {'error': 'not found'})

    def do_POST(self):
        if not self.path.startswith('/embed'):
            self._send(404, {'error': 'not found'})
            return
        try:
            n = int(self.headers.get('Content-Length') or 0)
            data = json.loads(self.rfile.read(n) or b'{}')
        except (ValueError, TypeError) as e:
            self._send(400, {'error': f'bad request: {e}'})
            return

        texts = data.get('texts')
        if isinstance(texts, str):
            texts = [texts]
        if not isinstance(texts, list) or not texts:
            self._send(400, {'error': 'texts must be a non-empty list'})
            return
        texts = [str(t)[:MAX_CHARS] for t in texts[:MAX_TEXTS]]

        try:
            vectors = get_model().encode(
                texts, normalize_embeddings=bool(data.get('normalize', True)),
                convert_to_numpy=True)
            self._send(200, {'vectors': [v.tolist() for v in vectors],
                             'dim': int(vectors.shape[1])})
        except Exception as e:                      # never take the service down
            log.exception('encode failed')
            self._send(500, {'error': f'{type(e).__name__}: {e}'})

    def log_message(self, fmt, *args):
        log.info(fmt, *args)


def main():
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
