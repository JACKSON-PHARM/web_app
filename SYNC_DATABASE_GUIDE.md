# Complete Database Sync Guide

## ✅ Current Status

Your Google Drive is **✅ Connected**! The folder ID is: `1UAui6_vzdoDwSQVZ9nxuBxCdriKBBWqt`

However, the database doesn't exist in Google Drive yet. Here's how to get everything synced:

## Step 1: Copy Database from Desktop Version (If Available)

If you have the desktop version database, copy it to the web app:

### Option A: Copy from Distribution Folder

```bash
# Copy database from distribution folder
copy "distribution\PharmaStockApp_v2.0\database\pharma_stock.db" "web_app\cache\pharma_stock.db"
```

### Option B: Use Existing Database

If you already have a database file, place it at:
```
web_app/cache/pharma_stock.db
```

## Step 2: Upload Database to Google Drive

### Method 1: Via Admin Panel (Recommended)

1. Go to: `http://localhost:8000/admin`
2. Click **"Sync Database from Drive"** button
   - This will upload your local database to Google Drive
   - Wait for success message

### Method 2: Via API

```bash
# Using PowerShell
Invoke-WebRequest -Uri "http://localhost:8000/api/admin/drive/sync" -Method POST -Headers @{"Authorization"="Bearer YOUR_TOKEN"}
```

## Step 3: Refresh Data (Fetch Latest from APIs)

After the database is uploaded, refresh the data:

1. Go to: `http://localhost:8000/dashboard`
2. Click **"Refresh Data"** button (or go to Settings → Refresh)
3. Enter your credentials (NILA and/or DAIMA)
4. Wait for refresh to complete
5. The refreshed database will automatically upload to Google Drive

## Step 4: Verify Sync

1. Go to Admin panel: `http://localhost:8000/admin`
2. Check Google Drive Info section
3. You should see:
   - ✅ Status: Connected
   - ✅ Database Exists: Yes
   - Size: [your database size] MB
   - Last Modified: [timestamp]

## What Gets Synced

The web app syncs the same database as the desktop version:

- ✅ **Stock Data** - Current stock positions for all branches
- ✅ **GRN Data** - Goods Received Notes
- ✅ **Orders** - Purchase orders and branch orders
- ✅ **Supplier Invoices** - Supplier invoice data
- ✅ **Document Tracker** - Tracks processed documents (prevents duplicates)

## Automatic Sync

After initial setup, the web app will:

1. **On Startup**: Download database from Google Drive (if available)
2. **After Refresh**: Upload updated database to Google Drive
3. **On Manual Sync**: Download latest database from Google Drive

## Troubleshooting

### Database Not Found in Drive

If you see "Database not found in Google Drive folder":
1. Make sure you've uploaded it using "Sync Database from Drive" button
2. Or run a refresh which will create and upload the database

### Upload Fails

- Check that Google Drive is authenticated (Status: ✅ Connected)
- Check server logs for error messages
- Verify folder ID is correct

### Download Fails

- Check that database exists in Google Drive
- Verify folder ID matches
- Check server logs for authentication errors

## Next Steps

Once database is synced:

1. ✅ **Dashboard** - View new arrivals and priority items
2. ✅ **Stock View** - View detailed stock information
3. ✅ **Procurement Bot** - Generate procurement orders
4. ✅ **Auto Refresh** - Scheduled data refresh (every 60 minutes)
5. ✅ **Manual Refresh** - Trigger refresh anytime

All features from the desktop version are now available in the web app!

