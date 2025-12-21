"""
Script to copy database from distribution folder to web app cache
"""
import os
import shutil
from pathlib import Path

def copy_database():
    """Copy database from distribution folder to web app cache"""
    # Paths
    dist_db = Path("distribution/PharmaStockApp_v2.0/database/pharma_stock.db")
    cache_dir = Path("web_app/cache")
    cache_db = cache_dir / "pharma_stock.db"
    
    # Check if distribution database exists
    if not dist_db.exists():
        print(f"❌ Distribution database not found at: {dist_db}")
        print("   Please ensure the desktop version database exists.")
        return False
    
    # Create cache directory if it doesn't exist
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Get file size
    size_mb = dist_db.stat().st_size / (1024 * 1024)
    print(f"📊 Database size: {size_mb:.2f} MB")
    
    # Copy database
    print(f"📋 Copying database...")
    print(f"   From: {dist_db.absolute()}")
    print(f"   To:   {cache_db.absolute()}")
    
    try:
        shutil.copy2(dist_db, cache_db)
        print(f"✅ Database copied successfully!")
        print(f"   Location: {cache_db.absolute()}")
        return True
    except Exception as e:
        print(f"❌ Error copying database: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Database Copy Script")
    print("=" * 60)
    print()
    
    success = copy_database()
    
    if success:
        print()
        print("=" * 60)
        print("Next Steps:")
        print("=" * 60)
        print("1. Start your web app server:")
        print("   cd web_app")
        print("   python run.py")
        print()
        print("2. Go to Admin panel:")
        print("   http://localhost:8000/admin")
        print()
        print("3. Click '📤 Upload to Drive' button")
        print("   This will upload the database to Google Drive")
        print()
        print("4. After upload, you can refresh data or use the app")
        print("=" * 60)
    else:
        print()
        print("=" * 60)
        print("Copy failed. Please check the error messages above.")
        print("=" * 60)

