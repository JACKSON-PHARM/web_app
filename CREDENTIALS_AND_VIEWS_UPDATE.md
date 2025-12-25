# Credentials and Materialized Views Update

## Summary of Changes

### 1. Materialized Views - Full Columns

Updated materialized views to include ALL required columns for stock view and priority items:

**stock_view_materialized** now includes:
- Basic: item_code, item_name, target_branch, target_company
- Stock: supplier_stock, branch_stock, pack_size, unit_price, stock_value
- Orders: last_order_date, last_order_doc, last_order_quantity
- Invoices: last_invoice_date, last_invoice_doc, last_invoice_quantity
- Supply/GRN: last_supply_date, last_supply_doc, last_supply_quantity, last_grn_date, last_grn_quantity, last_grn_doc
- Analysis: abc_class, amc, stock_comment, stock_level_pct

**priority_items_materialized** now includes:
- Basic: item_code, item_name, source_branch, source_company, target_branch, target_company
- Stock: source_stock_pieces, target_stock_pieces, pack_size
- Analysis: abc_class, amc_pieces (as amc), stock_comment
- Orders: last_order_date, stock_level_pct

### 2. Credentials Management

**Fetchers**: Use saved credentials from Supabase (`app_credentials` table)
- Scheduler automatically uses saved credentials
- No user interaction needed for scheduled refreshes
- Credentials persist across deployments

**Procurement Bot**: Requires user-provided credentials for accountability
- User must enter Company, Username, and Password in procurement modal
- Credentials are NOT saved - used only for the current order
- Ensures accountability - each order uses current credentials

### 3. How to Use

#### Recreate Materialized Views

Run the migration script again to recreate views with full columns:

```bash
cd web_app
python scripts/create_supabase_tables.py
```

This will:
1. Drop existing simplified views
2. Create new views with all required columns
3. Create unique indexes for CONCURRENT refresh
4. Refresh the views

#### Using Procurement Bot

1. Select items in stock view or priority table
2. Click "Run Procurement Bot"
3. Select order mode (Purchase Order or Branch Order)
4. **Enter API credentials** (Company, Username, Password) - REQUIRED
5. Select supplier (for Purchase Orders) or destination branch (for Branch Orders)
6. Click "Create Order"

#### Scheduled Data Refresh

1. Go to Settings page
2. Enter and save API credentials for NILA and/or DAIMA
3. Credentials are saved to Supabase
4. Scheduler will automatically use these credentials every hour (8 AM - 6 PM)
5. Materialized views refresh automatically after each data sync

## Benefits

1. **Fast Queries**: Materialized views pre-compute all joins - queries in seconds instead of minutes
2. **Accountability**: Procurement bot requires current credentials - each order is traceable
3. **Automation**: Fetchers use saved credentials - no manual intervention needed
4. **Performance**: Views refresh concurrently (with unique indexes) - no blocking

## Troubleshooting

### Views not refreshing?
Check if unique indexes exist:
```sql
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename IN ('stock_view_materialized', 'priority_items_materialized');
```

If missing, recreate views:
```bash
python scripts/create_supabase_tables.py
```

### Procurement bot asking for credentials?
This is intentional! Procurement bot requires user-provided credentials for accountability. Enter current API credentials in the modal.

### Fetchers not using saved credentials?
Check if credentials are saved:
```sql
SELECT company_name, username, is_enabled FROM app_credentials;
```

Save credentials via Settings page in the web app.

