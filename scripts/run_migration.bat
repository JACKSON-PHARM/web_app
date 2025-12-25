@echo off
REM Run migration script from correct directory
cd /d %~dp0..
python scripts/create_supabase_tables.py
pause

