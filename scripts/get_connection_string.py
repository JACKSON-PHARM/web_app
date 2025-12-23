"""
Helper script to generate properly encoded connection string
"""
import urllib.parse

# Your password
password = "b?!HABE69$TwwSV"

# URL encode the password (encode all special characters)
encoded_password = urllib.parse.quote(password, safe='')

print("=" * 60)
print("YOUR SUPABASE CONNECTION STRING")
print("=" * 60)
print()
print("Password (original):", password)
print("Password (encoded):", encoded_password)
print()
print("Full connection string:")
print("-" * 60)
connection_string = f"postgresql://postgres:{encoded_password}@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres"
print(connection_string)
print("-" * 60)
print()
print("Copy the connection string above and use it for migration!")
print()
print("To test connection, run:")
print(f'  python scripts/test_connection.py "{connection_string}"')
print()
print("To migrate, run:")
print(f'  python scripts/migrate_to_supabase.py cache/pharma_stock.db "{connection_string}"')

