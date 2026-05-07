from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.notification_service import NotificationService
from app.schemas.notification import NotificationCreate, NotificationOut
from app.models.notification import Notification
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=NotificationOut)
def create_notification(data: NotificationCreate, db: Session = Depends(get_db)):
    return NotificationService.create(db, data)


@router.get("/", response_model=list[NotificationOut])
def get_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Notification).filter(Notification.user_id == current_user.user_id).all()


@router.put("/{id}/read", response_model=NotificationOut)
def mark_as_read(id: str, db: Session = Depends(get_db)):
    return NotificationService.mark_as_read(db, id)