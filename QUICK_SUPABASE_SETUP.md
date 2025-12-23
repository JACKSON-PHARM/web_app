# Quick Supabase Setup Guide - Procurement Database

## Goal
Reduce database from 600MB to <500MB and migrate to Supabase for instant access.

## Step 1: Clean Your Database (5 minutes)

### Run cleanup script:
```bash
cd web_app
python scripts/cleanup_database.py cache/pharma_stock.db 3
```

This will:
- ✅ Keep only last 3 months of orders/invoices
- ✅ Remove sales data (not needed for procurement)
- ✅ Remove old stock snapshots
- ✅ Reduce database size to ~200-300MB

**Expected result**: Database size reduced from 600MB to ~200-300MB ✅

---

## Step 2: Create Supabase Project (2 minutes)

1. Go to https://supabase.com
2. Sign up (free account)
3. Click "New Project"
4. Fill in:
   - **Name**: `pharmastock-procurement`
   - **Database Password**: (save this!)
   - **Region**: Choose closest to you
5. Click "Create new project"
6. Wait ~2 minutes for setup

---

## Step 3: Get Connection String (1 minute)

1. In Supabase dashboard, go to **Settings** → **Database**
2. Find **Connection string** section
3. Copy the **URI** connection string:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres
   ```
4. Save this - you'll need it!

---

## Step 4: Migrate Database (10 minutes)

### Install PostgreSQL driver:
```bash
pip install psycopg2-binary
```

### Run migration:
```bash
python scripts/migrate_to_supabase.py cache/pharma_stock.db "postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres"
```

**Expected result**: All data migrated to Supabase ✅

---

## Step 5: Update App to Use Supabase (15 minutes)

### 5.1 Update requirements.txt:
```bash
echo "psycopg2-binary>=2.9.0" >> requirements.txt
```

### 5.2 Create new database manager for PostgreSQL:

Create `web_app/app/services/postgres_manager.py`:
```python
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from app.config import settings

class PostgresManager:
    def __init__(self):
        self.conn = None
        self.connection_string = os.getenv(
            'SUPABASE_DATABASE_URL',
            settings.SUPABASE_DATABASE_URL
        )
    
    def get_connection(self):
        if not self.conn or self.conn.closed:
            self.conn = psycopg2.connect(self.connection_string)
        return self.conn
    
    def get_cursor(self):
        return self.get_connection().cursor(cursor_factory=RealDictCursor)
    
    def execute_query(self, query, params=None):
        cursor = self.get_cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
    
    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()
```

### 5.3 Update config.py:
```python
# Add to Settings class:
SUPABASE_DATABASE_URL: str = Field(
    default="",
    description="Supabase PostgreSQL connection string"
)
```

### 5.4 Set environment variable:
```bash
# In Render dashboard or .env file:
SUPABASE_DATABASE_URL=postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres
```

---

## Step 6: Update Queries (SQLite → PostgreSQL)

### Key differences:
- SQLite: `?` placeholders → PostgreSQL: `%s`
- SQLite: `date('now', '-3 months')` → PostgreSQL: `CURRENT_DATE - INTERVAL '3 months'`
- SQLite: `LIMIT ? OFFSET ?` → PostgreSQL: `LIMIT %s OFFSET %s`

### Example conversion:
```python
# SQLite (old):
cursor.execute("SELECT * FROM purchase_orders WHERE document_date > date('now', '-3 months')")

# PostgreSQL (new):
cursor.execute("SELECT * FROM purchase_orders WHERE document_date > CURRENT_DATE - INTERVAL '3 months'")
```

---

## Step 7: Test & Deploy

1. Test locally with Supabase connection
2. Verify all features work:
   - ✅ Stock view
   - ✅ Priority items
   - ✅ Recent orders (last 3 months)
   - ✅ Supplier invoices (last 3 months)
   - ✅ Inventory analysis
3. Deploy to Render with `SUPABASE_DATABASE_URL` environment variable

---

## Benefits After Migration

✅ **Instant Access**: No more 10-minute download waits
✅ **Real-time Sync**: Changes visible immediately
✅ **Multiple Users**: All users see same data instantly
✅ **Automatic Backups**: Supabase handles backups
✅ **Free Tier**: 500MB database, 2GB bandwidth/month
✅ **Scalable**: Easy to upgrade if needed

---

## Troubleshooting

### Database still too large after cleanup?
- Reduce `keep_months` to 2 or 1:
  ```bash
  python scripts/cleanup_database.py cache/pharma_stock.db 2
  ```

### Migration fails?
- Check connection string format
- Ensure Supabase project is active
- Check firewall/network access

### Queries not working?
- Check SQL syntax (SQLite vs PostgreSQL)
- Use `%s` instead of `?` for parameters
- Check table names (case-sensitive in PostgreSQL)

---

## Next Steps

1. ✅ Clean database (Step 1)
2. ✅ Create Supabase project (Step 2)
3. ✅ Migrate data (Step 4)
4. ✅ Update app code (Step 5-6)
5. ✅ Test & deploy (Step 7)

**Total time**: ~30-45 minutes
**Result**: Instant access, no more Google Drive sync! 🎉

