"""
Test script to verify MySQL database connection and table creation.
"""
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import init_database, get_db, User
from app.config import settings

def test_database_connection():
    """Test database connection and table creation."""
    print("=" * 70)
    print("Testing MySQL Database Connection")
    print("=" * 70)
    
    print(f"\nDatabase Configuration:")
    print(f"  Host: {settings.DB_HOST}")
    print(f"  Port: {settings.DB_PORT}")
    print(f"  Database: {settings.DB_NAME}")
    print(f"  User: {settings.DB_USER}")
    print(f"  Password: {'*' * len(settings.DB_PASSWORD) if settings.DB_PASSWORD else '(empty)'}")
    
    try:
        # Initialize database
        print("\nInitializing database connection...")
        if init_database():
            print("SUCCESS: Database connection successful!")
            
            # Test creating a simple query
            print("\nTesting database query...")
            db = get_db()
            
            # Check if tables exist by querying
            from sqlalchemy import text
            result = db.execute(text("SHOW TABLES"))
            tables = [row[0] for row in result]
            
            print(f"SUCCESS: Found {len(tables)} tables:")
            for table in tables:
                print(f"   - {table}")
            
            db.close()
            
            print("\n" + "=" * 70)
            print("SUCCESS: DATABASE CONNECTION TEST PASSED")
            print("=" * 70)
            return True
        else:
            print("FAILED: Database connection failed")
            return False
            
    except Exception as e:
        print(f"FAILED: Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_database_connection()
    sys.exit(0 if success else 1)
