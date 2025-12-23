# Ready to Migrate! - Your Connection String

## ✅ Your Connection String (with password encoded):

```
postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres
```

**Note**: Special characters in password are URL-encoded:
- `?` → `%3F`
- `!` → `%21`  
- `$` → `%24`

---

## ⚠️ Important: IPv4 Warning

If you see "Not IPv4 compatible" warning in Supabase:
- **Use Session Pooler instead** (switch to "Session Pooler" tab in the modal)
- Session Pooler connection string will look like:
  ```
  postgresql://postgres.oagcmmkmypmwmeuodkym:[ENCODED_PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
  ```

---

## 🚀 Migration Steps (Run These Commands):

### Step 1: Clean Database (5 minutes)
```powershell
cd C:\PharmaStockApp\web_app
python scripts/cleanup_database.py cache/pharma_stock.db 3
```

### Step 2: Install PostgreSQL Driver
```powershell
pip install psycopg2-binary
```

### Step 3: Test Connection (Optional but recommended)
```powershell
python scripts/test_connection.py "postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres"
```

### Step 4: Migrate Database
```powershell
python scripts/migrate_to_supabase.py cache/pharma_stock.db "postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres"
```

---

## 🔄 If Direct Connection Doesn't Work:

1. In Supabase modal, switch to **"Session Pooler"** tab
2. Copy that connection string
3. Replace `[YOUR-PASSWORD]` with your encoded password: `b%3F%21HABE69%24TwwSV`
4. Use that connection string instead

---

## ✅ After Migration:

1. Verify tables in Supabase dashboard (Database → Tables)
2. Check data looks correct
3. We'll update app code to use PostgreSQL

**Ready to start? Run Step 1 (cleanup) first!**

