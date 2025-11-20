import sys
import os
import traceback

# Try to import Flask - if this fails, we'll show an error
try:
    from flask import Flask, jsonify
    FLASK_AVAILABLE = True
except ImportError as e:
    FLASK_AVAILABLE = False
    FLASK_ERROR = str(e)

# 1. Setup Paths
# api/index.py is now at server/api/index.py
# So server directory is the parent of api/
current_dir = os.path.dirname(os.path.abspath(__file__))  # server/api/
server_dir = os.path.dirname(current_dir)  # server/ (parent of api/)

# 2. Add server directory to sys.path so we can import app.py
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

# 3. Change directory to server so relative paths (templates/static) work
os.chdir(server_dir)

if FLASK_AVAILABLE:
    # 4. Create a "Sandbox" Flask app (This ensures Vercel starts successfully)
    app = Flask(__name__)

    @app.route('/')
    def home():
        return jsonify({
            "status": "Online",
            "message": "Vercel wrapper is running. Go to /debug to see why server/app.py is crashing.",
            "python_path": sys.path[:5],  # First 5 entries only
            "current_dir": os.getcwd(),
            "flask_location": Flask.__file__ if hasattr(Flask, '__file__') else "unknown"
        })

    @app.route('/debug')
    def debug_import():
        """
        This route attempts to import your real app.py and captures
        ANY error (syntax, missing env var, crash) into a string.
        """
        try:
            # Try to import the app module (app.py is in server/ directory)
            from app import app as user_app
            return f"SUCCESS! App imported correctly.\n\nApp type: {type(user_app)}\nApp: {user_app}"
        except SystemExit as e:
            # Catch app.run() or sys.exit() calls
            return f"SYSTEM EXIT CAUGHT (Likely app.run() running): {e}\n\n{traceback.format_exc()}", 500
        except Exception:
            # Catch runtime errors (KeyError, ImportError, etc)
            return f"CRITICAL ERROR DURING IMPORT:\n\n{traceback.format_exc()}", 500

    # 5. Export the SANDBOX app, not your real app
    handler = app
else:
    # Flask not available - create a minimal WSGI handler to show the error
    def handler(environ, start_response):
        status = '500 Internal Server Error'
        headers = [('Content-type', 'text/plain; charset=utf-8')]
        start_response(status, headers)
        error_msg = f"Flask is not installed!\n\nImportError: {FLASK_ERROR}\n\nsys.path:\n" + "\n".join(sys.path[:10])
        return [error_msg.encode('utf-8')]