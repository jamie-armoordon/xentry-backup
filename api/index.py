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
            # Current directory is /var/task (not api/)
            current = os.getcwd()
            output.append(f"Files in Current Dir ({current}): {os.listdir(current)}")
            
            # Check api directory
            api_path = os.path.join(current, 'api')
            if os.path.exists(api_path):
                output.append(f"Files in API ({api_path}): {os.listdir(api_path)}")
            
            # Check server directory (should be at /var/task/server)
            server_path = os.path.join(current, 'server')
            if os.path.exists(server_path):
                output.append(f"Files in Server ({server_path}): {os.listdir(server_path)}")
            else:
                output.append(f"ERROR: 'server' directory NOT FOUND at {server_path}")
                
            # Check _vendor for dependencies
            vendor_path = os.path.join(current, '_vendor')
            if os.path.exists(vendor_path):
                output.append(f"Files in _vendor ({vendor_path}): {os.listdir(vendor_path)[:10]}")  # First 10
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

