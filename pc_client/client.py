import requests
import os
import time
import logging
import uuid
import threading
from pystray import MenuItem as item
import pystray
from PIL import Image, ImageDraw

# Configuration
SERVER_URL = "https://xentry.jamiearmoordon.co.uk/"
DOWNLOAD_FOLDER = os.path.expanduser("~/Desktop/Jamie's Xentry Backup")
POLL_INTERVAL = 60  # seconds
CLIENT_ID_FILE = '.client_id'

def get_client_id():
    """Gets or creates a unique client ID."""
    if os.path.exists(CLIENT_ID_FILE):
        with open(CLIENT_ID_FILE, 'r') as f:
            return f.read().strip()
    else:
        client_id = str(uuid.uuid4())
        with open(CLIENT_ID_FILE, 'w') as f:
            f.write(client_id)
        return client_id

CLIENT_ID = get_client_id()

# Ensure the download folder exists
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

def ping_server():
    """Pings the server to register the client's presence."""
    try:
        payload = {'type': 'pc_client', 'client_id': CLIENT_ID}
        requests.post(f"{SERVER_URL}/ping", json=payload, timeout=10)
        return True
    except requests.exceptions.RequestException as e:
        logging.warning(f"Could not ping server: {e}")
        return False

def get_remote_files():
    """Gets the list of files from the server."""
    try:
        response = requests.get(f"{SERVER_URL}/files")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Could not connect to the server: {e}")
        return {}

def get_local_files():
    """Gets a set of file paths that exist locally."""
    local_files = set()
    for root, _, files in os.walk(DOWNLOAD_FOLDER):
        for name in files:
            # We need to construct the same relative path format as the server
            # Assumes the server paths are like 'YYYY-MM-DD/filename.pdf'
            # and we are storing them in the same way.
            rel_dir = os.path.relpath(root, DOWNLOAD_FOLDER)
            if rel_dir == '.':
                rel_path = name
            else:
                rel_path = os.path.join(rel_dir, name)

            local_files.add(rel_path.replace("\\", "/"))
    return local_files

def flatten_file_tree(tree):
    """Recursively traverses the file tree and yields file paths."""
    for name, node in tree.items():
        if node['type'] == 'file':
            yield node['path']
        elif node['type'] == 'folder' and 'children' in node:
            yield from flatten_file_tree(node['children'])

def download_file(remote_path_with_id):
    """Downloads a single file to the correct merged location."""
    
    # Strip client ID to determine local path
    path_parts = remote_path_with_id.replace("\\", "/").split('/')
    local_relative_path = os.path.join(*path_parts[1:]) if len(path_parts) > 1 else path_parts[0]
    local_path = os.path.join(DOWNLOAD_FOLDER, local_relative_path)
    
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    try:
        logging.info(f"Downloading '{remote_path_with_id}' to '{local_relative_path}'...")
        response = requests.get(f"{SERVER_URL}/files/{remote_path_with_id}", stream=True)
        response.raise_for_status()
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logging.info(f"Successfully downloaded to '{local_path}'")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to download {remote_path_with_id}: {e}")


def sync_files():
    """Syncs files from the server."""
    logging.info("Checking for new files...")
    remote_data = get_remote_files()
    if not remote_data:
        return

    # Get the set of local files for quick lookups
    local_files = get_local_files()

    # Use a set to store the full paths of new files to download
    new_files_to_download = set()

    # Iterate through all remote files from all clients
    for client_id, client_info in remote_data.items():
        if 'tree' in client_info:
            for path_with_id in flatten_file_tree(client_info['tree']):
                # Create the stripped path for comparison
                path_parts = path_with_id.replace("\\", "/").split('/')
                if len(path_parts) > 1:
                    path_without_id = "/".join(path_parts[1:])
                    
                    # If this version of the file isn't in our local backup, schedule it for download
                    if path_without_id not in local_files:
                        new_files_to_download.add(path_with_id)

    if new_files_to_download:
        logging.info(f"Found {len(new_files_to_download)} new files.")
        # Sort for a predictable download order
        for full_remote_path in sorted(list(new_files_to_download)):
            download_file(full_remote_path)
    else:
        logging.info("No new files found.")

# --- NEW TRAY ICON AND WORKER THREAD LOGIC ---

def create_image(width, height, color1, color2):
    """Creates a simple icon image."""
    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle((width // 2, 0, width, height // 2), fill=color2)
    dc.rectangle((0, height // 2, width // 2, height), fill=color2)
    return image

def sync_worker(icon, stop_event):
    """This function will run in the background thread."""
    
    # Create the icons we will use
    icon_running = create_image(64, 64, 'green', 'white')
    icon_stopped = create_image(64, 64, 'red', 'white')

    while not stop_event.is_set():
        logging.info("Pinging server...")
        
        # Ping and update the icon based on success
        if ping_server():
            icon.icon = icon_running
            icon.title = "Xentry PC Client (Running)"
            sync_files()
        else:
            icon.icon = icon_stopped
            icon.title = "Xentry PC Client (Connection Failed)"
        
        logging.info(f"Waiting for {POLL_INTERVAL} seconds...")
        # Use an event-based wait instead of time.sleep for faster shutdown
        stop_event.wait(POLL_INTERVAL)
    
    # When the loop exits, set the icon to red and update title
    icon.icon = icon_stopped
    icon.title = "Xentry PC Client (Stopped)"
    logging.info("Sync worker has stopped.")

def on_quit(icon, item):
    """This function is called when the user clicks 'Exit'."""
    logging.info("Exit clicked. Shutting down.")
    stop_event.set() # Signal the worker thread to stop
    icon.stop()

if __name__ == "__main__":
    logging.info("Starting PC client...")
    logging.info(f"Backup folder is: {DOWNLOAD_FOLDER}")

    # Setup for the tray icon
    stop_event = threading.Event()
    menu = (item('Exit', on_quit),)
    icon = pystray.Icon("Xentry PC Client", create_image(64, 64, 'red', 'white'), "Xentry PC Client (Starting)", menu)
    
    # Create and start the background thread
    sync_thread = threading.Thread(target=sync_worker, args=(icon, stop_event))
    sync_thread.daemon = True # Allows main program to exit even if thread is running
    sync_thread.start()

    # Run the tray icon (this is a blocking call)
    icon.run()
