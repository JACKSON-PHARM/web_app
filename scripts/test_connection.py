"""
Test Supabase PostgreSQL Connection
"""
import psycopg2
import sys

def test_connection(connection_string: str):
    """Test PostgreSQL connection"""
    try:
        print("Testing connection to Supabase...")
        conn = psycopg2.connect(connection_string)
        cursor = conn.cursor()
        
        # Test query
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"Connected successfully!")
        print(f"PostgreSQL version: {version}")
        
        # List tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        if tables:
            print(f"\nFound {len(tables)} tables:")
            for (table_name,) in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"   - {table_name}: {count:,} rows")
        else:
            print("\nNo tables found (database is empty)")
        
        conn.close()
        return True
        
    except psycopg2.OperationalError as e:
        print(f"Connection failed: {e}")
        print("\nTroubleshooting:")
        print("   1. Check if password is correct")
        print("   2. Try Session Pooler instead of Direct connection")
        print("   3. Check if your network supports IPv6 (or use IPv4)")
        return False
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_connection.py <connection_string>")
        print("\nExample:")
        print('  python test_connection.py "postgresql://postgres:password@db.xxx.supabase.co:5432/postgres"')
        sys.exit(1)
    
    connection_string = sys.argv[1]
    success = test_connection(connection_string)
    
    if success:
        print("\nConnection test passed! Ready to migrate.")
    else:
        print("\nConnection test failed. Fix issues above before migrating.")
        sys.exit(1)

