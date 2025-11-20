# Xentry File Sync

This project is a file synchronization system for "Xentry star machines". It consists of a central server and two types of clients.

## Components

### 1. Server
- Receives files from Star Machines.
- Stores files with a 30-day retention policy.
- Provides an API for clients and a future admin dashboard.

### 2. Star Machine Client (Sender)
- Monitors a local directory for new PDF files.
- Sends new files to the server.

### 3. PC Client (Receiver)
- Polls the server for new files.
- Downloads new files to a local backup folder.

## Project Structure
```
├── server/
│   ├── app.py
│   ├── uploads/
│   └── requirements.txt
├── star_client/
│   ├── client.py
│   └── requirements.txt
├── pc_client/
│   ├── client.py
│   └── requirements.txt
├── Jamie's Xentry Backup/
└── README.md
```
