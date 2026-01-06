-- Migration: Cleanup current_stock duplicates and ensure only one version per branch
-- This migration:
-- 1. Removes existing duplicate stock records (keeps only the most recent per branch/company/item_code)
-- 2. Creates a unique constraint to prevent future duplicates
-- 3. Creates a trigger to automatically delete old versions when new ones are inserted

-- Step 1: Remove existing duplicates (keep the most recent record based on id)
-- This will significantly reduce the table size
DO $$
DECLARE
    duplicate_count INTEGER;
    total_before INTEGER;
    total_after INTEGER;
BEGIN
    -- Count total records before cleanup
    SELECT COUNT(*) INTO total_before FROM current_stock;
    
    -- Count duplicates
    SELECT COUNT(*) INTO duplicate_count
    FROM (
        SELECT branch, company, item_code, COUNT(*) as cnt
        FROM current_stock
        GROUP BY branch, company, item_code
        HAVING COUNT(*) > 1
    ) duplicates;
    
    RAISE NOTICE 'Total records before cleanup: %', total_before;
    RAISE NOTICE 'Duplicate groups found: %', duplicate_count;
    
    -- Delete old versions, keeping only the most recent (highest id) for each (branch, company, item_code)
    DELETE FROM current_stock a
    USING current_stock b
    WHERE a.branch = b.branch
      AND a.company = b.company
      AND a.item_code = b.item_code
      AND a.id < b.id;
    
    GET DIAGNOSTICS duplicate_count = ROW_COUNT;
    
    -- Count total records after cleanup
    SELECT COUNT(*) INTO total_after FROM current_stock;
    
    RAISE NOTICE 'Deleted duplicate records: %', duplicate_count;
    RAISE NOTICE 'Total records after cleanup: %', total_after;
    RAISE NOTICE 'Space saved: % records', (total_before - total_after);
END $$;

-- Step 2: Create unique constraint to prevent future duplicates
-- This ensures only one record per (branch, company, item_code) combination
DO $$
BEGIN
    -- Drop existing constraint if it exists
    IF EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'current_stock_unique_branch_company_item'
    ) THEN
        ALTER TABLE current_stock 
        DROP CONSTRAINT current_stock_unique_branch_company_item;
        RAISE NOTICE 'Dropped existing unique constraint';
    END IF;
    
    -- Create unique constraint
    -- Using UPPER(TRIM()) to handle case-insensitive and whitespace issues
    CREATE UNIQUE INDEX IF NOT EXISTS current_stock_unique_branch_company_item_idx
    ON current_stock (UPPER(TRIM(branch)), UPPER(TRIM(company)), item_code);
    
    RAISE NOTICE 'Created unique constraint on (branch, company, item_code)';
END $$;

-- Step 3: Create function to automatically delete old versions after insert
-- NOTE: This runs AFTER insert to avoid data loss if insert fails
CREATE OR REPLACE FUNCTION cleanup_old_stock_versions()
RETURNS TRIGGER AS $$
BEGIN
    -- Delete any existing records with the same (branch, company, item_code) that are older
    -- This ensures only the latest version exists
    -- Runs AFTER insert so if insert fails, old data is preserved
    DELETE FROM current_stock
    WHERE UPPER(TRIM(branch)) = UPPER(TRIM(NEW.branch))
      AND UPPER(TRIM(company)) = UPPER(TRIM(NEW.company))
      AND item_code = NEW.item_code
      AND id < NEW.id;  -- Delete older versions (keep the newest)
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Step 4: Create trigger that runs AFTER INSERT to clean up old versions
-- This ensures we never lose data if insert fails
DROP TRIGGER IF EXISTS trigger_cleanup_old_stock_versions ON current_stock;

CREATE TRIGGER trigger_cleanup_old_stock_versions
    AFTER INSERT ON current_stock
    FOR EACH ROW
    EXECUTE FUNCTION cleanup_old_stock_versions();

-- Step 5: Create a function to clean up duplicates manually (for maintenance)
CREATE OR REPLACE FUNCTION cleanup_current_stock_duplicates()
RETURNS TABLE(
    deleted_count BIGINT,
    remaining_count BIGINT
) AS $$
DECLARE
    deleted BIGINT;
    remaining BIGINT;
BEGIN
    -- Delete old versions, keeping only the most recent (highest id)
    DELETE FROM current_stock a
    USING current_stock b
    WHERE UPPER(TRIM(a.branch)) = UPPER(TRIM(b.branch))
      AND UPPER(TRIM(a.company)) = UPPER(TRIM(b.company))
      AND a.item_code = b.item_code
      AND a.id < b.id;
    
    GET DIAGNOSTICS deleted = ROW_COUNT;
    
    SELECT COUNT(*) INTO remaining FROM current_stock;
    
    RETURN QUERY SELECT deleted, remaining;
END;
$$ LANGUAGE plpgsql;

-- Step 6: Add comment to document the cleanup strategy
COMMENT ON FUNCTION cleanup_old_stock_versions() IS 
'Automatically deletes old stock versions when new ones are inserted. Ensures only one version per (branch, company, item_code) exists.';

COMMENT ON FUNCTION cleanup_current_stock_duplicates() IS 
'Manual cleanup function to remove duplicate stock records. Keeps only the most recent version (highest id) per (branch, company, item_code).';

-- Step 7: Vacuum to reclaim space
VACUUM ANALYZE current_stock;

DO $$
BEGIN
    RAISE NOTICE '✅ Migration complete: current_stock duplicates cleaned and triggers created';
END $$;

