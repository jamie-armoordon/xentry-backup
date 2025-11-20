# Vercel Deployment Notes

## Important Considerations

### File Storage
Vercel has an **ephemeral filesystem** - files stored in `/tmp` will be lost on each deployment or after function execution. 

**✅ Vercel Blob Storage is now integrated!**

The server automatically uses Vercel Blob Storage when `BLOB_READ_WRITE_TOKEN` is set. To enable:

1. **Create a Blob Store**:
   - Go to your Vercel project dashboard
   - Navigate to Storage → Create Database → Blob
   - Name your blob store and create it

2. **Set Environment Variable**:
   - In Vercel project settings, add environment variable:
     - `BLOB_READ_WRITE_TOKEN` = (your blob store token)
   - This token is automatically provided when you create a blob store

3. **The server will automatically use blob storage** when the token is available, falling back to local storage otherwise.

### Background Tasks
The cleanup scheduler is disabled on Vercel. Use **Vercel Cron Jobs** instead:

1. Go to your Vercel project settings
2. Add a Cron Job that calls: `https://xentry.jamiearmoordon.co.uk/api/cleanup` (you'll need to add this endpoint)
3. Set it to run daily

### Environment Variables
Set these in Vercel dashboard:
- `DATA_DIR`: Storage location (defaults to `/tmp` for ephemeral storage)
- `VERCEL`: Automatically set to `1` by Vercel

### Deployment
1. Connect your GitHub repository to Vercel
2. Set root directory to project root
3. Vercel will automatically detect `vercel.json` and deploy

### Current Limitations
- File uploads are stored in `/tmp` (ephemeral)
- Cleanup scheduler needs to be replaced with Vercel Cron Jobs
- Consider migrating to external storage for production

