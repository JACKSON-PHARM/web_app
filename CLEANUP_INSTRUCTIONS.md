# Database Cleanup Instructions - Procurement Focus

## What Gets Cleaned

### ✅ KEEP (Essential for Procurement):
1. **Current Stock** - All records (replaced entirely on each refresh)
2. **Recent Orders** - Last 3 months only
   - `purchase_orders` (last 3 months)
   - `branch_orders` (last 3 months)
3. **Recent Supplier Invoices** - Last 3 months only
   - `supplier_invoices` (last 3 months)
4. **Inventory Analysis** - CSV file (ABC class, AMC metrics)
   - Stored in `resources/templates/Inventory_Analysis.csv`
   - Not in database - loaded from CSV file

### ❌ REMOVE (Not needed for procurement):
1. **Old Orders** - Older than 3 months
2. **Old Invoices** - Older than 3 months
3. **Sales Data** - Entire table removed (not needed)
4. **Historical Stock Snapshots** - Entire `stock_data` table removed
   - Only `current_stock` is kept (replaced on each refresh)

---

## How to Run Cleanup

### Step 1: Navigate to web_app directory
```powershell
cd C:\PharmaStockApp\web_app
```

### Step 2: Run cleanup script
```powershell
python scripts/cleanup_database.py cache/pharma_stock.db 3
```

**What happens:**
- ✅ Deletes orders older than 3 months
- ✅ Deletes invoices older than 3 months
- ✅ Removes ALL sales data
- ✅ Removes ALL stock snapshots (stock_data table)
- ✅ Keeps only current_stock (will be replaced on refresh)
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
🧹 Removing all stock snapshots...
   Deleted 100000 stock snapshots
   Dropped stock_data table
🧹 Removing sales data...
   Removed sales tables
📊 Creating indexes...
🧹 Vacuuming database...
✅ Cleanup complete!
📊 New database size: 150.00 MB
✅ Database fits in Supabase free tier (500MB limit)
```

---

## After Cleanup

### Database Structure:
- ✅ `current_stock` - Current stock (replaced on each refresh)
- ✅ `purchase_orders` - Last 3 months only
- ✅ `branch_orders` - Last 3 months only
- ✅ `supplier_invoices` - Last 3 months only
- ✅ `items` - Item master data
- ✅ `document_tracker` - For incremental loading
- ❌ `sales` - Removed (not needed)
- ❌ `stock_data` - Removed (not needed)

### Inventory Analysis:
- Stored in CSV file: `resources/templates/Inventory_Analysis.csv`
- Contains: ABC class, AMC, customer appeal, etc.
- Loaded dynamically when needed (not in database)

---

## How Current Stock Works

### On Each Refresh:
1. **Delete all** `current_stock` records
2. **Fetch fresh** stock data from API
3. **Insert new** stock data
4. **Result**: Only current stock exists (no historical snapshots)

This ensures:
- ✅ Removed items are deleted from database
- ✅ Stock is always current
- ✅ No historical snapshots (saves space)

---

## Ready for Supabase Migration

After cleanup, your database will be:
- ✅ Small enough for Supabase free tier (<500MB)
- ✅ Contains only procurement-essential data
- ✅ Optimized with indexes
- ✅ Ready to migrate

**Next step**: Run migration script to Supabase!

