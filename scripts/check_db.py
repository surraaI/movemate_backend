import os
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))
inspector = inspect(engine)

def check_table(table_name):
    print(f"\nChecking table: {table_name}")
    columns = inspector.get_columns(table_name)
    for column in columns:
        print(f"Column: {column['name']}, Type: {column['type']}")

try:
    check_table("notifications")
    check_table("users")
except Exception as e:
    print(f"Error: {e}")
