import logging
from typing import Optional, Dict, Any
import firebase_admin
from firebase_admin import credentials, messaging
from app.core.config import settings

logger = logging.getLogger(__name__)
import requests

from google.oauth2 import service_account
from google.auth.transport.requests import Request




class FirebaseError(Exception):
    """Custom exception for Firebase-related errors"""
    pass


def _get_access_token() -> str | None:
    """
    Generate OAuth2 access token using service account
    """
    if not settings.FIREBASE_SERVICE_ACCOUNT:
        raise FirebaseError("FIREBASE_SERVICE_ACCOUNT is not set")

    credentials = service_account.Credentials.from_service_account_file(
        settings.FIREBASE_SERVICE_ACCOUNT,
        scopes=["https://www.googleapis.com/auth/firebase.messaging"]
    )

    try:
        credentials = service_account.Credentials.from_service_account_file(
            settings.FIREBASE_SERVICE_ACCOUNT,
            scopes=["https://www.googleapis.com/auth/firebase.messaging"]
        )
        credentials.refresh(Request())
        return credentials.token
    except Exception as e:
        print(f"Firebase token error (expected in development): {e}")
        return None


def send_push(
    token: str,
    title: str,
    message: str,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Send push notification to a single device

    Args:
        token: Device FCM token
        title: Notification title
        message: Notification body
        data: Optional custom payload

    Returns:
        Firebase response dict or dummy success dict
    """

    if not settings.FIREBASE_PROJECT_ID or settings.FIREBASE_PROJECT_ID == "dummy":
        print(f"[Firebase disabled in dev] Not sending push: {title} - {message}")
        return {"success": True, "message": "Push notifications disabled in development"}

    access_token = _get_access_token()
    if not access_token:
        print(f"[Firebase disabled in dev] Not sending push: {title} - {message}")
        return {"success": True, "message": "Push notifications disabled in development"}

    url = f"https://fcm.googleapis.com/v1/projects/{settings.FIREBASE_PROJECT_ID}/messages:send"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "message": {
            "token": token,
            "notification": {
                "title": title,
                "body": message
            },
            "data": data or {}
        }
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=10
        )

        if response.status_code != 200:
            raise FirebaseError(f"FCM Error: {response.text}")

        return response.json()

    except requests.RequestException as e:
        raise FirebaseError(f"Request failed: {str(e)}")


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