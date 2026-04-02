"""
Tesserae V6 - Main entry point for Replit
Production-ready startup with robust error handling
"""
import os
import sys

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
    print("Flask application imported successfully")
except Exception as e:
    print(f"ERROR importing Flask application: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"Backend API and Frontend on port {port}")
    print("=" * 50)

    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    ssl_mode = os.environ.get('TESSERAE_SSL', '').strip().lower()
    ssl_cert = os.environ.get('TESSERAE_SSL_CERT', '').strip()
    ssl_key = os.environ.get('TESSERAE_SSL_KEY', '').strip()
    ssl_context = None

    if ssl_mode == 'adhoc':
        ssl_context = 'adhoc'
        print("HTTPS enabled with an adhoc development certificate")
    elif ssl_cert and ssl_key:
        ssl_context = (ssl_cert, ssl_key)
        print(f"HTTPS enabled with certificate {ssl_cert}")

    try:
        start_cache_init()
        print("Cache initialization started in background")
    except Exception as e:
        print(f"Warning: Cache init failed (non-fatal): {e}")

    scheme = 'https' if ssl_context else 'http'
    print(f"Starting Flask server on {scheme}://0.0.0.0:{port}...")
    sys.stdout.flush()

    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug_mode,
        threaded=True,
        ssl_context=ssl_context,
    )
