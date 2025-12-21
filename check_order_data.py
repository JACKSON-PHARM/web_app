#!/usr/bin/env python3
"""Check if order/supply/invoice data exists in the database"""
import sqlite3
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def check_data():
    db_path = os.path.join('web_app', 'cache', 'pharma_stock.db')
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        return
    
    print(f"✅ Database found: {db_path}")
    print(f"   Size: {os.path.getsize(db_path) / (1024*1024):.2f} MB\n")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('purchase_orders', 'supplier_invoices', 'hq_invoices', 'goods_received_notes')")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"📋 Tables found: {tables}\n")
    
    # Check purchase_orders
    print("=" * 70)
    print("PURCHASE ORDERS")
    print("=" * 70)
    cursor.execute("SELECT COUNT(*) FROM purchase_orders")
    total = cursor.fetchone()[0]
    print(f"Total records: {total}")
    
    if total > 0:
        cursor.execute("SELECT DISTINCT branch, company, COUNT(*) as cnt FROM purchase_orders GROUP BY branch, company ORDER BY cnt DESC LIMIT 10")
        branches = cursor.fetchall()
        print(f"\nTop branches:")
        for branch, company, cnt in branches:
            print(f"  '{branch}' ({company}): {cnt} records")
        
        # Check for DAIMA MERU WHOLESALE
        cursor.execute("SELECT COUNT(*) FROM purchase_orders WHERE UPPER(TRIM(branch)) = UPPER(TRIM('DAIMA MERU WHOLESALE')) AND UPPER(TRIM(company)) = UPPER(TRIM('DAIMA'))")
        count = cursor.fetchone()[0]
        print(f"\nDAIMA MERU WHOLESALE (DAIMA): {count} records")
        
        if count == 0:
            cursor.execute("SELECT DISTINCT branch FROM purchase_orders WHERE UPPER(TRIM(company)) = UPPER(TRIM('DAIMA')) LIMIT 10")
            daima_branches = cursor.fetchall()
            print(f"  Available DAIMA branches: {[b[0] for b in daima_branches]}")
    
    # Check supplier_invoices
    print("\n" + "=" * 70)
    print("SUPPLIER INVOICES")
    print("=" * 70)
    cursor.execute("SELECT COUNT(*) FROM supplier_invoices")
    total = cursor.fetchone()[0]
    print(f"Total records: {total}")
    
    if total > 0:
        cursor.execute("SELECT DISTINCT branch, company, COUNT(*) as cnt FROM supplier_invoices GROUP BY branch, company ORDER BY cnt DESC LIMIT 10")
        branches = cursor.fetchall()
        print(f"\nTop branches:")
        for branch, company, cnt in branches:
            print(f"  '{branch}' ({company}): {cnt} records")
        
        cursor.execute("SELECT COUNT(*) FROM supplier_invoices WHERE UPPER(TRIM(branch)) = UPPER(TRIM('DAIMA MERU WHOLESALE')) AND UPPER(TRIM(company)) = UPPER(TRIM('DAIMA'))")
        count = cursor.fetchone()[0]
        print(f"\nDAIMA MERU WHOLESALE (DAIMA): {count} records")
    
    # Check hq_invoices
    print("\n" + "=" * 70)
    print("HQ INVOICES")
    print("=" * 70)
    cursor.execute("SELECT COUNT(*) FROM hq_invoices")
    total = cursor.fetchone()[0]
    print(f"Total records: {total}")
    
    if total > 0:
        cursor.execute("SELECT DISTINCT branch, company, COUNT(*) as cnt FROM hq_invoices GROUP BY branch, company ORDER BY cnt DESC LIMIT 10")
        branches = cursor.fetchall()
        print(f"\nTop branches:")
        for branch, company, cnt in branches:
            print(f"  '{branch}' ({company}): {cnt} records")
        
        cursor.execute("SELECT COUNT(*) FROM hq_invoices WHERE UPPER(TRIM(branch)) = UPPER(TRIM('DAIMA MERU WHOLESALE')) AND UPPER(TRIM(company)) = UPPER(TRIM('DAIMA'))")
        count = cursor.fetchone()[0]
        print(f"\nDAIMA MERU WHOLESALE (DAIMA): {count} records")
    
    # Check goods_received_notes
    print("\n" + "=" * 70)
    print("GOODS RECEIVED NOTES")
    print("=" * 70)
    cursor.execute("SELECT COUNT(*) FROM goods_received_notes")
    total = cursor.fetchone()[0]
    print(f"Total records: {total}")
    
    if total > 0:
        cursor.execute("SELECT DISTINCT branch, company, COUNT(*) as cnt FROM goods_received_notes GROUP BY branch, company ORDER BY cnt DESC LIMIT 10")
        branches = cursor.fetchall()
        print(f"\nTop branches:")
        for branch, company, cnt in branches:
            print(f"  '{branch}' ({company}): {cnt} records")
        
        cursor.execute("SELECT COUNT(*) FROM goods_received_notes WHERE UPPER(TRIM(branch)) = UPPER(TRIM('DAIMA MERU WHOLESALE')) AND UPPER(TRIM(company)) = UPPER(TRIM('DAIMA'))")
        count = cursor.fetchone()[0]
        print(f"\nDAIMA MERU WHOLESALE (DAIMA): {count} records")
    
    conn.close()

if __name__ == "__main__":
    check_data()

