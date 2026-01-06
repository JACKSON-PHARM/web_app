-- Migration: Add secondary admin role and branch assignment to users
-- This migration:
-- 1. Adds is_user_admin field (secondary admin - can manage users but not full admin)
-- 2. Adds assigned_branch and assigned_company fields to tie users to branches
-- 3. Adds indexes for efficient lookups

-- Step 1: Add is_user_admin column (secondary admin role)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'app_users' 
        AND column_name = 'is_user_admin'
    ) THEN
        ALTER TABLE app_users 
        ADD COLUMN is_user_admin BOOLEAN DEFAULT FALSE;
        
        RAISE NOTICE 'Added is_user_admin column';
    ELSE
        RAISE NOTICE 'is_user_admin column already exists';
    END IF;
END $$;

-- Step 2: Add assigned_branch column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'app_users' 
        AND column_name = 'assigned_branch'
    ) THEN
        ALTER TABLE app_users 
        ADD COLUMN assigned_branch TEXT;
        
        RAISE NOTICE 'Added assigned_branch column';
    ELSE
        RAISE NOTICE 'assigned_branch column already exists';
    END IF;
END $$;

-- Step 3: Add assigned_company column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'app_users' 
        AND column_name = 'assigned_company'
    ) THEN
        ALTER TABLE app_users 
        ADD COLUMN assigned_company TEXT;
        
        RAISE NOTICE 'Added assigned_company column';
    ELSE
        RAISE NOTICE 'assigned_company column already exists';
    END IF;
END $$;

-- Step 4: Create indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_app_users_user_admin ON app_users(is_user_admin) WHERE is_user_admin = TRUE;
CREATE INDEX IF NOT EXISTS idx_app_users_assigned_branch ON app_users(assigned_branch, assigned_company);
CREATE INDEX IF NOT EXISTS idx_app_users_branch_company ON app_users(UPPER(TRIM(assigned_branch)), UPPER(TRIM(assigned_company)));

-- Step 5: Add comments to document the new fields
COMMENT ON COLUMN app_users.is_user_admin IS 
'Secondary admin role - can create/modify user accounts but not full admin privileges';

COMMENT ON COLUMN app_users.assigned_branch IS 
'Branch name that the user is assigned to. Users can only send orders to this branch.';

COMMENT ON COLUMN app_users.assigned_company IS 
'Company name that the user is assigned to. Must match assigned_branch company.';

DO $$
BEGIN
    RAISE NOTICE '✅ Migration complete: Added secondary admin role and branch assignment to users';
END $$;

