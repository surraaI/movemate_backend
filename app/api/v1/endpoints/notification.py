from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.notification_service import NotificationService
from app.schemas.notification import NotificationCreate
from app.models.notification import Notification

router = APIRouter()

@router.post("/")
def create_notification(data: NotificationCreate, db: Session = Depends(get_db)):
    return NotificationService.create(db, data)

@router.get("/")
def get_notifications(db: Session = Depends(get_db)):
    return db.query(Notification).all()

@router.put("/{id}/read")
def mark_as_read(id: str, db: Session = Depends(get_db)):
    return NotificationService.mark_as_read(db, id)