"""Verify stock_snapshot function signature"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config import settings
import psycopg2

conn = psycopg2.connect(settings.DATABASE_URL)
cursor = conn.cursor()
cursor.execute("""
    SELECT pg_get_function_arguments(oid) 
    FROM pg_proc 
    WHERE proname = 'stock_snapshot' 
    AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
    LIMIT 1
""")
result = cursor.fetchone()
if result:
    print(f"Function signature: stock_snapshot({result[0]})")
    if 'p_target_company' in result[0] and 'p_source_company' in result[0]:
        print("SUCCESS: Function updated correctly with cross-company support!")
    else:
        print("WARNING: Function may not have been updated correctly")
else:
    print("ERROR: Function not found")
cursor.close()
conn.close()

