from sqlalchemy.orm import Session
from app.models.notification import Notification

class NotificationService:

    @staticmethod
    def create(db: Session, data):
        notification = Notification(**data.dict())
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification

    @staticmethod
    def mark_as_read(db: Session, notification_id):
        notification = db.query(Notification).get(notification_id)
        if notification:
            notification.status = "READ"
            db.commit()
        return notification