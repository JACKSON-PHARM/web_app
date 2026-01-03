"""Test that item names are correctly retrieved from current_stock when inventory_analysis has NO SALES DATA"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config import settings
import psycopg2

conn = psycopg2.connect(settings.DATABASE_URL)
cursor = conn.cursor()

# Test: Find items with NO SALES DATA in inventory_analysis and verify they get item_name from current_stock
cursor.execute("""
    SELECT 
        ia.item_code,
        ia.item_name as inventory_analysis_name,
        result.item_name as final_item_name
    FROM inventory_analysis_new ia
    LEFT JOIN LATERAL (
        SELECT * FROM stock_snapshot(
            ia.branch_name::text,
            'BABA DOGO HQ'::text,
            ia.company_name::text,
            'NILA'::text
        ) WHERE item_code = ia.item_code
        LIMIT 1
    ) result ON true
    WHERE UPPER(TRIM(ia.item_name)) LIKE 'NO SALES%'
    LIMIT 5
""")

results = cursor.fetchall()
if results:
    print(f"Found {len(results)} items with NO SALES in inventory_analysis:")
    for row in results:
        item_code, inv_name, final_name = row
        if final_name and final_name.strip() and final_name.upper() not in ('NO SALES', 'NO SALES DATA', ''):
            print(f"  SUCCESS: {item_code} - '{inv_name}' -> '{final_name}'")
        else:
            print(f"  WARNING: {item_code} - '{inv_name}' -> '{final_name}' (still NO SALES)")
else:
    print("No items with NO SALES found, or function returned no results")

cursor.close()
conn.close()

