import os
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))
inspector = inspect(engine)

with open("db_info.txt", "w") as f:
    def check_table(table_name):
        f.write(f"\nChecking table: {table_name}\n")
        try:
            columns = inspector.get_columns(table_name)
            for column in columns:
                f.write(f"Column: {column['name']}, Type: {column['type']}\n")
        except Exception as e:
            f.write(f"Error checking {table_name}: {e}\n")

    check_table("notifications")
    check_table("users")
