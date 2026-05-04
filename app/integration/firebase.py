import requests
from typing import Optional, Dict, Any
from google.oauth2 import service_account
from google.auth.transport.requests import Request

from app.core.config import settings


class FirebaseError(Exception):
    """Custom exception for Firebase-related errors"""
    pass


def _get_access_token() -> str:
    """
    Generate OAuth2 access token using service account
    """
    credentials = service_account.Credentials.from_service_account_file(
        settings.FIREBASE_SERVICE_ACCOUNT,
        scopes=["https://www.googleapis.com/auth/firebase.messaging"]
    )

    credentials.refresh(Request())
    return credentials.token


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
        Firebase response dict
    """

    if not settings.FIREBASE_PROJECT_ID:
        raise FirebaseError("FIREBASE_PROJECT_ID is not set")

    access_token = _get_access_token()

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