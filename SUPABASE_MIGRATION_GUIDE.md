# Supabase Migration Guide - Complete Setup

This guide covers migrating to Supabase for users, credentials, and materialized views.

## Step 1: Create Supabase Tables and Views

Run the migration script to create all necessary tables:

```bash
cd web_app
python scripts/create_supabase_tables.py
```

This will create:
- `app_users` table - stores user accounts
- `app_credentials` table - stores API credentials
- `stock_view_materialized` - materialized view for fast stock queries
- `priority_items_materialized` - materialized view for fast priority items

## Step 2: Verify Tables Created

Check Supabase dashboard to verify:
- Tables: `app_users`, `app_credentials`
- Materialized Views: `stock_view_materialized`, `priority_items_materialized`

## Step 3: Migrate Existing Users (Optional)

If you have existing users in the local file, you can migrate them:

```python
# Run this once to migrate users from local file to Supabase
from app.services.user_service import UserService
from app.services.user_service_supabase import UserServiceSupabase
from app.dependencies import get_db_manager

old_service = UserService()
new_service = UserServiceSupabase(get_db_manager())

# Get all users from old service and create in new service
# (You'll need to implement this migration script)
```

## Step 4: Materialized Views Auto-Refresh

Materialized views are automatically refreshed after each data refresh. The scheduler will:
1. Fetch data from APIs
2. Update tables in Supabase
3. Refresh materialized views automatically

## Benefits

1. **Users persist** - Stored in Supabase, not local files
2. **Credentials secure** - Stored in Supabase, accessible by scheduler
3. **Fast queries** - Materialized views pre-compute joins
4. **Free tier compatible** - Views refresh efficiently

## Performance Improvements

- **Stock View**: Uses `stock_view_materialized` - queries in seconds instead of minutes
- **Priority Items**: Uses `priority_items_materialized` - instant results
- **Auto-refresh**: Views refresh after each data sync

## Troubleshooting

### Views not refreshing?
Check if views exist:
```sql
SELECT * FROM pg_matviews WHERE schemaname = 'public';
```

Manually refresh:
```sql
REFRESH MATERIALIZED VIEW stock_view_materialized;
REFRESH MATERIALIZED VIEW priority_items_materialized;
```

### Users not persisting?
Check if `app_users` table exists and has data:
```sql
SELECT * FROM app_users;
```

### Credentials not working?
Check if `app_credentials` table exists:
```sql
SELECT company_name, username, is_enabled FROM app_credentials;
```

