# User Admin and Branch Restriction Feature

## Overview

This feature adds:
1. **Secondary Admin Role** - Users who can create/modify user accounts (but not full admin)
2. **Branch Assignment** - Users can be tied to specific branches
3. **Order Restrictions** - Users can only send orders to their assigned branch

## Database Migration

Run the migration to add the new fields:

```bash
psql -h your-supabase-host -U postgres -d postgres -f scripts/migrations/003_add_user_admin_and_branch_assignment.sql
```

This adds:
- `is_user_admin` - Boolean flag for secondary admin role
- `assigned_branch` - Branch name the user is assigned to
- `assigned_company` - Company name the user is assigned to

## User Roles

### Full Admin (`is_admin = TRUE`)
- Can do everything
- Can create other admins
- Can send orders to any branch
- No branch restrictions

### Secondary Admin (`is_user_admin = TRUE`)
- Can create/modify user accounts
- Can activate/deactivate users
- Can update subscriptions
- **Cannot** create other admins
- **Cannot** access full admin features
- Subject to branch restrictions (if assigned)

### Regular User
- Can use the app normally
- Subject to branch restrictions (if assigned)

## Branch Restrictions

### How It Works

1. **Users with branch assignment**:
   - Can only send orders to their assigned branch
   - Cannot send orders to other branches
   - Error message shown if they try

2. **Users without branch assignment**:
   - Can send orders to any branch (no restrictions)
   - Useful for admin users or flexible users

3. **Full admins**:
   - Always bypass branch restrictions
   - Can send orders to any branch

### Example

```python
# User "john" is assigned to "BABA DOGO HQ" branch, "NILA" company
# User "john" tries to send order to "KISUMU" branch
# Result: Error - "You can only send orders to your assigned branch: BABA DOGO HQ (NILA)"
```

## API Changes

### Create User Request

```json
{
  "username": "john",
  "password": "password123",
  "subscription_days": 30,
  "is_admin": false,
  "is_user_admin": true,  // NEW: Secondary admin role
  "assigned_branch": "BABA DOGO HQ",  // NEW: Branch assignment
  "assigned_company": "NILA"  // NEW: Company assignment
}
```

### User Info Response

```json
{
  "username": "john",
  "is_admin": false,
  "is_user_admin": true,
  "assigned_branch": "BABA DOGO HQ",
  "assigned_company": "NILA",
  "active": true,
  "subscription_days": 30,
  "days_remaining": 25
}
```

## Endpoint Access

### User Management Endpoints

All user management endpoints now allow both **full admin** and **user admin**:
- `POST /api/admin/users/create` - Create user
- `POST /api/admin/users/update-subscription` - Update subscription
- `POST /api/admin/users/activate` - Activate user
- `POST /api/admin/users/deactivate` - Deactivate user
- `POST /api/admin/users/delete` - Delete user
- `GET /api/admin/users/list` - List users

**Note**: Only full admins can create other admins (`is_admin = true`).

### Procurement Endpoint

`POST /api/procurement/run` now checks branch restrictions:
- If user has `assigned_branch` and `assigned_company`, they can only order for that branch
- Full admins bypass this check
- Returns 403 error if user tries to order for different branch

## Usage Examples

### Creating a Secondary Admin with Branch Assignment

```python
# As full admin, create a user admin for a specific branch
POST /api/admin/users/create
{
  "username": "branch_manager",
  "password": "secure123",
  "subscription_days": 365,
  "is_admin": false,
  "is_user_admin": true,
  "assigned_branch": "BABA DOGO HQ",
  "assigned_company": "NILA"
}
```

### Creating a Regular User with Branch Restriction

```python
# As admin or user_admin, create a regular user for a branch
POST /api/admin/users/create
{
  "username": "branch_user",
  "password": "password123",
  "subscription_days": 90,
  "is_admin": false,
  "is_user_admin": false,
  "assigned_branch": "KISUMU",
  "assigned_company": "NILA"
}
```

### Sending Order (Branch Restriction Check)

```python
# User "branch_user" tries to send order
POST /api/procurement/run
{
  "branch_name": "KISUMU",  // ✅ Allowed - matches assigned branch
  "branch_company": "NILA",
  ...
}

# User "branch_user" tries to send order to different branch
POST /api/procurement/run
{
  "branch_name": "BABA DOGO HQ",  // ❌ Error - doesn't match assigned branch
  "branch_company": "NILA",
  ...
}
# Response: 403 Forbidden
# "You can only send orders to your assigned branch: KISUMU (NILA)"
```

## Migration Steps

1. **Run the migration**:
   ```bash
   psql -h your-supabase-host -U postgres -d postgres -f scripts/migrations/003_add_user_admin_and_branch_assignment.sql
   ```

2. **Update existing users** (optional):
   ```sql
   -- Assign a branch to an existing user
   UPDATE app_users 
   SET assigned_branch = 'BABA DOGO HQ', 
       assigned_company = 'NILA'
   WHERE username = 'existing_user';
   
   -- Make an existing user a secondary admin
   UPDATE app_users 
   SET is_user_admin = TRUE
   WHERE username = 'existing_user';
   ```

3. **Test the feature**:
   - Create a user admin
   - Assign a branch to a user
   - Try sending orders (should be restricted)

## Security Notes

- **Full admins** can always bypass branch restrictions
- **User admins** cannot create other admins (only full admins can)
- Branch restrictions are enforced at the API level
- Users without branch assignment have no restrictions (backward compatible)

## Backward Compatibility

- Existing users without branch assignment continue to work normally
- No breaking changes to existing functionality
- New fields are optional (can be NULL)

