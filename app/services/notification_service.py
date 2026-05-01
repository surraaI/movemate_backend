from sqlalchemy.orm import Session
from app.models.notification import Notification
from app.integration.firebase import send_push, FirebaseError


class NotificationService:

    @staticmethod
    def create(db: Session, data, device_token: str = None):
        # 1. Save notification in DB
        notification = Notification(**data.dict())
        notification.status = "SENT"

        db.add(notification)
        db.commit()
        db.refresh(notification)

        # 2. Send push notification (THIS is where token is used)
        if device_token:
            try:
                send_push(
                    token=device_token,
                    title=notification.title,
                    message=notification.message,
                    data={
                        "notification_id": str(notification.id),
                        "type": notification.type
                    }
                )
            except FirebaseError as e:
                # 3. Update status if push fails
                notification.status = "FAILED"
                db.commit()
                print("Push failed:", e)
        else:
            print("No device token → skipping push")

        return notification

    @staticmethod
    def mark_as_read(db: Session, notification_id):
        notification = db.query(Notification).get(notification_id)

        if notification:
            notification.status = "READ"
            db.commit()

        return notification