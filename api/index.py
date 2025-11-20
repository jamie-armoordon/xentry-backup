import sys
import os
import traceback

# 1. Setup Paths
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
server_dir = os.path.join(project_root, 'server')

# 2. Add server directory to sys.path
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

# 3. Change directory to server (critical for relative reads in Flask)
os.chdir(server_dir)

# 4. Define a specific WSGI fallback for errors
def error_app(environ, start_response):
    """A simple WSGI app to display startup errors."""
    status = '500 Internal Server Error'
    response_headers = [('Content-type', 'text/plain; charset=utf-8')]
    start_response(status, response_headers)
    
    # Get the full traceback
    error_message = traceback.format_exc()
    
    # Print to Vercel runtime logs as well
    print("CRITICAL STARTUP ERROR:", file=sys.stderr)
    print(error_message, file=sys.stderr)
    
    return [f"STARTUP FAILED - SEE TRACEBACK:\n\n{error_message}".encode('utf-8')]

# 5. Attempt to import the real app
try:
    from app import app as flask_app
    handler = flask_app
except Exception:
    # If app fails to import (syntax error, missing dep, etc.), serve the error text
    handler = error_app

