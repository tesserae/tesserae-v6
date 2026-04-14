"""
Tesserae V6 - Main entry point for Replit
Production-ready startup with robust error handling
"""
import os
import sys
import socket
import ssl

print("=" * 50)
print("TESSERAE V6 STARTING")
print("=" * 50)
print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")
print("=" * 50)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Signal to app.py that we're running Flask directly (not behind Apache).
# This enables /api prefix on all routes since there's no Apache WSGIScriptAlias
# to strip it for us.
os.environ['TESSERAE_DIRECT_SERVER'] = '1'

try:
    print("Importing Flask application...")
    from backend.app import app, start_cache_init
    from werkzeug.serving import (
        WSGIRequestHandler,
        generate_adhoc_ssl_context,
        load_ssl_context,
        make_server,
    )
    print("Flask application imported successfully")
except Exception as e:
    print(f"ERROR importing Flask application: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


class HandshakeTimeoutWSGIRequestHandler(WSGIRequestHandler):
    """Perform TLS handshakes per connection with a finite timeout.

    Werkzeug's development server wraps the listening socket when SSL is
    enabled. That causes the accept loop to block inside the TLS handshake,
    so a single incomplete client connection can stall the whole server.
    Wrapping the accepted socket here keeps handshake work inside the worker
    thread and allows us to fail slow clients quickly.
    """

    def setup(self):
        conn = self.request
        ssl_context = getattr(self.server, "ssl_context", None)

        if ssl_context is not None and not isinstance(conn, ssl.SSLSocket):
            handshake_timeout = float(
                os.environ.get("TESSERAE_SSL_HANDSHAKE_TIMEOUT", "5")
            )
            conn.settimeout(handshake_timeout)
            conn = ssl_context.wrap_socket(
                conn,
                server_side=True,
                do_handshake_on_connect=False,
            )

            try:
                conn.do_handshake()
            except (socket.timeout, ssl.SSLError):
                try:
                    conn.close()
                finally:
                    raise
            finally:
                try:
                    conn.settimeout(None)
                except OSError:
                    pass

            self.request = conn

        super().setup()


def build_ssl_context(ssl_mode, ssl_cert, ssl_key):
    if ssl_mode == "adhoc":
        print("HTTPS enabled with an adhoc development certificate")
        return generate_adhoc_ssl_context()
    if ssl_cert and ssl_key:
        print(f"HTTPS enabled with certificate {ssl_cert}")
        return load_ssl_context(ssl_cert, ssl_key)
    return None


def run_server(host, port, debug, ssl_context):
    if ssl_context is None:
        app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True,
        )
        return

    server = make_server(
        host,
        port,
        app,
        threaded=True,
        request_handler=HandshakeTimeoutWSGIRequestHandler,
        ssl_context=None,
    )
    server.ssl_context = ssl_context
    server.log_startup()
    print("Press CTRL+C to quit")
    sys.stdout.flush()
    server.serve_forever()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"Backend API and Frontend on port {port}")
    print("=" * 50)

    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    ssl_mode = os.environ.get('TESSERAE_SSL', '').strip().lower()
    ssl_cert = os.environ.get('TESSERAE_SSL_CERT', '').strip()
    ssl_key = os.environ.get('TESSERAE_SSL_KEY', '').strip()
    ssl_context = build_ssl_context(ssl_mode, ssl_cert, ssl_key)

    try:
        start_cache_init()
        print("Cache initialization started in background")
    except Exception as e:
        print(f"Warning: Cache init failed (non-fatal): {e}")

    scheme = 'https' if ssl_context else 'http'
    print(f"Starting Flask server on {scheme}://0.0.0.0:{port}...")
    sys.stdout.flush()
    run_server(
        host='0.0.0.0',
        port=port,
        debug=debug_mode,
        ssl_context=ssl_context,
    )
