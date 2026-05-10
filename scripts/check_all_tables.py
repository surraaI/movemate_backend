import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.db.session import engine
from sqlalchemy import inspect
from app.db.base import Base
import app.models


def check_database_tables():
    inspector = inspect(engine)
    
    output_file = Path(__file__).parent / "database_table_status.txt"
    with output_file.open("w", encoding="utf-8") as f:
        f.write("=== DATABASE TABLES ===\n")
        existing_tables = sorted(inspector.get_table_names())
        for table in existing_tables:
            f.write(f"- {table}\n")
        
        f.write("\n=== MODELS ===")
        model_tables = sorted(Base.metadata.tables.keys())
        for table in model_tables:
            f.write(f"- {table}\n")
        
        f.write("\n=== MISSING TABLES ===\n")
        missing = set(model_tables) - set(existing_tables)
        if missing:
            for table in sorted(missing):
                f.write(f"- {table}\n")
        else:
            f.write("No missing tables found! All models have tables in the database!\n")
    
    print(f"Database table status written to: {output_file}")


if __name__ == "__main__":
    check_database_tables()
