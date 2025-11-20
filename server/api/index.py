# Vercel serverless function entry point
import sys
import os

# api/index.py is at server/api/index.py
# server directory is the parent (server/)
current_dir = os.path.dirname(os.path.abspath(__file__))  # server/api/
server_dir = os.path.dirname(current_dir)  # server/

# Add server directory to sys.path so we can import app.py
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

# Change directory to server so relative paths (templates/static) work
os.chdir(server_dir)

# Import the Flask app
from app import app

# Export for Vercel
handler = app