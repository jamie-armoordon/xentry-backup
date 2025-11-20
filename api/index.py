# Vercel serverless function entry point
import sys
import os
import traceback

# 1. Setup Paths
# current_dir = /var/task/api
current_dir = os.path.dirname(os.path.abspath(__file__))
# project_root = /var/task
project_root = os.path.dirname(current_dir)
# server_dir = /var/task/server
server_dir = os.path.join(project_root, 'server')

# 2. Add server directory to sys.path so we can import 'app'
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

# 3. Change directory to server so relative paths (templates/static) work
os.chdir(server_dir)

# 4. Safe Import
try:
    # Attempt to import the Flask app
    from app import app
    # If successful, expose it to Vercel
    handler = app
except Exception as e:
    # If IMPORT fails (e.g. syntax error, missing env var, db crash)
    # Capture the full traceback
    error_trace = traceback.format_exc()
    error_message = str(e)
    
    # Print to Vercel Logs (visible in dashboard)
    print(f"CRITICAL ERROR: {error_trace}")
    print(f"Error message: {error_message}")

    # Create a fallback handler to show the error in the browser
    from http.server import BaseHTTPRequestHandler
    
    # Store error in module-level variable so handler can access it
    _error_info = f"STARTUP FAILED:\n\nError: {error_message}\n\nTraceback:\n{error_trace}"
    
    class ErrorHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(_error_info.encode('utf-8'))
        
        def do_POST(self):
            self.do_GET()
    
    handler = ErrorHandler

