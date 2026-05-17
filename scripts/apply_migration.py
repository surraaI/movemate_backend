#!/usr/bin/env python
"""Apply migration to add price and distance_km columns to routes table"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from sqlalchemy import text

def main():
    db = SessionLocal()
    try:
        print("Applying migration: add price and distance_km columns to routes...")
        
        # Add price column
        try:
            db.execute(text('''
                ALTER TABLE routes 
                ADD COLUMN price numeric(10,2) NOT NULL DEFAULT 0.00
            '''))
            print("✅ Added price column")
        except Exception as e:
            if "already exists" in str(e):
                print("ℹ️  price column already exists")
            else:
                raise
        
        # Add distance_km column
        try:
            db.execute(text('''
                ALTER TABLE routes 
                ADD COLUMN distance_km numeric DEFAULT NULL
            '''))
            print("✅ Added distance_km column")
        except Exception as e:
            if "already exists" in str(e):
                print("ℹ️  distance_km column already exists")
            else:
                raise
        
        db.commit()
        print("\n✅ Migration applied successfully!")
        
        # Verify columns were added
        result = db.execute(text('''
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'routes' 
            ORDER BY column_name
        '''))
        columns = [row[0] for row in result]
        print(f"\nRoutes table columns: {', '.join(columns)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
