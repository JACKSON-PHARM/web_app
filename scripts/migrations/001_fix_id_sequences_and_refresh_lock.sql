-- ============================================================
-- PRODUCTION-SAFE MIGRATION: Fix ID Sequences & Refresh Lock
-- ============================================================
-- This migration fixes three critical production issues:
-- 1. Missing DEFAULT sequences for id columns (causing insert failures)
-- 2. Creates refresh lock mechanism (prevents concurrent refreshes)
-- 3. Safe to run multiple times (idempotent)
-- ============================================================

BEGIN;

-- ============================================================
-- PART 1: Fix ID Sequences for Tables Missing DEFAULT
-- ============================================================

-- Function to safely create sequence and attach to column
DO $$
DECLARE
    seq_name TEXT;
    max_id INTEGER;
BEGIN
    -- Fix purchase_orders.id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'purchase_orders' 
        AND column_name = 'id' 
        AND column_default LIKE 'nextval%'
    ) THEN
        seq_name := 'purchase_orders_id_seq';
        
        -- Create sequence if it doesn't exist
        IF NOT EXISTS (SELECT 1 FROM pg_sequences WHERE schemaname = 'public' AND sequencename = seq_name) THEN
            EXECUTE format('CREATE SEQUENCE %I', seq_name);
            RAISE NOTICE 'Created sequence: %', seq_name;
        END IF;
        
        -- Set sequence to current max id + 1 (safe for existing data)
        EXECUTE format('SELECT COALESCE(MAX(id), 0) FROM purchase_orders') INTO max_id;
        EXECUTE format('SELECT setval(%L, %s, true)', seq_name, GREATEST(max_id, 1));
        
        -- Attach sequence as DEFAULT
        ALTER TABLE purchase_orders ALTER COLUMN id SET DEFAULT nextval('purchase_orders_id_seq');
        RAISE NOTICE 'Fixed purchase_orders.id with sequence %', seq_name;
    END IF;
    
    -- Fix supplier_invoices.id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'supplier_invoices' 
        AND column_name = 'id' 
        AND column_default LIKE 'nextval%'
    ) THEN
        seq_name := 'supplier_invoices_id_seq';
        
        IF NOT EXISTS (SELECT 1 FROM pg_sequences WHERE schemaname = 'public' AND sequencename = seq_name) THEN
            EXECUTE format('CREATE SEQUENCE %I', seq_name);
            RAISE NOTICE 'Created sequence: %', seq_name;
        END IF;
        
        EXECUTE format('SELECT COALESCE(MAX(id), 0) FROM supplier_invoices') INTO max_id;
        EXECUTE format('SELECT setval(%L, %s, true)', seq_name, GREATEST(max_id, 1));
        
        ALTER TABLE supplier_invoices ALTER COLUMN id SET DEFAULT nextval('supplier_invoices_id_seq');
        RAISE NOTICE 'Fixed supplier_invoices.id with sequence %', seq_name;
    END IF;
    
    -- Fix branch_orders.id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'branch_orders' 
        AND column_name = 'id' 
        AND column_default LIKE 'nextval%'
    ) THEN
        seq_name := 'branch_orders_id_seq';
        
        IF NOT EXISTS (SELECT 1 FROM pg_sequences WHERE schemaname = 'public' AND sequencename = seq_name) THEN
            EXECUTE format('CREATE SEQUENCE %I', seq_name);
            RAISE NOTICE 'Created sequence: %', seq_name;
        END IF;
        
        EXECUTE format('SELECT COALESCE(MAX(id), 0) FROM branch_orders') INTO max_id;
        EXECUTE format('SELECT setval(%L, %s, true)', seq_name, GREATEST(max_id, 1));
        
        ALTER TABLE branch_orders ALTER COLUMN id SET DEFAULT nextval('branch_orders_id_seq');
        RAISE NOTICE 'Fixed branch_orders.id with sequence %', seq_name;
    END IF;
END $$;

-- ============================================================
-- PART 2: Create Refresh Lock Table
-- ============================================================

-- Table to track refresh operations (for monitoring/debugging)
CREATE TABLE IF NOT EXISTS refresh_lock (
    id SERIAL PRIMARY KEY,
    lock_type TEXT NOT NULL UNIQUE,  -- 'global', 'stock', 'orders', etc.
    locked_by TEXT,                  -- Process/thread identifier
    locked_at TIMESTAMP,
    expires_at TIMESTAMP,
    status TEXT DEFAULT 'active'     -- 'active', 'completed', 'failed'
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_refresh_lock_type ON refresh_lock(lock_type);
CREATE INDEX IF NOT EXISTS idx_refresh_lock_expires ON refresh_lock(expires_at) WHERE status = 'active';

-- Function to acquire refresh lock using Postgres advisory lock (pg_advisory_lock)
-- Uses a fixed lock ID (12345) for global refresh lock - works across all processes/workers
CREATE OR REPLACE FUNCTION acquire_refresh_lock(
    p_lock_type TEXT DEFAULT 'global',
    p_locked_by TEXT DEFAULT 'unknown',
    p_timeout_seconds INTEGER DEFAULT 3600  -- 1 hour default timeout
) RETURNS BOOLEAN AS $$
DECLARE
    v_expires_at TIMESTAMP;
    v_lock_id BIGINT;
    v_lock_acquired BOOLEAN;
BEGIN
    -- Use a fixed lock ID based on lock_type (hash to bigint)
    -- Global lock uses ID 12345, other types use different IDs
    IF p_lock_type = 'global' THEN
        v_lock_id := 12345;
    ELSE
        -- Hash lock_type to a bigint (simple hash)
        v_lock_id := abs(hashtext(p_lock_type))::BIGINT;
    END IF;
    
    -- Try to acquire Postgres advisory lock (non-blocking)
    -- pg_try_advisory_lock returns true if acquired, false if already held
    SELECT pg_try_advisory_lock(v_lock_id) INTO v_lock_acquired;
    
    IF NOT v_lock_acquired THEN
        -- Lock is already held by another process
        RETURN FALSE;
    END IF;
    
    -- Lock acquired - record in refresh_lock table for monitoring
    v_expires_at := NOW() + (p_timeout_seconds || ' seconds')::INTERVAL;
    
    -- Clean up expired locks first
    DELETE FROM refresh_lock 
    WHERE status = 'active' 
    AND expires_at < NOW();
    
    -- Record lock acquisition
    INSERT INTO refresh_lock (lock_type, locked_by, locked_at, expires_at, status)
    VALUES (p_lock_type, p_locked_by, NOW(), v_expires_at, 'active')
    ON CONFLICT (lock_type) DO UPDATE
    SET locked_by = p_locked_by,
        locked_at = NOW(),
        expires_at = v_expires_at,
        status = 'active';
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Function to release refresh lock (releases Postgres advisory lock)
CREATE OR REPLACE FUNCTION release_refresh_lock(
    p_lock_type TEXT DEFAULT 'global',
    p_locked_by TEXT DEFAULT NULL
) RETURNS BOOLEAN AS $$
DECLARE
    v_updated INTEGER;
    v_lock_id BIGINT;
BEGIN
    -- Use same lock ID as acquire_refresh_lock
    IF p_lock_type = 'global' THEN
        v_lock_id := 12345;
    ELSE
        v_lock_id := abs(hashtext(p_lock_type))::BIGINT;
    END IF;
    
    -- Release Postgres advisory lock
    PERFORM pg_advisory_unlock(v_lock_id);
    
    -- Update refresh_lock table for monitoring
    IF p_locked_by IS NULL THEN
        UPDATE refresh_lock 
        SET status = 'completed', expires_at = NOW()
        WHERE lock_type = p_lock_type 
        AND status = 'active';
    ELSE
        UPDATE refresh_lock 
        SET status = 'completed', expires_at = NOW()
        WHERE lock_type = p_lock_type 
        AND locked_by = p_locked_by
        AND status = 'active';
    END IF;
    
    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RETURN TRUE;  -- Always return true if advisory lock was released
END;
$$ LANGUAGE plpgsql;

-- Function to check if refresh is locked (checks Postgres advisory lock)
CREATE OR REPLACE FUNCTION is_refresh_locked(
    p_lock_type TEXT DEFAULT 'global'
) RETURNS BOOLEAN AS $$
DECLARE
    v_exists BOOLEAN;
    v_lock_id BIGINT;
    v_lock_held BOOLEAN;
BEGIN
    -- Use same lock ID as acquire_refresh_lock
    IF p_lock_type = 'global' THEN
        v_lock_id := 12345;
    ELSE
        v_lock_id := abs(hashtext(p_lock_type))::BIGINT;
    END IF;
    
    -- Check if Postgres advisory lock is held
    -- pg_advisory_lock_held checks if lock is held by ANY session
    SELECT pg_advisory_lock_held(v_lock_id) INTO v_lock_held;
    
    -- Also check refresh_lock table for monitoring
    DELETE FROM refresh_lock 
    WHERE status = 'active' 
    AND expires_at < NOW();
    
    SELECT EXISTS(
        SELECT 1 FROM refresh_lock 
        WHERE lock_type = p_lock_type 
        AND status = 'active'
    ) INTO v_exists;
    
    -- Return true if advisory lock is held OR table shows active lock
    RETURN v_lock_held OR v_exists;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- PART 3: Create Staging Table for Atomic Stock Refresh
-- ============================================================

-- Staging table for current_stock (same structure as current_stock)
CREATE TABLE IF NOT EXISTS current_stock_staging (
    LIKE current_stock INCLUDING ALL
);

-- Indexes on staging table (same as main table)
CREATE INDEX IF NOT EXISTS idx_current_stock_staging_branch_item 
    ON current_stock_staging(branch, item_code, company);
CREATE INDEX IF NOT EXISTS idx_current_stock_staging_company 
    ON current_stock_staging(company);
CREATE INDEX IF NOT EXISTS idx_current_stock_staging_item 
    ON current_stock_staging(item_code);

COMMIT;

-- ============================================================
-- VERIFICATION QUERIES (run these to verify migration)
-- ============================================================

-- Verify sequences exist and are attached:
-- SELECT table_name, column_name, column_default 
-- FROM information_schema.columns 
-- WHERE table_name IN ('purchase_orders', 'supplier_invoices', 'branch_orders')
-- AND column_name = 'id';

-- Verify lock functions exist:
-- SELECT proname FROM pg_proc WHERE proname LIKE '%refresh_lock%';

-- Verify staging table exists:
-- SELECT table_name FROM information_schema.tables WHERE table_name = 'current_stock_staging';

