# How to Run Migration Script

## Quick Fix

You're currently in the wrong directory. Run these commands:

```powershell
# Navigate to the correct directory
cd C:\PharmaStockApp\web_app

# Run the migration script
python scripts/create_supabase_tables.py
```

## Alternative: Use Helper Script

From anywhere, you can run:

```powershell
cd C:\PharmaStockApp\web_app
.\scripts\run_migration.ps1
```

Or double-click `run_migration.bat` from Windows Explorer.

## Verify You're in the Right Place

Before running, make sure you can see:
- `app` folder
- `scripts` folder  
- `templates` folder

If you see `web_app` folder inside `web_app`, you're in the wrong place!

## Troubleshooting

### Error: "DATABASE_URL not set"
Set the environment variable:
```powershell
$env:DATABASE_URL="your_supabase_connection_string"
python scripts/create_supabase_tables.py
```

### Error: "can't open file"
Make sure you're in `C:\PharmaStockApp\web_app` directory, not `C:\PharmaStockApp\web_app\web_app`

### Error: "No module named 'app'"
Make sure you're running from `web_app` directory, not from `scripts` directory

