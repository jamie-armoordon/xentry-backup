import sys
import time
import logging
import threading
import uuid
import os
import json
import tkinter as tk
from tkinter import filedialog
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import requests
from pystray import MenuItem as item
import pystray
from PIL import Image, ImageDraw

# --- Configuration and Setup ---

SERVER_URL = "https://xentry.jamiearmoordon.co.uk/"
CLIENT_ID_FILE = '.client_id'
CONFIG_FILE = '.star_config.json'
WATCHED_PATH = "" # Set at runtime
CLIENT_ID = "" # Set at runtime

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

def load_config():
    """Loads configuration from file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_config(config):
    """Saves configuration to file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except IOError as e:
        logging.error(f"Failed to save config: {e}")
        return False

def select_folder():
    """Opens a folder selection dialog in a separate thread."""
    result = [None]  # Use list to allow modification in nested function
    dialog_done = threading.Event()
    
    def run_dialog():
        root = None
        try:
            # Create a hidden root window
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            root.attributes('-topmost', True)  # Bring to front
            root.lift()  # Ensure it's on top
            root.focus_force()  # Force focus
            
            # Open folder selection dialog
            folder_path = filedialog.askdirectory(
                title="Select folder to watch for Xentry files",
                initialdir=os.path.expanduser("~"),
                parent=root
            )
            
            result[0] = folder_path if folder_path else None
            
        except Exception as e:
            logging.error(f"Error opening folder dialog: {e}")
            result[0] = None
        finally:
            # Always cleanup
            if root:
                try:
                    root.quit()
                    root.destroy()
                    root.update_idletasks()
                except:
                    pass
            dialog_done.set()
    
    # Run dialog in separate thread
    dialog_thread = threading.Thread(target=run_dialog, daemon=True)
    dialog_thread.start()
    
    # Wait for dialog to complete (with timeout)
    if dialog_done.wait(60):  # 60 second timeout
        return result[0]
    else:
        logging.error("Folder dialog timed out")
        return None

# --- Server Communication Functions ---

def ping_server():
    """Pings the server to register the client's presence."""
    try:
        payload = {'type': 'star_machine', 'client_id': CLIENT_ID}
        requests.post(f"{SERVER_URL}/ping", json=payload, timeout=10)
        logging.info("Server pinged successfully.")
        return True
    except requests.exceptions.RequestException as e:
        logging.warning(f"Could not ping server: {e}")
        return False

def create_remote_dir(relative_path):
    """Tells the server to create a directory."""
    logging.info(f"Ensuring remote directory exists: {relative_path}")
    try:
        payload = {
            'client_id': CLIENT_ID,
            'relative_path': relative_path.replace("\\", "/")
        }
        response = requests.post(f"{SERVER_URL}/create-dir", json=payload, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to create remote directory {relative_path}: {e}")

def upload_file(full_path, relative_path):
    """Uploads a file to the server with its relative path."""
    logging.info(f"Uploading file: {relative_path}")
    try:
        with open(full_path, 'rb') as f:
            data = {
                'client_id': CLIENT_ID,
                'relative_path': relative_path.replace("\\", "/")
            }
            files = {'file': (os.path.basename(full_path), f)}
            response = requests.post(f"{SERVER_URL}/upload", data=data, files=files)
            response.raise_for_status()
        logging.info(f"Successfully uploaded {relative_path}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to upload {relative_path}: {e}")
    except FileNotFoundError:
        logging.error(f"File not found during upload: {full_path}")

# --- File System Event Handler ---

class MirroringEventHandler(FileSystemEventHandler):
    """Handles new file system events to mirror them on the server."""
    def on_created(self, event):
        """Called when a file or directory is created."""
        relative_path = os.path.relpath(event.src_path, WATCHED_PATH)
        if event.is_directory:
            create_remote_dir(relative_path)
        else:
            time.sleep(1) # Wait for file to be fully written
            upload_file(event.src_path, relative_path)

# --- Main Execution ---

def sync_existing_on_startup():
    """Scans the watched directory and uploads any existing files and folders."""
    logging.info("Starting initial sync of existing files...")
    for root, dirs, files in os.walk(WATCHED_PATH):
        # Sync directories first
        for name in dirs:
            full_path = os.path.join(root, name)
            relative_path = os.path.relpath(full_path, WATCHED_PATH)
            create_remote_dir(relative_path)
        
        # Sync files
        for name in files:
            full_path = os.path.join(root, name)
            relative_path = os.path.relpath(full_path, WATCHED_PATH)
            upload_file(full_path, relative_path)
    logging.info("Initial sync complete.")

# --- NEW TRAY ICON AND WORKER THREAD LOGIC ---

def create_image(width, height, color1, color2):
    """Creates a simple icon image."""
    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle((width // 2, 0, width, height // 2), fill=color2)
    dc.rectangle((0, height // 2, width // 2, height), fill=color2)
    return image

def star_worker(icon, stop_event, folder_change_event):
    """This function will run in the background thread."""
    
    # Create the icons we will use
    icon_running = create_image(64, 64, 'green', 'white')
    icon_stopped = create_image(64, 64, 'red', 'white')
    icon_no_folder = create_image(64, 64, 'orange', 'white')
    
    observer = None
    event_handler = None
    current_watched_path = WATCHED_PATH
    
    def start_watching(path):
        """Start watching a new directory."""
        nonlocal observer, event_handler, current_watched_path
        
        # Stop existing observer if running
        if observer:
            observer.stop()
            observer.join()
        
        if not path or not os.path.isdir(path):
            return False
            
        try:
            # Perform the initial sync of all existing files and folders
            global WATCHED_PATH
            WATCHED_PATH = path
            current_watched_path = path
            sync_existing_on_startup()
            
            # Start the observer to watch for new changes
            event_handler = MirroringEventHandler()
            observer = Observer()
            observer.schedule(event_handler, path, recursive=True)
            observer.start()
            logging.info(f"Now watching for new changes in: {path}")
            return True
        except Exception as e:
            logging.error(f"Failed to start watching {path}: {e}")
            return False
    
    # Start watching the initial folder
    if current_watched_path:
        start_watching(current_watched_path)

    while not stop_event.is_set():
        # Check if folder needs to be changed
        if folder_change_event.is_set():
            folder_change_event.clear()
            # Reload config to get new folder
            config = load_config()
            new_folder = config.get('watched_folder', '')
            if new_folder != current_watched_path:
                logging.info(f"Changing watched folder from {current_watched_path} to {new_folder}")
                if start_watching(new_folder):
                    current_watched_path = new_folder
                else:
                    icon.icon = icon_no_folder
                    icon.title = f"Xentry Star Client (Invalid Folder) - {new_folder}"
                    continue
        
        # Only ping if we have a valid folder to watch
        if current_watched_path and os.path.isdir(current_watched_path):
            logging.info("Pinging server...")
            
            # Ping and update the icon based on success
            if ping_server():
                icon.icon = icon_running
                icon.title = f"Xentry Star Client (Running) - {current_watched_path}"
            else:
                icon.icon = icon_stopped
                icon.title = f"Xentry Star Client (Connection Failed) - {current_watched_path}"
        else:
            icon.icon = icon_no_folder
            icon.title = "Xentry Star Client (No Folder Selected)"
        
        # Wait for 60 seconds or until stop event or folder change
        stop_event.wait(60)
    
    # Cleanup when stopping
    if observer:
        observer.stop()
        observer.join()
    icon.icon = icon_stopped
    icon.title = f"Xentry Star Client (Stopped) - {current_watched_path}"
    logging.info("Star worker has stopped.")

def on_select_folder(icon, item):
    """This function is called when the user clicks 'Select Folder'."""
    logging.info("Select folder clicked.")
    folder_path = select_folder()
    if folder_path:
        # Save the new folder to config
        config = load_config()
        config['watched_folder'] = folder_path
        if save_config(config):
            logging.info(f"Selected folder: {folder_path}")
            # Signal the worker thread to change folder
            folder_change_event.set()
        else:
            logging.error("Failed to save folder selection")
    else:
        logging.info("No folder selected or dialog cancelled")


def on_show_current_folder(icon, item):
    """This function is called when the user clicks 'Show Current Folder'."""
    config = load_config()
    current_folder = config.get('watched_folder', 'No folder selected')
    logging.info(f"Current watched folder: {current_folder}")
    # You could show a message box here if needed

def on_quit(icon, item):
    """This function is called when the user clicks 'Exit'."""
    logging.info("Exit clicked. Shutting down.")
    stop_event.set() # Signal the worker thread to stop
    icon.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    CLIENT_ID = get_client_id()
    
    # Load config to get saved folder, or use command line argument
    config = load_config()
    if len(sys.argv) >= 2:
        # Command line argument takes precedence
        WATCHED_PATH = sys.argv[1]
        # Save it to config for future use
        config['watched_folder'] = WATCHED_PATH
        save_config(config)
    else:
        # Use saved folder from config
        WATCHED_PATH = config.get('watched_folder', '')
        if not WATCHED_PATH:
            print("No folder specified. Use command line argument or select folder from tray menu.")
            print("Usage: python client.py <directory_to_watch>")
            # Don't exit, let user select folder from tray menu
    
    logging.info("Starting Star client...")
    if WATCHED_PATH:
        logging.info(f"Watching directory: {WATCHED_PATH}")
    else:
        logging.info("No folder selected. Use tray menu to select folder.")

    # Setup for the tray icon
    stop_event = threading.Event()
    folder_change_event = threading.Event()
    
    # Create menu with folder options
    menu = (
        item('Select Folder', on_select_folder),
        item('Show Current Folder', on_show_current_folder),
        item('Exit', on_quit)
    )
    
    initial_title = f"Xentry Star Client (Starting) - {WATCHED_PATH}" if WATCHED_PATH else "Xentry Star Client (No Folder Selected)"
    icon = pystray.Icon("Xentry Star Client", create_image(64, 64, 'red', 'white'), initial_title, menu)
    
    # Create and start the background thread
    star_thread = threading.Thread(target=star_worker, args=(icon, stop_event, folder_change_event))
    star_thread.daemon = True # Allows main program to exit even if thread is running
    star_thread.start()

    # Run the tray icon (this is a blocking call)
    icon.run()
