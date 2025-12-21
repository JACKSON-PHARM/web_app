# Data Refresh Flow - How It Works

## ✅ Current Flow (Correct Approach)

The web app does **NOT** save directly to Google Drive. Here's the actual flow:

### Step-by-Step Process:

```
1. User clicks "Refresh" button
   ↓
2. Data Fetchers Run
   ├─ Stock Fetcher → Fetches from APIs
   ├─ GRN Fetcher → Fetches from APIs  
   ├─ Orders Fetcher → Fetches from APIs
   └─ Supplier Invoices Fetcher → Fetches from APIs
   ↓
3. All Data Saved to LOCAL Database
   └─ Location: web_app/cache/pharma_stock.db
   └─ Fast SQLite writes (local disk)
   ↓
4. After Refresh Completes
   ↓
5. Upload LOCAL Database to Google Drive
   └─ Single upload operation
   └─ Replaces database in Drive
```

## Why This Approach?

### ✅ Advantages:

1. **Performance**: 
   - Local SQLite writes are **much faster** than network writes
   - Multiple fetchers can write simultaneously without network delays

2. **Reliability**:
   - If refresh fails, local database is still intact
   - Upload only happens if refresh succeeds
   - Can retry upload without re-running fetchers

3. **Efficiency**:
   - Single upload operation at the end
   - Not uploading after every single record
   - Reduces API calls to Google Drive

4. **Data Integrity**:
   - All data is committed locally first
   - Atomic operations (all or nothing)
   - Database is consistent before upload

### ❌ If We Saved Directly to Drive:

- **Very Slow**: Network latency for every write
- **Unreliable**: Network failures could lose data
- **Expensive**: Many API calls to Google Drive
- **Complex**: Harder to handle errors and retries

## Code Flow

### Refresh Endpoint (`/api/refresh/all`):

```python
# 1. User triggers refresh
@router.post("/all")
async def refresh_all_data(...):
    # Starts background task
    background_tasks.add_task(run_refresh_task)
    return {"status": "started", ...}

# 2. Background task runs
async def run_refresh_task():
    # Run fetchers → Save to LOCAL database
    result = refresh_service.refresh_all_data()
    
    if result.get('success'):
        # 3. Upload LOCAL database to Drive
        drive_manager.upload_database(local_db_path)
```

### Refresh Service:

```python
def refresh_all_data(self):
    # Fetchers save to LOCAL database via db_manager
    for fetcher_name in priority_fetchers:
        fetcher.run()  # Saves to local SQLite database
    
    return results  # Returns success/failure
```

## Database Locations

### Local Database:
- **Path**: `web_app/cache/pharma_stock.db`
- **Purpose**: Primary working database
- **Operations**: All reads and writes happen here
- **Speed**: Fast (local disk)

### Google Drive Database:
- **Path**: `PharmaStock_Database/pharma_stock.db` (in Drive)
- **Purpose**: Backup and sync
- **Operations**: Upload/download only
- **Speed**: Slower (network)

## Startup Flow

```
1. App Starts
   ↓
2. Check Google Drive Authentication
   ↓
3. Download Database from Drive (if exists)
   └─ Saves to: web_app/cache/pharma_stock.db
   ↓
4. Initialize Database Manager
   └─ Uses LOCAL database
   ↓
5. App Ready
   └─ All operations use LOCAL database
```

## Summary

**The web app:**
- ✅ Saves data **locally first** (fast, reliable)
- ✅ Uploads to Drive **after refresh completes** (efficient)
- ✅ Downloads from Drive **on startup** (sync)

**It does NOT:**
- ❌ Save directly to Google Drive during refresh
- ❌ Write to Drive for every record
- ❌ Use Drive as primary database

This is the **correct and optimal approach** for performance and reliability!

