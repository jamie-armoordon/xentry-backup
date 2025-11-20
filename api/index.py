import sys
import os
import traceback
from flask import Flask, jsonify

# 1. Setup Paths
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
server_dir = os.path.join(project_root, 'server')

# 2. Add server directory to sys.path
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

# 3. Change directory to server
os.chdir(server_dir)

# 4. Create a "Sandbox" Flask app (This ensures Vercel starts successfully)
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "Online",
        "message": "Vercel wrapper is running. Go to /debug to see why server/app.py is crashing.",
        "python_path": sys.path,
        "current_dir": os.getcwd()
    })

@app.route('/debug')
def debug_import():
    """
    This route attempts to import your real app.py and captures
    ANY error (syntax, missing env var, crash) into a string.
    """
    output = []
    output.append("--- ATTEMPTING IMPORT ---")
    
    try:
        # Try to import the app module
        import app as user_app
        return f"SUCCESS! App imported correctly.\n\nApp details: {user_app}"
        
    except Exception:
        # Catch runtime errors (KeyError, ImportError, etc)
        return f"CRITICAL ERROR DURING IMPORT:\n\n{traceback.format_exc()}", 500
        
    except SystemExit as e:
        # Catch app.run() or sys.exit() calls
        return f"SYSTEM EXIT CAUGHT (Likely app.run() running): {e}", 500

# 5. Export the SANDBOX app, not your real app
handler = app