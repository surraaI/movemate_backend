# app/api/v1/endpoints/notification.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.notification_service import NotificationService
from app.schemas.notification import NotificationCreate
from app.models.notification import Notification
from app.models.user import User
from app.models.enums import UserRole
from app.core.deps import get_current_user, require_roles
from app.schemas.notification import NotificationOut

router = APIRouter()


# =========================================================
# CREATE NOTIFICATION
# Only ADMIN can create notifications
# =========================================================

@router.post("/", response_model=NotificationOut)
def create_notification(
    payload: NotificationCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):

    test_token = "test_token"

    return NotificationService.create(
        db,
        payload,
        device_token=test_token
    )

# =========================================================
# GET CURRENT USER NOTIFICATIONS
# Any authenticated user can access
# =========================================================
@router.get("/")
def get_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Notification)
        .filter(Notification.user_id == current_user.user_id)
        .all()
    )


# =========================================================
# MARK NOTIFICATION AS READ
# User can only mark THEIR OWN notification
# =========================================================
@router.put("/{id}/read")
def mark_as_read(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification = (
        db.query(Notification)
        .filter(Notification.id == id)
        .first()
    )

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    # Prevent users from modifying others' notifications
    if notification.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this notification",
        )

    return NotificationService.mark_as_read(db, id)