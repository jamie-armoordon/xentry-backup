# Vercel Blob Storage Setup

## Quick Setup

1. **Create Blob Store in Vercel Dashboard**:
   - Go to your project → Storage → Create Database → Blob
   - Name it (e.g., "xentry-files")
   - Create the store

2. **Environment Variable**:
   - Vercel automatically creates `BLOB_READ_WRITE_TOKEN`
   - It's available in your project settings → Environment Variables
   - The server will automatically detect and use it

3. **That's it!** The server will automatically use blob storage when the token is available.

## How It Works

- **With Blob Token**: Files are stored in Vercel Blob Storage (persistent, global CDN)
- **Without Blob Token**: Falls back to local filesystem (ephemeral on Vercel)

## Testing

After deployment, check the logs to see if blob storage is being used:
- Look for "File uploaded to Vercel Blob successfully" messages
- If you see "Blob upload failed, falling back to local storage", check your token

## API Implementation Note

The current implementation uses a reverse-engineered REST API. If you encounter issues:

1. Check Vercel's official documentation for REST API endpoints
2. Consider using a Next.js proxy endpoint that uses the official `@vercel/blob` SDK
3. Wait for an official Python SDK from Vercel

## File Paths

Files are stored with paths like:
- `uploads/{client_id}/{relative_path}`

Example: `uploads/abc123/2025-01-15/file.pdf`

