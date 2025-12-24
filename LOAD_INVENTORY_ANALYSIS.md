# Load Inventory Analysis CSV to Supabase

The Inventory Analysis CSV contains critical data:
- **Branches** (company_name, branch_name)
- **ABC Classes** (abc_class)
- **AMC** (Average Monthly Consumption - base_amc, adjusted_amc)
- **Stock Recommendations** (stock_recommendation)
- **Ideal Stock Levels** (ideal_stock_pieces)
- And more...

## Quick Load

1. **Get your Supabase connection string** (from `.env` file or Supabase dashboard)

2. **Run the load script:**
   ```bash
   cd web_app
   python scripts/load_inventory_analysis_to_supabase.py "postgresql://user:password@host:port/database" "resources/templates/Inventory_Analysis.csv"
   ```

   Or if the CSV is in the default location:
   ```bash
   python scripts/load_inventory_analysis_to_supabase.py "postgresql://user:password@host:port/database"
   ```

3. **Verify the data loaded:**
   - Check Supabase dashboard → Table Editor → `inventory_analysis`
   - Should see ~93,000 rows
   - Should see branches like "BABA DOGO HQ", "DAIMA MERU WHOLESALE", etc.

## What This Does

1. Creates `inventory_analysis` table in Supabase (if it doesn't exist)
2. Loads all data from `Inventory_Analysis.csv`
3. Creates indexes for fast queries
4. Shows summary of branches and item counts

## After Loading

- ✅ Branches will appear in dashboard dropdowns
- ✅ ABC classes will be assigned to items
- ✅ AMC values will be available for stock level calculations
- ✅ Stock recommendations will be displayed

## Troubleshooting

- **"Table already exists"**: The script will truncate and reload data
- **"CSV not found"**: Specify the full path to the CSV file
- **"Connection failed"**: Check your connection string (password encoding, etc.)

