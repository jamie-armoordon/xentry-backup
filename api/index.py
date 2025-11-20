import sys
import os
import traceback

# Global state to store the app or error
real_app = None
startup_error = None

def show_error(start_response, error_text):
    """WSGI function to display errors."""
    try:
        status = '500 Internal Server Error'
        headers = [('Content-type', 'text/plain; charset=utf-8')]
        start_response(status, headers)
        return [f"----------------------------------------\nAPP STARTUP FAILED\n----------------------------------------\n\n{error_text}".encode('utf-8')]
    except Exception as e:
        # If even error display fails, try minimal response
        try:
            start_response('500 Internal Server Error', [('Content-type', 'text/plain')])
            return [f"Fatal error: {str(e)}\n\nOriginal error: {error_text[:500]}".encode('utf-8')]
        except:
            # Last resort - return empty response
            return [b"Internal Server Error"]

def handler(environ, start_response):
    """
    Vercel Serverless Handler.
    Lazily imports the Flask app on the first request to catch startup errors.
    """
    global real_app, startup_error

    try:
        # Case 1: App is already loaded, pass the request to Flask
        if real_app:
            return real_app(environ, start_response)

        # Case 2: App previously failed to load, show the cached error
        if startup_error:
            return show_error(start_response, startup_error)

        # Case 3: First request - try to import the app
        try:
            # 1. Setup Paths
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            server_dir = os.path.join(project_root, 'server')

            # 2. Add server directory to sys.path
            if server_dir not in sys.path:
                sys.path.insert(0, server_dir)

            # 3. Change directory to server (critical for relative reads in Flask)
            os.chdir(server_dir)

            # 4. Import Flask here so we catch ImportError/SyntaxError/etc
            from app import app as flask_app
            real_app = flask_app
            return real_app(environ, start_response)
        except BaseException as e:
            # Catch EVERYTHING (including SystemExit)
            startup_error = traceback.format_exc()
            # Log to Vercel console
            print(f"CRITICAL FAILURE: {startup_error}", file=sys.stderr)
            print(f"Exception type: {type(e).__name__}", file=sys.stderr)
            print(f"Exception message: {str(e)}", file=sys.stderr)
            return show_error(start_response, startup_error)
    except Exception as e:
        # If handler itself fails, show error
        error_msg = f"Handler error: {str(e)}\n\n{traceback.format_exc()}"
        print(f"HANDLER FAILED: {error_msg}", file=sys.stderr)
        return show_error(start_response, error_msg)