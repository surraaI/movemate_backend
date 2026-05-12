import requests
import uuid
from app.core.config import settings


class PaymentConfigError(RuntimeError):
    pass


def initiate_payment(amount: int, email: str):
    if not settings.CHAPA_SECRET_KEY:
        raise PaymentConfigError("CHAPA_SECRET_KEY is not set")

    tx_ref = f"tx-{uuid.uuid4()}"

    payload = {
        "amount": str(amount),
        "currency": "ETB",
        "email": email,
        "first_name": "MoveMate",
        "last_name": "User",
        "phone_number": "0912345678",
        "tx_ref": tx_ref,
        "callback_url": settings.CHAPA_CALLBACK_URL,
        "return_url": settings.CHAPA_RETURN_URL,
        "customization": {
            "title": "MoveMate",
            "description": "Bus ticket payment"
        }
    }

    headers = {
        "Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        f"{settings.CHAPA_BASE_URL}/transaction/initialize",
        json=payload,
        headers=headers
    )

    # 🔥 DEBUG OUTPUT
    print("STATUS CODE:", response.status_code)
    print("RESPONSE:", response.text)

    data = response.json()

    # 🔥 SAFETY CHECKS
    if response.status_code not in [200, 201]:
        raise Exception(f"Chapa request failed: {data}")

    if not data.get("data"):
        raise Exception(f"Invalid Chapa response: {data}")

    checkout_url = data["data"].get("checkout_url")

    if not checkout_url:
        raise Exception(f"checkout_url missing: {data}")

    return {
        "tx_ref": tx_ref,
        "checkout_url": checkout_url
    }


def verify_payment(tx_ref: str):
    if not settings.CHAPA_SECRET_KEY:
        raise PaymentConfigError("CHAPA_SECRET_KEY is not set")

    url = f"{settings.CHAPA_BASE_URL}/transaction/verify/{tx_ref}"

    headers = {
        "Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}"
    }

    response = requests.get(url, headers=headers)

    print("VERIFY RESPONSE:", response.text)

    return response.json()