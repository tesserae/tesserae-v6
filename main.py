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
    print("Backend API and Frontend on port 5000")
    print("=" * 50)
    
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    try:
        start_cache_init()
        print("Cache initialization started in background")
    except Exception as e:
        print(f"Warning: Cache init failed (non-fatal): {e}")
    
    print("Starting Flask server on 0.0.0.0:5000...")
    sys.stdout.flush()
    
    app.run(host='0.0.0.0', port=5000, debug=debug_mode, threaded=True)
