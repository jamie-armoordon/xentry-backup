"""
Vercel Blob Storage integration using REST API.
Requires BLOB_READ_WRITE_TOKEN environment variable from Vercel.

Note: This is a reverse-engineered implementation based on the JavaScript SDK.
The actual REST API endpoints may differ. If you encounter issues, check Vercel's
official documentation or use the JavaScript SDK via a proxy endpoint.

Alternative: You can create a Next.js API route that uses @vercel/blob SDK
and call it from Python, or wait for an official Python SDK.
"""
import os
import requests
import logging
from typing import Optional, BinaryIO

BLOB_API_BASE = "https://blob.vercel-storage.com"
BLOB_READ_WRITE_TOKEN = os.environ.get('BLOB_READ_WRITE_TOKEN')

def put_blob(path: str, data: bytes, access: str = 'public') -> Optional[dict]:
    """
    Upload a file to Vercel Blob Storage.
    
    Args:
        path: The path/key for the blob (e.g., 'uploads/client_id/file.pdf')
        data: File data as bytes
        access: 'public' or 'private'
    
    Returns:
        Dict with blob info including 'url', or None on error
    """
    if not BLOB_READ_WRITE_TOKEN:
        logging.warning("BLOB_READ_WRITE_TOKEN not set, falling back to local storage")
        return None
    
    try:
        url = f"{BLOB_API_BASE}/put"
        headers = {
            'Authorization': f'Bearer {BLOB_READ_WRITE_TOKEN}',
        }
        files = {
            'file': (os.path.basename(path), data)
        }
        data_payload = {
            'pathname': path,
            'access': access
        }
        
        response = requests.post(url, headers=headers, files=files, data=data_payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Failed to upload to Vercel Blob: {e}")
        return None

def get_blob(path: str) -> Optional[bytes]:
    """
    Download a file from Vercel Blob Storage.
    
    Args:
        path: The path/key of the blob
    
    Returns:
        File data as bytes, or None on error
    """
    if not BLOB_READ_WRITE_TOKEN:
        return None
    
    try:
        url = f"{BLOB_API_BASE}/get"
        headers = {
            'Authorization': f'Bearer {BLOB_READ_WRITE_TOKEN}',
        }
        params = {
            'pathname': path
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        logging.error(f"Failed to download from Vercel Blob: {e}")
        return None

def delete_blob(path: str) -> bool:
    """
    Delete a file from Vercel Blob Storage.
    
    Args:
        path: The path/key of the blob
    
    Returns:
        True if successful, False otherwise
    """
    if not BLOB_READ_WRITE_TOKEN:
        return False
    
    try:
        url = f"{BLOB_API_BASE}/delete"
        headers = {
            'Authorization': f'Bearer {BLOB_READ_WRITE_TOKEN}',
        }
        data = {
            'pathname': path
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return True
    except Exception as e:
        logging.error(f"Failed to delete from Vercel Blob: {e}")
        return False

def list_blobs(prefix: str = '') -> Optional[list]:
    """
    List blobs with a given prefix.
    
    Args:
        prefix: Path prefix to filter blobs (e.g., 'uploads/client_id/')
    
    Returns:
        List of blob info dicts, or None on error
    """
    if not BLOB_READ_WRITE_TOKEN:
        return None
    
    try:
        url = f"{BLOB_API_BASE}/list"
        headers = {
            'Authorization': f'Bearer {BLOB_READ_WRITE_TOKEN}',
        }
        params = {
            'prefix': prefix
        } if prefix else {}
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json().get('blobs', [])
    except Exception as e:
        logging.error(f"Failed to list Vercel Blobs: {e}")
        return None

