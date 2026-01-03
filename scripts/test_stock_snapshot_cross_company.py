"""Test stock_snapshot function with cross-company parameters"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config import settings
import psycopg2

conn = psycopg2.connect(settings.DATABASE_URL)
cursor = conn.cursor()

# Test the function with 4 parameters (new signature)
try:
    cursor.execute("""
        SELECT * FROM stock_snapshot(
            'DAIMA MERU WHOLESALE'::text,
            'BABA DOGO HQ'::text,
            'DAIMA'::text,
            'NILA'::text
        ) LIMIT 1
    """)
    result = cursor.fetchone()
    if result:
        print("SUCCESS: Function accepts 4 parameters (cross-company support)")
        print(f"Sample result: {result[0] if result else 'No data'}")
    else:
        print("Function executed but returned no data (this is OK if no matching data)")
except psycopg2.errors.UndefinedFunction as e:
    print(f"ERROR: Function doesn't accept 4 parameters: {e}")
    print("The function needs to be updated")
except Exception as e:
    print(f"Other error: {e}")

cursor.close()
conn.close()

