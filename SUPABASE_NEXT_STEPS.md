# Next Steps - Supabase Migration

## ✅ You've Created Supabase Project!
Project URL: `https://oagcmmkmypmwmeuodkym.supabase.co`

## Step 1: Get Database Connection String (2 minutes)

1. In Supabase dashboard, click **"Settings"** (gear icon) in left sidebar
2. Click **"Database"** in settings menu
3. Scroll down to **"Connection string"** section
4. Find **"URI"** tab (not "JDBC" or "Golang")
5. Copy the connection string - it looks like:
   ```
   postgresql://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
   ```
   OR
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres
   ```

6. **Important**: Replace `[YOUR-PASSWORD]` with the password you set when creating the project
7. Save this connection string - you'll need it!

---

## Step 2: Clean Your Local Database (5 minutes)

Before migrating, we need to reduce the database size to fit Supabase free tier (500MB).

### Run cleanup script:
```bash
cd C:\PharmaStockApp\web_app
python scripts/cleanup_database.py cache/pharma_stock.db 3
```

**What this does:**
- ✅ Keeps only last 3 months of orders/invoices
- ✅ Removes sales data (not needed for procurement)
- ✅ Removes old stock snapshots
- ✅ Reduces database from 600MB → ~200-300MB

**Expected output:**
```
📊 Original database size: 600.00 MB
🧹 Cleaning old purchase orders...
   Deleted 50000 old purchase orders
🧹 Cleaning old branch orders...
   Deleted 30000 old branch orders
...
✅ Cleanup complete!
📊 New database size: 250.00 MB
✅ Database fits in Supabase free tier (500MB limit)
```

---

## Step 3: Install PostgreSQL Driver (1 minute)

```bash
pip install psycopg2-binary
```

---

## Step 4: Migrate to Supabase (10 minutes)

### Run migration script:
```bash
python scripts/migrate_to_supabase.py cache/pharma_stock.db "YOUR_CONNECTION_STRING_HERE"
```

**Replace `YOUR_CONNECTION_STRING_HERE` with the connection string from Step 1**

**Example:**
```bash
python scripts/migrate_to_supabase.py cache/pharma_stock.db "postgresql://postgres:yourpassword@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres"
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
...
✅ Migration complete!
🎉 Migration successful!
```

---

## Step 5: Verify Migration (2 minutes)

1. Go back to Supabase dashboard
2. Click **"Database"** in left sidebar
3. Click **"Tables"**
4. You should see your tables:
   - ✅ `items`
   - ✅ `current_stock`
   - ✅ `purchase_orders`
   - ✅ `branch_orders`
   - ✅ `supplier_invoices`
   - ✅ `stock_data`

5. Click on a table to see data
6. Check row counts match your cleaned database

---

## Step 6: Update App Configuration

### 6.1 Add connection string to config:

Create or update `web_app/.env` file:
```env
SUPABASE_DATABASE_URL=postgresql://postgres:yourpassword@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres
```

### 6.2 Update app/config.py:

Add to `Settings` class:
```python
SUPABASE_DATABASE_URL: str = Field(
    default="",
    env="SUPABASE_DATABASE_URL",
    description="Supabase PostgreSQL connection string"
)
```

---

## Troubleshooting

### "Database not found" error?
- Make sure you're in the `web_app` directory
- Check path: `cache/pharma_stock.db` exists

### "Connection refused" error?
- Check connection string format
- Make sure password is correct
- Try using the "Session" connection string instead of "Transaction"

### "Table already exists" error?
- Tables already exist in Supabase
- Either drop them first, or modify migration script to skip existing tables

### Database still too large?
- Run cleanup with fewer months:
  ```bash
  python scripts/cleanup_database.py cache/pharma_stock.db 2  # Keep only 2 months
  ```

---

## Quick Checklist

- [ ] Got database connection string from Supabase Settings → Database
- [ ] Cleaned local database (reduced to <500MB)
- [ ] Installed psycopg2-binary
- [ ] Ran migration script
- [ ] Verified tables in Supabase dashboard
- [ ] Updated app config with connection string

---

## After Migration

Once migration is complete, we'll update the app code to:
1. Use PostgreSQL instead of SQLite
2. Connect directly to Supabase
3. Remove Google Drive dependency
4. Enable instant access for all users

**Ready to start? Begin with Step 1 - get your connection string!**

