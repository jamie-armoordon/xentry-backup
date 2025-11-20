# Vercel serverless function entry point
import sys
import os

# In Vercel, the working directory is /var/task (project root)
# The api/ directory is at /var/task/api
# The server/ directory is at /var/task/server

# Get the project root (/var/task)
project_root = os.getcwd()  # Vercel sets CWD to /var/task

# Get the server directory
server_dir = os.path.join(project_root, 'server')

# Add server_dir to sys.path explicitly so we can import 'app'
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

# Change working directory to server/ so relative paths inside app.py (like templates/) work
os.chdir(server_dir)

from app import app

# Vercel expects a variable named 'app', 'handler', or 'application'
handler = app

