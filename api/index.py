# DIAGNOSTIC SCRIPT - Temporary replacement to debug Vercel environment
from http.server import BaseHTTPRequestHandler
import sys
import os

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        
        output = []
        output.append("--- DIAGNOSTIC INFO ---")
        output.append(f"Python Version: {sys.version}")
        output.append(f"Current Working Dir: {os.getcwd()}")
        
        output.append("\n--- FILE SYSTEM ---")
        try:
            # List files in current directory (api/)
            output.append(f"Files in {os.getcwd()}: {os.listdir('.')}")
            # List files in project root (parent)
            parent = os.path.dirname(os.getcwd())
            output.append(f"Files in Root ({parent}): {os.listdir(parent)}")
            # Check if server dir exists
            server_path = os.path.join(parent, 'server')
            if os.path.exists(server_path):
                output.append(f"Files in Server ({server_path}): {os.listdir(server_path)}")
            else:
                output.append("ERROR: 'server' directory NOT FOUND")
        except Exception as e:
            output.append(f"FS Error: {e}")

        output.append("\n--- DEPENDENCIES ---")
        output.append("sys.path:")
        for p in sys.path:
            output.append(f"  - {p}")
            
        try:
            import flask
            output.append(f"\nSUCCESS: Flask found at {flask.__file__}")
        except ImportError as e:
            output.append(f"\nFAILURE: Flask Import Failed: {e}")
            
        self.wfile.write('\n'.join(output).encode())

