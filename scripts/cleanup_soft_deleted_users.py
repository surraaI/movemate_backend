from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.db.session import SessionLocal
from app.models.enums import UserStatus
from app.models.user import User
from app.services.admin_service import AdminService


def main() -> None:
    db = SessionLocal()
    cleaned = 0
    try:
        user_ids = [
            user_id
            for (user_id,) in db.query(User.user_id).filter(User.status == UserStatus.INACTIVE).all()
        ]

        for user_id in user_ids:
            if AdminService.hard_delete_user(db, user_id):
                cleaned += 1

        print(f"Cleaned {cleaned} soft-deleted user(s)")
    finally:
        db.close()


if __name__ == "__main__":
    main()