import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.db.session import engine
from app.db.base import Base
import app.models  # Import all models

def create_all_tables():
    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)
    print("All tables created!")

if __name__ == "__main__":
    create_all_tables()