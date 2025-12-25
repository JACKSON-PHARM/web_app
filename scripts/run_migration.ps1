# Run migration script from correct directory
Set-Location (Split-Path -Parent $PSScriptRoot)
python scripts/create_supabase_tables.py
Read-Host "Press Enter to continue"

