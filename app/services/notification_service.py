# app/services/notification_service.py

import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.integration.firebase import send_push, FirebaseError


class NotificationService:

    @staticmethod
    def create(db: Session, data, device_token: str = None):
        # Explicitly generate a string ID to avoid any UUID type issues
        notification_id = str(uuid.uuid4())
        
        # Save notification
        notification = Notification(
            id=notification_id,
            user_id=data.user_id,
            title=data.title,
            message=data.message,
            type=data.type,
            status="SENT"
        )

        db.add(notification)
        db.commit()
        db.refresh(notification)

        # Send push notification
        if device_token:
            try:
                send_push(
                    token=device_token,
                    title=notification.title,
                    message=notification.message,
                    data={
                        "notification_id": str(notification.id),
                        "type": notification.type,
                    },
                )

            except FirebaseError as e:
                notification.status = "FAILED"
                db.commit()

                print("Push failed:", e)

        else:
            print("No device token → skipping push")

    
        return notification

    @staticmethod
    def mark_as_read(db: Session, notification_id: str):

        notification = (
            db.query(Notification)
            .filter(Notification.id == notification_id)
            .first()
        )

        if notification:
            notification.status = "READ"
            notification.read_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(notification)

        if notification:
            notification.status = "READ"
            db.commit()
        return notification