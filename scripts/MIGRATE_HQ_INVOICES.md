# HQ Invoices Migration Guide

## Overview

This script migrates HQ invoice and branch transfer CSV files from the standalone script into Supabase.

## What It Does

1. **Reads CSV files** from `D:\DATA ANALYTICS\HQ_DAIMA_INVOICES` (or custom path)
2. **Processes invoices and transfers** - normalizes data from different CSV formats
3. **Calculates monthly quantities** - aggregates current month data
4. **Bulk loads to Supabase** - uses optimized bulk insert for fast loading
5. **Handles duplicates** - uses ON CONFLICT to update existing records

## Quick Start

### Run Migration

```powershell
cd c:\PharmaStockApp\web_app\scripts
python migrate_hq_invoices_csv_to_supabase.py
```

Or with custom connection string and folder:

```powershell
python migrate_hq_invoices_csv_to_supabase.py "postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres" "D:\DATA ANALYTICS\HQ_DAIMA_INVOICES"
```

## CSV File Structure Expected

The script looks for CSV files in this structure:

```
D:\DATA ANALYTICS\HQ_DAIMA_INVOICES\
├── 2025\
│   ├── 06\
│   │   ├── 01\
│   │   │   ├── INV_DAIMA_MERU_RETAIL_SD12345_20250601.csv
│   │   │   ├── BT_DAIMA_THIKA_RETAIL_BTR67890_20250601.csv
│   │   │   └── ...
```

### File Naming Patterns

- **Invoices**: `INV_*.csv` or `DAIMA_*_SD*_*.csv`
- **Transfers**: `BT_*.csv` or `*_BTR*_*.csv`

## What Gets Migrated

- **Invoice records** - Sales invoices from BABA DOGO HQ to Daima branches
- **Transfer records** - Branch transfers from BABA DOGO HQ
- **Monthly quantities** - Calculated `this_month_qty` for current month
- **Last values** - Keeps most recent values per branch/item

## After Migration

Once migration completes:

1. ✅ All historical HQ invoice data is in Supabase
2. ✅ The fetcher will continue incrementally from the latest date
3. ✅ Data is available for dashboard and stock view
4. ✅ Monthly quantities are calculated and stored

## Verification

After migration, check the data:

```sql
-- Check total records
SELECT COUNT(*) FROM hq_invoices;

-- Check date range
SELECT MIN(date), MAX(date) FROM hq_invoices WHERE date IS NOT NULL;

-- Check by branch
SELECT branch, COUNT(*) as count 
FROM hq_invoices 
GROUP BY branch 
ORDER BY count DESC;
```

## Next Steps

After migration:

1. ✅ Run the fetcher orchestrator - it will continue from latest date
2. ✅ Deploy to Render - app will use Supabase data
3. ✅ Test dashboard - verify HQ invoices appear correctly

## Troubleshooting

**No CSV files found:**
- Check the folder path: `D:\DATA ANALYTICS\HQ_DAIMA_INVOICES`
- Verify files exist in subdirectories

**Insert errors:**
- Check connection string is correct
- Verify `hq_invoices` table exists in Supabase
- Check CSV file format matches expected structure

**Slow loading:**
- Normal for large datasets
- Script shows progress every 5,000 records
- Uses bulk insert for speed

