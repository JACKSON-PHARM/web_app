# Get Started with Supabase Migration - Step by Step

## ✅ Step 1: Get Database Connection String (2 minutes)

1. In your Supabase dashboard, click **"Settings"** (⚙️ gear icon) in the left sidebar
2. Click **"Database"** in the settings menu
3. Scroll down to find **"Connection string"** section
4. You'll see tabs: **"URI"**, **"JDBC"**, **"Golang"**, etc.
5. Click the **"URI"** tab
6. You'll see a connection string like:
   ```
   postgresql://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
   ```
   
   **OR** (direct connection):
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres
   ```

7. **Important**: Replace `[YOUR-PASSWORD]` with the password you set when creating the Supabase project
8. Copy the full connection string and save it somewhere safe

**Example of what it should look like:**
```
postgresql://postgres:MySecurePassword123@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres
```

---

## ✅ Step 2: Clean Your Local Database (5 minutes)

**This reduces your database from 600MB to ~200-300MB**

### Open PowerShell/Terminal and run:

```powershell
cd C:\PharmaStockApp\web_app
python scripts/cleanup_database.py cache/pharma_stock.db 3
```

**What happens:**
- ✅ Removes orders older than 3 months
- ✅ Removes invoices older than 3 months  
- ✅ Removes sales data (not needed for procurement)
- ✅ Removes old stock snapshots
- ✅ Adds indexes for faster queries
- ✅ Compresses database

**Expected output:**
```
📊 Original database size: 600.00 MB
🧹 Cleaning old purchase orders...
   Deleted 50000 old purchase orders
🧹 Cleaning old branch orders...
   Deleted 30000 old branch orders
🧹 Cleaning old supplier invoices...
   Deleted 20000 old supplier invoices
🧹 Cleaning old stock snapshots...
   Deleted 100000 old stock snapshots
🧹 Removing sales data...
   Removed sales tables
📊 Creating indexes...
🧹 Vacuuming database...
✅ Cleanup complete!
📊 New database size: 250.00 MB
✅ Database fits in Supabase free tier (500MB limit)
```

---

## ✅ Step 3: Install PostgreSQL Driver (1 minute)

```powershell
pip install psycopg2-binary
```

---

## ✅ Step 4: Migrate to Supabase (10 minutes)

### Run migration script with your connection string:

```powershell
python scripts/migrate_to_supabase.py cache/pharma_stock.db "YOUR_CONNECTION_STRING_HERE"
```

**Replace `YOUR_CONNECTION_STRING_HERE` with the connection string from Step 1**

**Example:**
```powershell
python scripts/migrate_to_supabase.py cache/pharma_stock.db "postgresql://postgres:MyPassword123@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres"
```

**Expected output:**
```
📂 Connecting to SQLite: cache/pharma_stock.db
🔌 Connecting to Supabase PostgreSQL...
📊 Found 6 tables to migrate
Creating table items...
Migrating items...
  Migrating 10,000 rows...
✅ Migrated 10,000 rows from items
Creating table current_stock...
Migrating current_stock...
  Migrating 50,000 rows...
✅ Migrated 50,000 rows from current_stock
...
✅ Migration complete!
🎉 Migration successful! Update your app config to use Supabase.
```

---

## ✅ Step 5: Verify in Supabase Dashboard (2 minutes)

1. Go back to Supabase dashboard
2. Click **"Database"** in left sidebar
3. Click **"Tables"** tab
4. You should see your tables:
   - `items`
   - `current_stock`
   - `purchase_orders`
   - `branch_orders`
   - `supplier_invoices`
   - `stock_data`

5. Click on any table to see the data
6. Check that row counts match your cleaned database

---

## 🎯 Quick Reference

**Your Supabase Project:**
- Project URL: `https://oagcmmkmypmwmeuodkym.supabase.co`
- Connection string location: Settings → Database → Connection string → URI tab

**Commands to run:**
```powershell
# 1. Clean database
cd C:\PharmaStockApp\web_app
python scripts/cleanup_database.py cache/pharma_stock.db 3

# 2. Install driver
pip install psycopg2-binary

# 3. Migrate (replace with your connection string)
python scripts/migrate_to_supabase.py cache/pharma_stock.db "postgresql://postgres:YOUR_PASSWORD@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres"
```

---

## ⚠️ Troubleshooting

### "Database not found" error?
- Make sure you're in `C:\PharmaStockApp\web_app` directory
- Check that `cache/pharma_stock.db` exists

### "Connection refused" or "Authentication failed"?
- Double-check your connection string
- Make sure password is correct (no spaces, special characters properly encoded)
- Try using the "Session" connection string instead of "Transaction"

### "Table already exists"?
- Tables might already exist in Supabase
- Go to Supabase → Database → Tables
- Drop existing tables if needed, then re-run migration

### Database still too large after cleanup?
- Try keeping only 2 months instead of 3:
  ```powershell
  python scripts/cleanup_database.py cache/pharma_stock.db 2
  ```

---

## 📋 Checklist

- [ ] Got connection string from Supabase (Settings → Database → URI)
- [ ] Cleaned local database (reduced to <500MB)
- [ ] Installed psycopg2-binary
- [ ] Ran migration script successfully
- [ ] Verified tables appear in Supabase dashboard
- [ ] Verified data looks correct

**Ready? Start with Step 1 - get your connection string!**

