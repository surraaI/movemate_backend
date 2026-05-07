from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.notification_service import NotificationService
from app.schemas.notification import NotificationCreate
from app.models.notification import Notification
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.post("/")
def create_notification(data: NotificationCreate, db: Session = Depends(get_db)):
    return NotificationService.create(db, data)



@router.get("/")
def get_notifications(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user) # Logic runs automatically
):
    # Use the authenticated user's ID
    return db.query(Notification).filter(Notification.user_id == current_user.user_id).all()

@router.put("/{id}/read")
def mark_as_read(id: str, db: Session = Depends(get_db)):
    return NotificationService.mark_as_read(db, id)