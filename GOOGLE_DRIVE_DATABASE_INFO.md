# Google Drive Database - Read/Write Information

## ✅ **YES - The Database is FULLY MODIFIABLE!**

The database file stored in Google Drive is **NOT read-only**. Here's how it works:

## How It Works

1. **Upload**: Database is uploaded as a regular file to Google Drive
2. **Download**: You can download it anytime
3. **Modify**: You can modify the database locally (add/update/delete records)
4. **Re-upload**: Upload the modified database back to Google Drive
5. **Sync**: The app automatically syncs changes

## Database Operations

### ✅ What You CAN Do:

- **Create Tables**: Add new tables to the database
- **Modify Tables**: Alter table structure (add columns, change types, etc.)
- **Insert Data**: Add new records
- **Update Data**: Modify existing records
- **Delete Data**: Remove records
- **Refresh Data**: Run data fetchers to update from APIs
- **Upload Changes**: Upload modified database back to Drive

### 🔄 Automatic Sync Flow:

```
Local Database (web_app/cache/pharma_stock.db)
    ↓ (Modified by app operations)
    ↓ (After refresh/updates)
    ↓
Upload to Google Drive
    ↓
Google Drive (pharma_stock.db)
    ↓ (Download on startup)
    ↓
Local Database (web_app/cache/pharma_stock.db)
```

## File Storage Details

- **Location**: Google Drive folder `PharmaStock_Database`
- **File Name**: `pharma_stock.db`
- **Format**: SQLite database file
- **Access**: Full read/write access
- **Versioning**: Google Drive keeps version history

## Important Notes

1. **Large Files**: Files >100MB are uploaded in the background to prevent timeouts
2. **Progress Tracking**: Check server logs for upload progress
3. **Concurrent Access**: If multiple instances modify the database, the last upload wins
4. **Backup**: Google Drive automatically keeps version history

## Common Operations

### Upload Modified Database:
```bash
# Via Admin Panel
1. Go to http://localhost:8000/admin
2. Click "📤 Upload to Drive"
3. Wait for completion (check server logs for large files)
```

### Download Latest Database:
```bash
# Via Admin Panel
1. Go to http://localhost:8000/admin
2. Click "📥 Download from Drive"
3. Database will be downloaded and replace local copy
```

### Modify Database Programmatically:
```python
# The database is a regular SQLite file
import sqlite3

conn = sqlite3.connect('web_app/cache/pharma_stock.db')
cursor = conn.cursor()

# Create table
cursor.execute('CREATE TABLE IF NOT EXISTS my_table (...)')

# Insert data
cursor.execute('INSERT INTO my_table VALUES (...)')

# Update data
cursor.execute('UPDATE my_table SET column = value WHERE ...')

# Commit changes
conn.commit()
conn.close()

# Then upload to Drive via admin panel or API
```

## Troubleshooting

### Upload Timeout:
- **Cause**: Large file (>100MB) taking too long
- **Solution**: Upload now runs in background automatically
- **Check**: Server terminal logs for progress

### Database Locked:
- **Cause**: Another process is using the database
- **Solution**: Close other connections, wait a moment, try again

### Upload Failed:
- **Check**: Google Drive authentication status
- **Check**: Server logs for error details
- **Retry**: Upload operation (it's idempotent)

## Summary

**The database is fully modifiable!** It's stored as a regular file in Google Drive, not as a read-only document. You can:

- ✅ Modify tables and data
- ✅ Upload changes back to Drive
- ✅ Download latest version anytime
- ✅ Use it like any local SQLite database

The only difference is that it's synced to Google Drive for backup and multi-device access.

