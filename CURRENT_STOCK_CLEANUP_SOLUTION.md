# Current Stock Cleanup Solution

## Problem
The `current_stock` table was accumulating duplicate versions of stock data, causing the database to exceed the 0.5 GB Supabase free tier limit. The table should only contain **one version per (branch, company, item_code)** combination.

## Solution Overview

We've implemented a comprehensive solution with multiple layers of protection:

1. **Database Migration** - Cleans existing duplicates and sets up constraints
2. **Automatic Cleanup Trigger** - Prevents duplicates on insert
3. **Application-Level Cleanup** - Cleans old versions before inserting new data
4. **Manual Cleanup Script** - For maintenance and immediate cleanup

## Files Created/Modified

### 1. Database Migration
**File:** `scripts/migrations/002_cleanup_current_stock_duplicates.sql`

This migration:
- Removes existing duplicate records (keeps most recent per branch/company/item_code)
- Creates a unique constraint to prevent future duplicates
- Creates a trigger function to automatically clean old versions
- Creates a manual cleanup function for maintenance

**To run:**
```bash
psql -h your-supabase-host -U postgres -d postgres -f scripts/migrations/002_cleanup_current_stock_duplicates.sql
```

### 2. Updated Stock Fetcher
**File:** `scripts/data_fetchers/database_stock_fetcher.py`

Modified `process_company_stock()` to:
- Extract unique branches from incoming data
- Delete old versions for those branches before inserting
- Ensures only the latest version exists per branch

### 3. Updated Database Manager
**File:** `app/services/postgres_database_manager.py`

Modified `insert_current_stock()` to:
- When `replace_all=False` (append mode), clean up old versions per (branch, company) before inserting
- Ensures no duplicates even in append mode

### 4. Cleanup Script
**File:** `scripts/cleanup_current_stock_duplicates.py`

Standalone script for manual cleanup:
- Check for duplicates without deleting: `python scripts/cleanup_current_stock_duplicates.py --check-only`
- Clean up duplicates: `python scripts/cleanup_current_stock_duplicates.py`

## How It Works

### Automatic Cleanup (During Inserts)

1. **UPSERT Mode**: For append mode, uses `INSERT ... ON CONFLICT DO UPDATE` (UPSERT)
   - Atomically updates existing records or inserts new ones
   - **Never deletes old data before insert** - ensures we always have data
   - If insert fails, old data is preserved

2. **After Insert**: Post-insert cleanup removes any remaining old versions
   - Only runs after successful insert
   - Keeps only the most recent version per (branch, company, item_code)

### Database Trigger (Safety Net)

A PostgreSQL trigger (`trigger_cleanup_old_stock_versions`) runs **AFTER** each INSERT:
- Automatically deletes any older records with the same (branch, company, item_code)
- **Runs AFTER insert** to avoid data loss if insert fails
- Ensures only the latest version exists
- Acts as a safety net to prevent duplicates

### Unique Constraint

A unique index on `(UPPER(TRIM(branch)), UPPER(TRIM(company)), item_code)`:
- Prevents duplicate inserts at the database level
- Handles case-insensitive and whitespace variations

## Immediate Actions Required

### Step 1: Run the Migration
```bash
# Connect to your Supabase database and run:
psql -h your-supabase-host -U postgres -d postgres -f scripts/migrations/002_cleanup_current_stock_duplicates.sql
```

This will:
- Remove existing duplicates (should significantly reduce table size)
- Set up the trigger and constraint
- Reclaim space with VACUUM

### Step 2: Verify Cleanup
```bash
# Check for duplicates
python scripts/cleanup_current_stock_duplicates.py --check-only
```

### Step 3: Monitor Database Size
After cleanup, check your Supabase dashboard to verify the database size is below 0.5 GB.

## Expected Results

After running the migration:
- **Before**: ~1.9M rows (with duplicates)
- **After**: ~200K-500K rows (one per branch/company/item_code)
- **Storage**: Should reduce from ~388 MB to ~50-100 MB

## Ongoing Protection

Going forward:
1. **Automatic**: Every stock refresh will automatically clean old versions
2. **Trigger**: Database trigger ensures no duplicates can be inserted
3. **Constraint**: Unique constraint prevents duplicates at the database level

## Manual Cleanup (If Needed)

If duplicates accumulate again (shouldn't happen with the new system):

```bash
# Check status
python scripts/cleanup_current_stock_duplicates.py --check-only

# Clean up
python scripts/cleanup_current_stock_duplicates.py
```

Or use the database function directly:
```sql
SELECT * FROM cleanup_current_stock_duplicates();
```

## Monitoring

To monitor the current_stock table size:

```sql
-- Check table size
SELECT 
    pg_size_pretty(pg_total_relation_size('current_stock')) as total_size,
    pg_size_pretty(pg_relation_size('current_stock')) as table_size,
    COUNT(*) as row_count
FROM current_stock;

-- Check for duplicates
SELECT 
    branch, 
    company, 
    item_code, 
    COUNT(*) as versions
FROM current_stock
GROUP BY branch, company, item_code
HAVING COUNT(*) > 1;
```

## Notes

- The cleanup preserves the **most recent** version (highest `id`) for each (branch, company, item_code)
- Case-insensitive matching handles "NILA" vs "nila" variations
- Whitespace is trimmed for consistency
- The trigger may slightly slow down bulk inserts, but ensures data integrity
- All cleanup operations are logged for monitoring

## Troubleshooting

### If migration fails:
1. Check database connection
2. Ensure you have proper permissions
3. Check if trigger/function already exists (migration handles this)

### If duplicates still appear:
1. Check if trigger is enabled: `SELECT * FROM pg_trigger WHERE tgname = 'trigger_cleanup_old_stock_versions';`
2. Check if unique constraint exists: `\d current_stock` in psql
3. Run manual cleanup script

### Performance concerns:
- The trigger fires for each row during bulk inserts
- If performance is an issue, consider disabling trigger during bulk operations:
  ```sql
  ALTER TABLE current_stock DISABLE TRIGGER trigger_cleanup_old_stock_versions;
  -- ... bulk insert ...
  ALTER TABLE current_stock ENABLE TRIGGER trigger_cleanup_old_stock_versions;
  ```

