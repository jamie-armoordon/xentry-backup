# Xentry File Sync

This project is a file synchronization system for "Xentry star machines". It consists of a central server and two types of clients.

## Components

### 1. Server (Deployed on Vercel)
- Receives files from Star Machines.
- Stores files with a 30-day retention policy.
- Provides an API for clients and an admin dashboard.
- **Deployed at**: https://xentry.jamiearmoordon.co.uk/

### 2. Star Machine Client (Sender)
- Monitors a local directory for new PDF files.
- Sends new files to the server.
- **Note**: Client code is not in this repository (local only)

### 3. PC Client (Receiver)
- Polls the server for new files.
- Downloads new files to a local backup folder.
- **Note**: Client code is not in this repository (local only)

## Project Structure (Git Repository)
```
server/
├── api/
│   ├── index.py          # Vercel serverless function entry point
│   └── requirements.txt  # Python dependencies for Vercel
├── app.py                # Main Flask application
├── blob_storage.py       # Vercel Blob Storage integration
├── vercel.json           # Vercel configuration
├── requirements.txt      # Server dependencies
├── runtime.txt           # Python version
├── static/               # CSS, JS files
└── templates/            # HTML templates
```

**Note**: This repository contains only the server code. Client applications are maintained separately.
