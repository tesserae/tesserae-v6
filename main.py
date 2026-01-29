"""
Tesserae V6 - Main entry point for Replit
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app import app, start_cache_init

if __name__ == '__main__':
    print("=" * 50)
    print("TESSERAE V6 STARTING")
    print("=" * 50)
    print("Backend API and Frontend on port 5000")
    print("=" * 50)
    
    import os
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    # Start cache initialization in background thread
    # This allows the server to start immediately and pass health checks
    start_cache_init()
    
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
