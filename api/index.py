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

# Global state to store the app or error
real_app = None
startup_error = None

def handler(environ, start_response):
    """
    Vercel Serverless Handler.
    Lazily imports the Flask app on the first request to catch startup errors.
    """
    global real_app, startup_error

    # Case 1: App is already loaded, pass the request to Flask
    if real_app:
        return real_app(environ, start_response)

    # Case 2: App previously failed to load, show the cached error
    if startup_error:
        return show_error(start_response, startup_error)

    # Case 3: First request - try to import the app
    try:
        # Import Flask here so we catch ImportError/SyntaxError/etc
        from app import app as flask_app
        real_app = flask_app
        return real_app(environ, start_response)
    except BaseException:
        # Catch EVERYTHING (including SystemExit)
        startup_error = traceback.format_exc()
        # Log to Vercel console
        print(f"CRITICAL FAILURE: {startup_error}", file=sys.stderr)
        return show_error(start_response, startup_error)

def show_error(start_response, error_text):
    status = '500 Internal Server Error'
    headers = [('Content-type', 'text/plain; charset=utf-8')]
    start_response(status, headers)
    return [f"----------------------------------------\nAPP STARTUP FAILED\n----------------------------------------\n\n{error_text}".encode('utf-8')]

