-- Create PostgreSQL function to refresh materialized views
-- This can be called via Supabase API or scheduled job

CREATE OR REPLACE FUNCTION refresh_materialized_views()
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result json;
    start_time timestamp;
    end_time timestamp;
BEGIN
    start_time := clock_timestamp();
    
    -- Refresh stock view materialized view
    BEGIN
        REFRESH MATERIALIZED VIEW CONCURRENTLY stock_view_materialized;
    EXCEPTION WHEN OTHERS THEN
        -- If CONCURRENTLY fails, try without it
        REFRESH MATERIALIZED VIEW stock_view_materialized;
    END;
    
    -- Refresh priority items materialized view
    BEGIN
        REFRESH MATERIALIZED VIEW CONCURRENTLY priority_items_materialized;
    EXCEPTION WHEN OTHERS THEN
        -- If CONCURRENTLY fails, try without it
        REFRESH MATERIALIZED VIEW priority_items_materialized;
    END;
    
    end_time := clock_timestamp();
    
    result := json_build_object(
        'success', true,
        'message', 'Materialized views refreshed successfully',
        'duration_seconds', EXTRACT(EPOCH FROM (end_time - start_time)),
        'refreshed_at', end_time
    );
    
    RETURN result;
END;
$$;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION refresh_materialized_views() TO authenticated;

-- Create a simple endpoint function that can be called via HTTP
-- Note: Supabase Edge Functions are better for HTTP endpoints, but this works too
COMMENT ON FUNCTION refresh_materialized_views() IS 'Refreshes stock_view_materialized and priority_items_materialized views. Can be called via Supabase API or scheduled job.';

