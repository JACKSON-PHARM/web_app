# 🔄 Update stock_snapshot Function on Render

## Problem
The localhost version shows correct item names (not "NO SALES DATA"), but Render still shows "NO SALES DATA" because the SQL function hasn't been updated on Render's database.

## Solution: Update the Function on Render

### Option 1: Run Update Script Locally (Recommended)

If Render and localhost use the **same Supabase database**, the function is already updated! But if they use different databases, run:

```bash
python scripts/update_stock_snapshot_render.py
```

**Make sure DATABASE_URL points to Render's database:**
- Check Render Dashboard → Environment → `DATABASE_URL`
- Set it temporarily in your local environment:
  ```powershell
  $env:DATABASE_URL = "postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres"
  ```
- Then run the script

### Option 2: Update via Supabase SQL Editor (Easiest)

1. **Go to Supabase Dashboard**
   - https://supabase.com/dashboard
   - Select your project

2. **Open SQL Editor**
   - Click "SQL Editor" in left sidebar
   - Click "New query"

3. **Copy and Paste the SQL Function**
   - Open `scripts/create_stock_snapshot_function.sql` in your code editor
   - Copy the entire contents
   - Paste into Supabase SQL Editor

4. **Run the Query**
   - Click "Run" or press `Ctrl+Enter`
   - Should see: "Success. No rows returned"

5. **Verify**
   - Run this query to verify:
   ```sql
   SELECT pg_get_function_arguments(oid) 
   FROM pg_proc 
   WHERE proname = 'stock_snapshot' 
   AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public');
   ```
   - Should show: `p_target_branch text, p_source_branch text, p_target_company text, p_source_company text DEFAULT NULL`

### Option 3: Deploy Updated Code to Render

The Python code that calls the function also needs to be deployed:

1. **Commit and Push Code**
   ```bash
   git add .
   git commit -m "Update stock_snapshot function for cross-company and item name fallback"
   git push origin main
   ```

2. **Trigger Render Deployment**
   - Go to Render Dashboard
   - Your Service → Manual Deploy → Deploy latest commit
   - Or wait for automatic deployment

3. **Verify Deployment**
   - Check Render logs for successful deployment
   - Visit: https://web-app-c2ws.onrender.com/stock-view
   - Item names should now show correctly (not "NO SALES DATA")

## Quick Check: Are They Using the Same Database?

Run this locally to check:
```python
python -c "from app.config import settings; print('Local DATABASE_URL:', settings.DATABASE_URL[:50] + '...' if settings.DATABASE_URL else 'NOT SET')"
```

Then check Render Dashboard → Environment → `DATABASE_URL`

**If they match:** Function is already updated! Just need to deploy code.
**If they differ:** Use Option 1 or 2 to update Render's database.

## What the Update Does

The updated `stock_snapshot()` function:
1. ✅ Supports cross-company stock views (target DAIMA + source NILA works)
2. ✅ Shows actual item names instead of "NO SALES DATA"
3. ✅ Falls back to `current_stock` table for item names when inventory_analysis has "NO SALES DATA"

## After Update

1. **Clear Browser Cache** (Ctrl+Shift+R or Cmd+Shift+R)
2. **Refresh Stock View** on Render
3. **Verify** item names show correctly

