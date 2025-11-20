import os
import json
import shutil
from flask import Flask, request, jsonify, send_from_directory, render_template, Response
from flask_cors import CORS
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import logging

# Try to import blob storage (optional)
try:
    # Try relative import first (when in server directory)
    try:
        from .blob_storage import put_blob, get_blob, delete_blob, list_blobs
    except (ImportError, ValueError):
        # Fallback to absolute import
        from blob_storage import put_blob, get_blob, delete_blob, list_blobs
    BLOB_STORAGE_AVAILABLE = True
except ImportError:
    BLOB_STORAGE_AVAILABLE = False
    logging.warning("Blob storage module not available, using local storage only")

app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# Configuration
# Use /tmp for Vercel (ephemeral) or /data for persistent storage
# Note: Vercel has ephemeral filesystem - use Vercel Blob Storage for production
USE_BLOB_STORAGE = os.environ.get('BLOB_READ_WRITE_TOKEN') is not None and BLOB_STORAGE_AVAILABLE
DATA_DIR = os.environ.get('DATA_DIR', '/tmp')
UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads')
CLIENT_DATA_FILE = os.path.join(DATA_DIR, 'clients.json')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')
MAX_STORAGE_BYTES = 5 * 1024 * 1024 * 1024  # 5GB total storage limit

# Set upload limit to 5GB
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024 * 1024  # 5GB max file size
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def load_json(filename, default_data):
    """Loads data from a JSON file."""
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return default_data

def save_json(filename, data):
    """Saves data to a JSON file."""
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def get_storage_usage():
    """Calculate total storage usage in bytes."""
    total_size = 0
    try:
        for root, dirs, files in os.walk(UPLOAD_FOLDER):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.exists(file_path):
                    total_size += os.path.getsize(file_path)
    except OSError as e:
        logging.error(f"Error calculating storage usage: {e}")
    return total_size

def format_bytes(bytes_value):
    """Convert bytes to human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} TB"

# Ensure the upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

logging.basicConfig(level=logging.INFO)

@app.route('/ping', methods=['POST'])
def ping():
    """Allows clients to register or update their status."""
    # Load fresh data from disk
    clients = load_json(CLIENT_DATA_FILE, {})
    settings = load_json(SETTINGS_FILE, {'default_retention_days': 30})
    
    data = request.json
    if not data or 'client_id' not in data:
        return jsonify({"error": "client_id is required"}), 400

    client_id = data['client_id']
    client_type = data.get('type', 'unknown')
    
    # If client is new, initialize with default settings
    if client_id not in clients:
        clients[client_id] = {
            'label': '',
            'retention_days': settings.get('default_retention_days', 30)
        }

    clients[client_id].update({
        'last_seen': datetime.now().isoformat(),
        'type': client_type,
        'ip_address': request.remote_addr
    })
    save_json(CLIENT_DATA_FILE, clients) # Persist client data
    return jsonify({"message": "Ping received successfully"}), 200

def cleanup_old_files():
    """Remove files older than each client's configured retention period."""
    logging.info(f"Running granular cleanup task...")
    now = datetime.now()
    upload_folder = app.config['UPLOAD_FOLDER']
    current_storage = get_storage_usage()
    storage_percent = (current_storage / MAX_STORAGE_BYTES) * 100
    
    logging.info(f"Current storage usage: {format_bytes(current_storage)} ({storage_percent:.1f}%)")

    # Load fresh data from disk
    clients = load_json(CLIENT_DATA_FILE, {})
    settings = load_json(SETTINGS_FILE, {'default_retention_days': 30})

    for client_id, client_data in clients.items():
        retention_days = client_data.get('retention_days', settings.get('default_retention_days', 30))
        
        # If storage is over 90%, be more aggressive with cleanup
        if storage_percent > 90:
            retention_days = min(retention_days, 7)  # Max 7 days when storage is critical
            logging.info(f"Storage critical ({storage_percent:.1f}%), reducing retention to {retention_days} days for client {client_id}")
        
        client_dir = os.path.join(upload_folder, client_id)
        
        if not os.path.isdir(client_dir):
            continue

        logging.info(f"Checking client '{client_id}' with retention of {retention_days} days.")
        
        for date_folder in os.listdir(client_dir):
            folder_path = os.path.join(client_dir, date_folder)
            if os.path.isdir(folder_path):
                try:
                    folder_date = datetime.strptime(date_folder, '%Y-%m-%d')
                    if now - folder_date > timedelta(days=retention_days):
                        logging.info(f"Deleting old folder: {folder_path}")
                        shutil.rmtree(folder_path)
                except ValueError:
                    # Not a date-formatted folder, ignore.
                    pass
    
    # Log final storage usage
    final_storage = get_storage_usage()
    final_percent = (final_storage / MAX_STORAGE_BYTES) * 100
    logging.info(f"Cleanup completed. Final storage usage: {format_bytes(final_storage)} ({final_percent:.1f}%)")


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    if 'client_id' not in request.form or 'relative_path' not in request.form:
        return jsonify({"error": "client_id and relative_path are required"}), 400

    file = request.files['file']
    client_id = request.form['client_id']
    relative_path = request.form['relative_path']

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        # Read file data
        file_data = file.read()
        file_size = len(file_data)
        
        # Check storage limit before upload (only for local storage)
        if not USE_BLOB_STORAGE:
            current_storage = get_storage_usage()
            if current_storage + file_size > MAX_STORAGE_BYTES:
                return jsonify({
                    "error": "Storage limit exceeded",
                    "message": f"Upload would exceed 5GB storage limit. Current usage: {format_bytes(current_storage)}"
                }), 507  # 507 Insufficient Storage
        
        # Construct blob path: uploads/client_id/relative_path
        blob_path = f"uploads/{client_id}/{relative_path}".replace("\\", "/")
        
        if USE_BLOB_STORAGE:
            # Upload to Vercel Blob Storage
            result = put_blob(blob_path, file_data, access='public')
            if result:
                logging.info(f"File {relative_path} uploaded to Vercel Blob successfully")
                return jsonify({
                    "message": f"File {relative_path} uploaded successfully",
                    "url": result.get('url')
                }), 201
            else:
                # Fallback to local storage if blob upload fails
                logging.warning("Blob upload failed, falling back to local storage")
        
        # Local storage fallback
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], client_id, relative_path)
        os.makedirs(os.path.dirname(upload_path), exist_ok=True)
        
        with open(upload_path, 'wb') as f:
            f.write(file_data)
        
        # Log storage usage after upload
        if not USE_BLOB_STORAGE:
            new_storage = get_storage_usage()
            logging.info(f"Storage usage: {format_bytes(new_storage)} / {format_bytes(MAX_STORAGE_BYTES)}")
        
        return jsonify({"message": f"File {relative_path} uploaded successfully"}), 201

@app.route('/create-dir', methods=['POST'])
def create_dir():
    """Creates a directory on the server to mirror client structure."""
    data = request.json
    if not data or 'client_id' not in data or 'relative_path' not in data:
        return jsonify({"error": "client_id and relative_path are required"}), 400
    
    client_id = data['client_id']
    relative_path = data['relative_path']
    
    try:
        dir_path = os.path.join(app.config['UPLOAD_FOLDER'], client_id, relative_path)
        os.makedirs(dir_path, exist_ok=True)
        return jsonify({"message": f"Directory {relative_path} created successfully"}), 201
    except Exception as e:
        logging.error(f"Error creating directory {relative_path}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/files', methods=['GET'])
def list_files():
    """Lists all files, grouped by client."""
    # Load fresh data from disk
    clients = load_json(CLIENT_DATA_FILE, {})
    
    client_files = {}
    
    # Pre-populate with all known star_machine clients, so they appear even with zero files.
    for client_id, client_data in clients.items():
        if client_data.get('type') == 'star_machine':
            client_files[client_id] = {
                "label": client_data.get('label', client_id),
                "files": []
            }

    if USE_BLOB_STORAGE:
        # List files from blob storage
        blobs = list_blobs('uploads/')
        if blobs:
            # Build tree from blob paths
            for blob in blobs:
                path = blob.get('pathname', '')
                # Path format: uploads/client_id/relative_path
                if path.startswith('uploads/'):
                    parts = path[len('uploads/'):].split('/')
                    if len(parts) >= 2:
                        client_id = parts[0]
                        relative_path = '/'.join(parts[1:])
                        
                        if client_id not in client_files:
                            client_files[client_id] = {
                                "label": clients.get(client_id, {}).get('label', client_id),
                                "files": []
                            }
                        
                        if 'tree' not in client_files[client_id]:
                            client_files[client_id]['tree'] = {}
                        
                        # Build tree structure
                        build_tree_from_path(client_files[client_id]['tree'], relative_path.split('/'), path)
    else:
        # Use local file system
        upload_folder = app.config['UPLOAD_FOLDER']
        if os.path.isdir(upload_folder):
            for client_id in os.listdir(upload_folder):
                client_dir = os.path.join(upload_folder, client_id)
                if os.path.isdir(client_dir):
                    if client_id not in client_files:
                         client_files[client_id] = {
                            "label": clients.get(client_id, {}).get('label', client_id),
                            "files": [] # Kept for backward compatibility if needed, but tree is primary
                        }
                    
                    client_files[client_id]['tree'] = build_file_tree(client_dir, upload_folder)

    return jsonify(client_files)

def build_tree_from_path(tree, path_parts, full_path):
    """Builds a tree structure from a path list."""
    if not path_parts:
        return
    
    part = path_parts[0]
    if len(path_parts) == 1:
        # This is a file
        tree[part] = {
            "type": "file",
            "path": full_path.replace("uploads/", "")
        }
    else:
        # This is a folder
        if part not in tree:
            tree[part] = {
                "type": "folder",
                "children": {}
            }
        build_tree_from_path(tree[part]["children"], path_parts[1:], full_path)

def build_file_tree(dir_path, base_path):
    """Recursively builds a file and folder tree."""
    tree = {}
    try:
        for entry in os.listdir(dir_path):
            full_path = os.path.join(dir_path, entry)
            if os.path.isdir(full_path):
                tree[entry] = {
                    "type": "folder",
                    "children": build_file_tree(full_path, base_path)
                }
            else:
                tree[entry] = {
                    "type": "file",
                    "path": os.path.relpath(full_path, base_path).replace("\\", "/")
                }
    except OSError as e:
        logging.error(f"Error building file tree for {dir_path}: {e}")
    return tree


@app.route('/files/<path:filepath>', methods=['GET', 'DELETE'])
def handle_file(filepath):
    """Downloads or deletes a file."""
    blob_path = f"uploads/{filepath}".replace("\\", "/")
    
    if request.method == 'GET':
        if USE_BLOB_STORAGE:
            # Try to get from blob storage first
            file_data = get_blob(blob_path)
            if file_data:
                # Check if it's a PDF and if the request is for viewing
                is_pdf = filepath.lower().endswith('.pdf')
                is_view_request = request.args.get('view') == 'true'
                content_disposition = 'inline' if (is_pdf and is_view_request) else 'attachment'
                
                response = Response(
                    file_data,
                    mimetype='application/octet-stream',
                    headers={
                        'Content-Disposition': f'{content_disposition}; filename={os.path.basename(filepath)}'
                    }
                )
                return response
        
        # Fallback to local storage
        is_pdf = filepath.lower().endswith('.pdf')
        is_view_request = request.args.get('view') == 'true'
        as_attachment = not (is_pdf and is_view_request)
        return send_from_directory(app.config['UPLOAD_FOLDER'], filepath, as_attachment=as_attachment)
    
    if request.method == 'DELETE':
        deleted = False
        if USE_BLOB_STORAGE:
            deleted = delete_blob(blob_path)
        
        # Also try local storage (for fallback or hybrid scenarios)
        try:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filepath.replace('/', os.path.sep))
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted = True
                # Check if the containing date directory is empty and remove it.
                dir_path = os.path.dirname(file_path)
                if os.path.exists(dir_path) and not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    # Also check the parent (client) directory
                    client_dir = os.path.dirname(dir_path)
                    if os.path.exists(client_dir) and not os.listdir(client_dir):
                        os.rmdir(client_dir)
        except Exception as e:
            logging.error(f"Error deleting local file {filepath}: {e}")
        
        if deleted:
            return jsonify({"message": f"File {filepath} deleted successfully"}), 200
        else:
            return jsonify({"error": "File not found"}), 404


# --- Admin Dashboard Endpoints ---

@app.route('/')
def admin_dashboard():
    """Serves the admin dashboard page."""
    return render_template('index.html')

@app.route('/admin/clients', methods=['GET'])
def get_clients():
    """Lists connected clients."""
    # Load fresh data from disk
    clients = load_json(CLIENT_DATA_FILE, {})
    return jsonify(clients)

@app.route('/admin/clients/<client_id>/label', methods=['POST'])
def set_client_label(client_id):
    """Sets a label for a client."""
    # Load fresh data from disk
    clients = load_json(CLIENT_DATA_FILE, {})
    
    data = request.json
    if not data or 'label' not in data:
        return jsonify({"error": "Label is required"}), 400

    if client_id in clients:
        clients[client_id]['label'] = data['label']
        save_json(CLIENT_DATA_FILE, clients) # Persist the new label
        return jsonify({"message": "Label updated successfully"}), 200
    else:
        return jsonify({"error": "Client not found"}), 404

@app.route('/admin/clients/<client_id>/settings', methods=['POST'])
def set_client_settings(client_id):
    """Sets settings (label, retention) for a client."""
    # Load fresh data from disk
    clients = load_json(CLIENT_DATA_FILE, {})
    
    data = request.json
    if not data:
        return jsonify({"error": "Data is required"}), 400

    if client_id in clients:
        if 'label' in data:
            clients[client_id]['label'] = data['label']
        if 'retention_days' in data:
            clients[client_id]['retention_days'] = int(data['retention_days'])
        
        save_json(CLIENT_DATA_FILE, clients)
        return jsonify({"message": "Client settings updated successfully"}), 200
    else:
        return jsonify({"error": "Client not found"}), 404


# --- New API Endpoints ---

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    """Calculates and returns system analytics."""
    total_size = 0
    total_files = 0
    uploads_by_day = {}
    uploads_by_client = {}
    
    upload_folder = app.config['UPLOAD_FOLDER']
    
    for client_id in os.listdir(upload_folder):
        client_dir = os.path.join(upload_folder, client_id)
        if os.path.isdir(client_dir):
            uploads_by_client[client_id] = 0
            for root, _, files in os.walk(client_dir):
                for name in files:
                    full_path = os.path.join(root, name)
                    try:
                        file_size = os.path.getsize(full_path)
                        total_size += file_size
                        total_files += 1
                        uploads_by_client[client_id] += 1
                        
                        # Get date from folder structure (e.g., .../client_id/YYYY-MM-DD/...)
                        # This is a bit fragile; assumes a specific structure.
                        path_parts = full_path.split(os.sep)
                        for part in path_parts:
                            try:
                                date_obj = datetime.strptime(part, '%Y-%m-%d')
                                day_str = date_obj.strftime('%Y-%m-%d')
                                uploads_by_day[day_str] = uploads_by_day.get(day_str, 0) + 1
                                break
                            except ValueError:
                                continue
                                
                    except OSError:
                        pass # File might have been deleted

    # Sort daily uploads for the chart
    sorted_uploads = sorted(uploads_by_day.items())

    return jsonify({
        'total_files': total_files,
        'total_size_bytes': total_size,
        'total_size_mb': total_size / (1024 * 1024),
        'storage_limit_bytes': MAX_STORAGE_BYTES,
        'storage_limit_mb': MAX_STORAGE_BYTES / (1024 * 1024),
        'storage_usage_percent': (total_size / MAX_STORAGE_BYTES) * 100,
        'uploads_by_day': dict(sorted_uploads),
        'uploads_by_client': uploads_by_client
    })

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_global_settings():
    """Gets or updates global default settings."""
    # Load fresh data from disk
    settings = load_json(SETTINGS_FILE, {'default_retention_days': 30})
    
    if request.method == 'POST':
        new_settings = request.json
        settings['default_retention_days'] = int(new_settings.get('default_retention_days', 30))
        save_json(SETTINGS_FILE, settings)
        return jsonify({"message": "Global settings updated successfully"}), 200
    else: # GET
        return jsonify(settings)

@app.errorhandler(413)
def too_large(e):
    """Handle file size too large error (413 Request Entity Too Large)."""
    return jsonify({
        "error": "File too large", 
        "message": "File size exceeds the 5GB limit. Please compress or split the file."
    }), 413

@app.route('/api/test-blob', methods=['GET'])
def test_blob():
    """Test endpoint to verify blob storage connection."""
    blob_status = {
        "blob_storage_available": BLOB_STORAGE_AVAILABLE,
        "blob_token_set": os.environ.get('BLOB_READ_WRITE_TOKEN') is not None,
        "use_blob_storage": USE_BLOB_STORAGE,
        "storage_type": "Vercel Blob Storage" if USE_BLOB_STORAGE else "Local filesystem (ephemeral)"
    }
    
    # Try a simple blob operation if available
    if USE_BLOB_STORAGE:
        try:
            test_result = list_blobs('test/')
            blob_status["test_list_success"] = True
            blob_status["test_blobs_found"] = len(test_result) if test_result else 0
        except Exception as e:
            blob_status["test_list_success"] = False
            blob_status["test_error"] = str(e)
    
    return jsonify(blob_status)

if __name__ == '__main__':
    # Scheduler for daily cleanup (only in non-serverless environments)
    # For Vercel, use Vercel Cron Jobs instead
    if not os.environ.get('VERCEL'):
        scheduler = BackgroundScheduler()
        scheduler.add_job(cleanup_old_files, 'interval', days=1)
        scheduler.start()

    app.run(host='0.0.0.0', port=5000, debug=True)
else:
    # When imported by Vercel (not run directly), don't start the scheduler
    # Vercel will handle the app through the handler in api/index.py
    pass
