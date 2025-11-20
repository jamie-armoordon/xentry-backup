# Vercel serverless function entry point
import sys
import os

# Get the directory containing this file
current_dir = os.path.dirname(os.path.abspath(__file__))
# Get the project root (parent of api/)
project_root = os.path.dirname(current_dir)
# Get the server directory
server_dir = os.path.join(project_root, 'server')

# Add both to path
for path in [server_dir, project_root]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Change to server directory for relative imports
os.chdir(server_dir)

# Now import the app
from app import app

# Export the Flask app for Vercel
# Vercel expects a 'handler' variable for Python functions
handler = app

