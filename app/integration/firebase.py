import logging
from typing import Optional, Dict, Any
import firebase_admin
from firebase_admin import credentials, messaging
from app.core.config import settings

logger = logging.getLogger(__name__)

class FirebaseError(Exception):
    """Custom exception for Firebase-related errors"""
    pass

# Initialize Firebase App
_firebase_app = None

def _get_firebase_app():
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app
    
    if not settings.FIREBASE_SERVICE_ACCOUNT or settings.FIREBASE_SERVICE_ACCOUNT == "dummy":
        logger.warning("Firebase service account not configured. Push notifications will be disabled.")
        return None

    import os
    if not os.path.exists(settings.FIREBASE_SERVICE_ACCOUNT):
        logger.error(f"Firebase service account file not found at: {settings.FIREBASE_SERVICE_ACCOUNT}")
        return None

    try:
        cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT)
        _firebase_app = firebase_admin.initialize_app(cred)
        return _firebase_app
    except Exception as e:
        logger.error(f"Failed to initialize Firebase app: {e}")
        return None

def send_push(
    token: str,
    title: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
    tag: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send push notification to a single device with platform-specific enhancements
    """
    app = _get_firebase_app()
    if not app:
        logger.info(f"[Firebase disabled] Would send: {title} - {message} to {token}")
        return {"success": True, "message": "Firebase not configured"}

    # FCM data payload must be Dict[str, str]
    safe_data = {}
    if data:
        for k, v in data.items():
            safe_data[str(k)] = str(v) if v is not None else ""

    try:
        msg = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=message,
            ),
            token=token,
            data=safe_data,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    sound="default",
                    tag=tag,  # Optional tag for grouping/replacing notifications
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound="default", badge=1),
                ),
            ),
        )
        response = messaging.send(msg, app=app)
        logger.info(f"Successfully sent Firebase message: {response}")
        return {"success": True, "response": response}
    except Exception as e:
        logger.error(f"Error sending Firebase message: {e}")
        raise FirebaseError(f"FCM Error: {str(e)}")

def send_multicast(
    tokens: list[str],
    title: str,
    message: str,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Send push notifications to multiple devices
    (FCM v1 doesn't support batch in one call → loop)
    """

    results = []

    for token in tokens:
        try:
            result = send_push(token, title, message, data)
            results.append({
                "token": token,
                "success": True,
                "response": result
            })
        except FirebaseError as e:
            results.append({
                "token": token,
                "success": False,
                "error": str(e)
            })

    return {"results": results}